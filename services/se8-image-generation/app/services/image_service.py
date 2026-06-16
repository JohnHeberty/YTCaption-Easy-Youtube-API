import httpx
from fastapi import HTTPException
from fastapi.responses import Response
from typing import Optional

from app.core.config import get_settings
from common.log_utils import get_logger

logger = get_logger(__name__)
settings = get_settings()

DEFAULT_LORAS_JSON = '[{"enabled":true,"model_name":"sd_xl_offset_example-lora_1.0.safetensors","weight":0.1},{"enabled":true,"model_name":"None","weight":1.0},{"enabled":true,"model_name":"None","weight":1.0},{"enabled":true,"model_name":"None","weight":1.0},{"enabled":true,"model_name":"None","weight":1.0}]'

DEFAULT_STYLES = ["Fooocus V2", "Fooocus Enhance", "Fooocus Sharp"]


class FooocusClient:
    def __init__(self):
        self.base_url = settings.fooocus_api_url
        self.headers = {}
        if settings.fooocus_api_key:
            self.headers["X-API-Key"] = settings.fooocus_api_key
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=300.0)
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _build_headers(self, accept: str = None) -> dict:
        h = dict(self.headers)
        if accept:
            h["Accept"] = accept
        return h

    # =========================================================================
    # Generic proxy: forward raw HTTP request to fooocus-api
    # =========================================================================

    async def proxy_request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict = None,
        multipart_files: dict = None,
        multipart_data: dict = None,
        params: dict = None,
        accept: str = None,
    ):
        headers = self._build_headers(accept)
        client = await self._get_client()
        try:
            if multipart_files is not None:
                resp = await client.post(
                    f"{self.base_url}{path}",
                    files=multipart_files,
                    data=multipart_data or {},
                    headers=headers,
                )
            elif json_body is not None:
                resp = await client.request(
                    method,
                    f"{self.base_url}{path}",
                    json=json_body,
                    headers=headers,
                    params=params,
                )
            else:
                resp = await client.request(
                    method,
                    f"{self.base_url}{path}",
                    headers=headers,
                    params=params,
                )
        except httpx.RequestError as e:
            logger.error("proxy_request %s %s failed: %s", method, path, e)
            raise HTTPException(status_code=502, detail=f"Upstream connection error: {e}")

        if resp.status_code >= 400:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)

        try:
            return resp.json()
        except Exception:
            return resp.text

    async def proxy_raw_post(
        self,
        path: str,
        raw_body: bytes,
        content_type: str,
        accept: str = None,
    ) -> Response:
        headers = {"content-type": content_type, **self.headers}
        if accept:
            headers["Accept"] = accept
        client = await self._get_client()
        resp = await client.post(
            f"{self.base_url}{path}",
            content=raw_body,
            headers=headers,
        )
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            media_type=resp.headers.get("content-type", "application/json"),
        )

    # =========================================================================
    # V1 Generation (JSON proxy to FOOOCUS V1 — FOOOCUS accepts JSON too)
    # =========================================================================

    async def text_to_image(self, payload: dict, accept: str = None):
        return await self.proxy_request("POST", "/v1/generation/text-to-image", json_body=payload, accept=accept)

    async def image_upscale_vary(self, payload: dict, accept: str = None):
        return await self.proxy_request("POST", "/v1/generation/image-upscale-vary", json_body=payload, accept=accept)

    async def image_inpaint_outpaint(self, payload: dict, accept: str = None):
        return await self.proxy_request("POST", "/v1/generation/image-inpaint-outpaint", json_body=payload, accept=accept)

    async def image_prompt(self, payload: dict, accept: str = None):
        return await self.proxy_request("POST", "/v1/generation/image-prompt", json_body=payload, accept=accept)

    async def image_enhance(self, payload: dict, accept: str = None):
        return await self.proxy_request("POST", "/v1/generation/image-enhance", json_body=payload, accept=accept)

    async def stop(self):
        return await self.proxy_request("POST", "/v1/generation/stop")

    # =========================================================================
    # V2 Generation (JSON proxy)
    # =========================================================================

    async def text_to_image_v2(self, payload: dict, accept: str = None):
        return await self.proxy_request("POST", "/v2/generation/text-to-image-with-ip", json_body=payload, accept=accept)

    async def image_upscale_vary_v2(self, payload: dict, accept: str = None):
        return await self.proxy_request("POST", "/v2/generation/image-upscale-vary", json_body=payload, accept=accept)

    async def image_inpaint_outpaint_v2(self, payload: dict, accept: str = None):
        return await self.proxy_request("POST", "/v2/generation/image-inpaint-outpaint", json_body=payload, accept=accept)

    async def image_prompt_v2(self, payload: dict, accept: str = None):
        return await self.proxy_request("POST", "/v2/generation/image-prompt", json_body=payload, accept=accept)

    async def image_enhance_v2(self, payload: dict, accept: str = None):
        return await self.proxy_request("POST", "/v2/generation/image-enhance", json_body=payload, accept=accept)

    # =========================================================================
    # Query / Management
    # =========================================================================

    async def query_job(self, job_id: str, require_step_preview: bool = False):
        return await self.proxy_request(
            "GET", "/v1/generation/query-job",
            params={"job_id": job_id, "require_step_preview": require_step_preview},
        )

    async def job_queue(self):
        return await self.proxy_request("GET", "/v1/generation/job-queue")

    async def job_history(
        self,
        job_id: str = None,
        page: int = 0,
        page_size: int = 20,
        delete: bool = False,
    ):
        params = {"page": page, "page_size": page_size}
        if job_id:
            params["job_id"] = job_id
        if delete:
            params["delete"] = "true"
        return await self.proxy_request("GET", "/v1/generation/job-history", params=params)

    async def list_outputs(self):
        return await self.proxy_request("GET", "/v1/generation/outputs")

    async def get_output_file(self, date: str, file_name: str) -> tuple:
        client = await self._get_client()
        resp = await client.get(
            f"{self.base_url}/files/{date}/{file_name}",
            headers=self.headers,
        )
        if resp.status_code >= 400:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        content_type = resp.headers.get("content-type", "application/octet-stream")
        return resp.content, content_type

    # =========================================================================
    # Engines
    # =========================================================================

    async def all_models(self):
        return await self.proxy_request("GET", "/v1/engines/all-models")

    async def styles(self):
        return await self.proxy_request("GET", "/v1/engines/styles")

    async def styles_detail(self):
        return await self.proxy_request("GET", "/v1/engines/styles-detail")

    async def clean_vram(self):
        return await self.proxy_request("GET", "/v1/engines/clean_vram")

    # =========================================================================
    # Tools
    # =========================================================================

    async def describe_image(self, payload: dict):
        return await self.proxy_request("POST", "/v1/tools/describe-image", json_body=payload)

    async def generate_mask(self, payload: dict):
        return await self.proxy_request("POST", "/v1/tools/generate_mask", json_body=payload)

    # =========================================================================
    # Home
    # =========================================================================

    async def home(self):
        return await self.proxy_request("GET", "/")

    # =========================================================================
    # Health (ping)
    # =========================================================================

    async def health_check(self) -> bool:
        try:
            client = await self._get_client()
            resp = await client.get(f"{self.base_url}/ping")
            return resp.status_code == 200
        except Exception:
            return False


fooocus_client = FooocusClient()
