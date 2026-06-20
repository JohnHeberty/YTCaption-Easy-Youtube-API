from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from common.log_utils import get_logger

from app.api.schemas import VoiceProfileCreateResponse, DeleteVoiceResponse
from app.domain.exceptions import InvalidVoiceSample, VoiceProfileNotFound
from app.services.voice_manager import VoiceProfileManager
from app.infrastructure.dependencies import voice_manager

logger = get_logger(__name__)
router = APIRouter(prefix="/voices", tags=["Voices"])


@router.post("", response_model=VoiceProfileCreateResponse, status_code=201)
async def create_voice_profile(
    name: str = Form(...),
    description: str = Form(""),
    file: UploadFile = File(...),
    mgr: VoiceProfileManager = Depends(voice_manager),
) -> VoiceProfileCreateResponse:
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Empty file")

        profile = mgr.create_profile(
            name=name,
            file_content=content,
            description=description,
        )
        return VoiceProfileCreateResponse(
            id=profile.id,
            name=profile.name,
            description=profile.description,
            created_at=profile.created_at.isoformat(),
            duration_seconds=profile.duration_seconds,
            sample_rate=profile.sample_rate,
            status=profile.status,
            message="Voice profile created successfully",
        )

    except InvalidVoiceSample as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("")
async def list_voice_profiles(
    mgr: VoiceProfileManager = Depends(voice_manager),
) -> dict[str, Any]:
    profiles = mgr.list_profiles()
    return {
        "profiles": [p.model_dump() for p in profiles],
        "total": len(profiles),
    }


@router.get("/{voice_id}")
async def get_voice_profile(
    voice_id: str,
    mgr: VoiceProfileManager = Depends(voice_manager),
) -> dict[str, Any]:
    try:
        profile = mgr.get_profile(voice_id)
        return profile.model_dump()
    except VoiceProfileNotFound:
        raise HTTPException(status_code=404, detail=f"Voice profile not found: {voice_id}")


@router.get("/{voice_id}/sample")
async def download_voice_sample(
    voice_id: str,
    mgr: VoiceProfileManager = Depends(voice_manager),
) -> FileResponse:
    try:
        profile = mgr.get_profile(voice_id)
        return FileResponse(
            path=profile.audio_path,
            filename=f"voice_{voice_id}.wav",
            media_type="audio/wav",
        )
    except VoiceProfileNotFound:
        raise HTTPException(status_code=404, detail=f"Voice profile not found: {voice_id}")


@router.delete("/{voice_id}")
async def delete_voice_profile(
    voice_id: str,
    mgr: VoiceProfileManager = Depends(voice_manager),
) -> DeleteVoiceResponse:
    try:
        mgr.delete_profile(voice_id)
        return DeleteVoiceResponse(
            message="Voice profile deleted successfully",
            voice_id=voice_id,
        )
    except VoiceProfileNotFound:
        raise HTTPException(status_code=404, detail=f"Voice profile not found: {voice_id}")
