from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from common.log_utils import get_logger

from app.api.schemas import (
    DeleteVoiceResponse,
    ErrorResponse,
    VoiceProfileCreateResponse,
    VoiceProfileListResponse,
    VoiceProfileResponse,
)
from app.domain.exceptions import InvalidVoiceSample, VoiceProfileNotFound
from app.services.voice_manager import VoiceProfileManager
from app.infrastructure.dependencies import voice_manager

logger = get_logger(__name__)
router = APIRouter(prefix="/voices", tags=["Voices"])


@router.post(
    "",
    response_model=VoiceProfileCreateResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def create_voice_profile(
    name: str = Form(...),
    description: str = Form(""),
    file: UploadFile = File(...),
    mgr: VoiceProfileManager = Depends(voice_manager),
) -> VoiceProfileCreateResponse:
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")

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
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.get("", response_model=VoiceProfileListResponse)
async def list_voice_profiles(
    mgr: VoiceProfileManager = Depends(voice_manager),
) -> VoiceProfileListResponse:
    profiles = mgr.list_profiles()
    return VoiceProfileListResponse(
        profiles=[
            VoiceProfileResponse(
                id=p.id,
                name=p.name,
                description=p.description,
                created_at=p.created_at.isoformat(),
                duration_seconds=p.duration_seconds,
                sample_rate=p.sample_rate,
                status=p.status,
            )
            for p in profiles
        ],
        total=len(profiles),
    )


@router.get(
    "/{voice_id}",
    response_model=VoiceProfileResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_voice_profile(
    voice_id: str,
    mgr: VoiceProfileManager = Depends(voice_manager),
) -> VoiceProfileResponse:
    try:
        profile = mgr.get_profile(voice_id)
        return VoiceProfileResponse(
            id=profile.id,
            name=profile.name,
            description=profile.description,
            created_at=profile.created_at.isoformat(),
            duration_seconds=profile.duration_seconds,
            sample_rate=profile.sample_rate,
            status=profile.status,
        )
    except VoiceProfileNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Voice profile not found: {voice_id}")


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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Voice profile not found: {voice_id}")


@router.delete(
    "/{voice_id}",
    response_model=DeleteVoiceResponse,
    responses={404: {"model": ErrorResponse}},
)
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Voice profile not found: {voice_id}")
