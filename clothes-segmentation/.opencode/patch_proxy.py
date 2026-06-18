import json
import os
import time
import uuid

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import Response, StreamingResponse

LITELLM_BASE = os.getenv("LITELLM_BASE", "http://192.168.1.140:4000").rstrip("/")
FORCE_FIRST_TOOL = os.getenv("FORCE_FIRST_TOOL", "true").lower() == "true"
INJECT_TOOL_SYSTEM = os.getenv("INJECT_TOOL_SYSTEM", "true").lower() == "true"
SYNTHESIZE_FIRST_TOOL = os.getenv("SYNTHESIZE_FIRST_TOOL", "true").lower() == "true"

app = FastAPI()


def log(msg: str):
    print(msg, flush=True)


def filter_headers(headers: dict) -> dict:
    blocked = {
        "host",
        "content-length",
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
    }
    return {k: v for k, v in headers.items() if k.lower() not in blocked}


def load_json_body(body: bytes) -> dict | None:
    try:
        return json.loads(body.decode("utf-8")) if body else None
    except Exception:
        return None


def is_stream_request(payload: dict | None, request: Request) -> bool:
    if "text/event-stream" in request.headers.get("accept", ""):
        return True
    return bool(payload and payload.get("stream") is True)


def has_tools(payload: dict | None) -> bool:
    return bool(payload and payload.get("tools"))


def has_tool_result(payload: dict | None) -> bool:
    if not payload:
        return False
    return any(msg.get("role") == "tool" for msg in payload.get("messages", []))


def get_tool_names(payload: dict | None) -> list[str]:
    if not payload:
        return []

    names = []
    for tool in payload.get("tools", []):
        fn = tool.get("function") or {}
        name = fn.get("name")
        if name:
            names.append(name)

    return names


def find_tool(payload: dict | None, preferred: list[str]) -> dict | None:
    if not payload:
        return None

    tools = payload.get("tools", [])

    for wanted in preferred:
        for tool in tools:
            fn = tool.get("function") or {}
            if fn.get("name") == wanted:
                return tool

    for wanted in preferred:
        for tool in tools:
            fn = tool.get("function") or {}
            name = fn.get("name") or ""
            if wanted in name:
                return tool

    return tools[0] if tools else None


def build_args_for_tool(tool: dict) -> dict:
    fn = tool.get("function") or {}
    name = fn.get("name") or ""
    params = fn.get("parameters") or {}
    props = params.get("properties") or {}
    required = params.get("required") or []

    args = {}

    if name == "glob" or "glob" in name:
        args["pattern"] = "**/*"
        return args

    if name == "list" or "list" in name:
        args["path"] = "."
        return args

    if name == "bash" or "bash" in name:
        if "command" in props:
            args["command"] = "find . -maxdepth 3 -type f | sed 's#^./##' | head -200"
        elif "cmd" in props:
            args["cmd"] = "find . -maxdepth 3 -type f | sed 's#^./##' | head -200"

        if "description" in props:
            args["description"] = "Listar arquivos principais do projeto para análise inicial"

        return args

    for key in required:
        lk = key.lower()

        if lk in ("pattern", "glob", "include"):
            args[key] = "**/*"
        elif lk in ("path", "cwd", "dir", "directory"):
            args[key] = "."
        elif lk in ("command", "cmd"):
            args[key] = "find . -maxdepth 3 -type f | sed 's#^./##' | head -200"
        elif lk == "description":
            args[key] = "Listar arquivos principais do projeto para análise inicial"
        elif lk in ("query", "regex"):
            args[key] = "package.json|README|app.json|babel.config|metro.config|tsconfig"
        else:
            args[key] = ""

    return args


def synthesize_tool_call(payload: dict | None, request_id: str) -> dict | None:
    tool = find_tool(payload, ["glob", "list", "bash", "grep", "read"])
    if not tool:
        return None

    fn = tool.get("function") or {}
    name = fn.get("name")
    if not name:
        return None

    args = build_args_for_tool(tool)

    log(f"[patch-proxy:{request_id}] synthesizing tool_call name={name} args={args}")

    return {
        "id": f"chatcmpl-patch-{request_id}",
        "created": int(time.time()),
        "model": payload.get("model", "unknown") if payload else "unknown",
        "object": "chat.completion.chunk",
        "choices": [
            {
                "index": 0,
                "delta": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": f"call_patch_{request_id}",
                            "type": "function",
                            "index": 0,
                            "function": {
                                "name": name,
                                "arguments": json.dumps(args, ensure_ascii=False),
                            },
                        }
                    ],
                },
            }
        ],
    }


def synthesize_finish(payload: dict | None, request_id: str) -> dict:
    return {
        "id": f"chatcmpl-patch-{request_id}",
        "created": int(time.time()),
        "model": payload.get("model", "unknown") if payload else "unknown",
        "object": "chat.completion.chunk",
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": "tool_calls",
            }
        ],
    }


def patch_request_body(payload: dict | None) -> bytes | None:
    if not payload or not has_tools(payload):
        return None

    changed = False

    if INJECT_TOOL_SYSTEM:
        instruction = (
            "Você está rodando dentro do OpenCode. "
            "Quando precisar ler, listar, buscar, editar ou escrever arquivos, "
            "NÃO responda dizendo que vai fazer. Chame imediatamente uma das ferramentas disponíveis. "
            "Frases como 'vou analisar', 'deixa eu ler', 'vou explorar', 'vou verificar', "
            "'vou ler os arquivos' e 'vou executar' são inválidas quando uma ferramenta pode ser usada. "
            "Use resposta textual somente quando a tarefa já estiver concluída ou quando nenhuma ferramenta for necessária."
        )

        messages = payload.setdefault("messages", [])

        if messages and messages[0].get("role") == "system":
            current = messages[0].get("content") or ""
            if instruction not in current:
                messages[0]["content"] = current + "\n\n" + instruction
                changed = True
        else:
            messages.insert(0, {"role": "system", "content": instruction})
            changed = True

    if FORCE_FIRST_TOOL:
        if payload.get("tool_choice") in (None, "auto"):
            payload["tool_choice"] = "required"
            changed = True

    return json.dumps(payload, ensure_ascii=False).encode("utf-8") if changed else None


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "upstream": LITELLM_BASE,
        "force_first_tool": FORCE_FIRST_TOOL,
        "inject_tool_system": INJECT_TOOL_SYSTEM,
        "synthesize_first_tool": SYNTHESIZE_FIRST_TOOL,
    }


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def proxy(path: str, request: Request):
    request_id = str(uuid.uuid4())[:8]

    url = f"{LITELLM_BASE}/{path}"
    headers = filter_headers(dict(request.headers))
    original_body = await request.body()
    payload = load_json_body(original_body)

    patched_body = patch_request_body(payload)
    body = patched_body if patched_body is not None else original_body

    wants_stream = is_stream_request(payload, request)
    tools_count = len(payload.get("tools", [])) if payload else 0
    tool_names = get_tool_names(payload)
    model = payload.get("model") if payload else "-"
    has_prior_tool_result = has_tool_result(payload)

    log(
        f"[patch-proxy:{request_id}] request model={model} "
        f"stream={wants_stream} tools={tools_count} "
        f"tool_names={tool_names} "
        f"has_prior_tool_result={has_prior_tool_result} "
        f"forced_body={patched_body is not None}"
    )

    if wants_stream:
        async def stream_response():
            saw_tool_call = False
            saw_text = False
            patched_finish = False
            text_buffer = []

            # Importante:
            # antes havia "and not has_tool_result(payload)" aqui.
            # Isso impedia síntese em sessões do OpenCode que já tinham histórico de tool.
            can_synthesize = (
                SYNTHESIZE_FIRST_TOOL
                and has_tools(payload)
            )

            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    request.method,
                    url,
                    headers=headers,
                    content=body,
                    params=request.query_params,
                    timeout=None,
                ) as upstream:
                    async for line in upstream.aiter_lines():
                        if line == "":
                            continue

                        if not line.startswith("data: "):
                            if not can_synthesize:
                                yield line + "\n"
                            continue

                        raw = line[len("data: "):]

                        if raw == "[DONE]":
                            if can_synthesize and not saw_tool_call and saw_text:
                                synthetic = synthesize_tool_call(payload, request_id)
                                if synthetic:
                                    finish = synthesize_finish(payload, request_id)

                                    yield "data: " + json.dumps(synthetic, ensure_ascii=False) + "\n\n"
                                    yield "data: " + json.dumps(finish, ensure_ascii=False) + "\n\n"

                                    log(
                                        f"[patch-proxy:{request_id}] replaced text-only response with synthetic tool_call "
                                        f"text={''.join(text_buffer)[:200]!r}"
                                    )

                                    yield "data: [DONE]\n\n"
                                    return

                            yield "data: [DONE]\n\n"
                            log(
                                f"[patch-proxy:{request_id}] done "
                                f"saw_tool_call={saw_tool_call} "
                                f"saw_text={saw_text} "
                                f"patched_finish={patched_finish} "
                                f"text_preview={''.join(text_buffer)[:200]!r}"
                            )
                            return

                        try:
                            obj = json.loads(raw)
                        except json.JSONDecodeError:
                            if not can_synthesize:
                                yield line + "\n\n"
                            continue

                        for choice in obj.get("choices", []):
                            delta = choice.get("delta") or {}

                            if delta.get("tool_calls"):
                                saw_tool_call = True

                            content = delta.get("content")
                            if content:
                                saw_text = True
                                text_buffer.append(content)

                            if saw_tool_call and choice.get("finish_reason") == "stop":
                                choice["finish_reason"] = "tool_calls"
                                patched_finish = True

                        # Se ainda não veio tool_call, segura o texto para poder trocar por tool_call no [DONE].
                        if can_synthesize and not saw_tool_call:
                            continue

                        yield "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n"

            log(f"[patch-proxy:{request_id}] stream ended without DONE")

        return StreamingResponse(
            stream_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    async with httpx.AsyncClient(timeout=None) as client:
        upstream = await client.request(
            request.method,
            url,
            headers=headers,
            content=body,
            params=request.query_params,
            timeout=None,
        )

    log(f"[patch-proxy:{request_id}] non-stream status={upstream.status_code}")

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type"),
        headers=filter_headers(dict(upstream.headers)),
    )