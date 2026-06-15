import uuid
from pathlib import Path

from common.log_utils import get_logger

from app.core.constants import VOICE_SAMPLE_RATE_TARGET, VOICE_ID_PREFIX
from app.domain.models import VoiceProfile
from app.domain.interfaces import IVoiceStore
from app.domain.exceptions import InvalidVoiceSample, VoiceProfileNotFound
from app.services.audio_utils import validate_voice_sample, convert_to_mono_wav

logger = get_logger(__name__)


class VoiceProfileManager:
    def __init__(self, store: IVoiceStore, voices_dir: str):
        self._store = store
        self._voices_dir = Path(voices_dir)
        self._voices_dir.mkdir(parents=True, exist_ok=True)

    def create_profile(
        self,
        name: str,
        file_content: bytes,
        description: str = "",
        target_sr: int = VOICE_SAMPLE_RATE_TARGET,
    ) -> VoiceProfile:
        temp_path = self._voices_dir / f"temp_{uuid.uuid4().hex}.wav"
        try:
            temp_path.write_bytes(file_content)

            info = validate_voice_sample(str(temp_path))
            final_name = f"{VOICE_ID_PREFIX}{uuid.uuid4().hex[:16]}"
            final_path = self._voices_dir / f"{final_name}.wav"

            convert_to_mono_wav(str(temp_path), str(final_path), target_sr)

            profile = VoiceProfile(
                id=final_name,
                name=name,
                description=description,
                audio_path=str(final_path),
                duration_seconds=info["duration_seconds"],
                sample_rate=target_sr,
                status="active",
            )
            self._store.save_profile(profile)
            logger.info(f"Voice profile created: {profile.id} (name={name})")
            return profile

        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)

    def get_profile(self, voice_id: str) -> VoiceProfile:
        profile = self._store.get_profile(voice_id)
        if not profile:
            raise VoiceProfileNotFound(voice_id)
        return profile

    def list_profiles(self) -> list[VoiceProfile]:
        return self._store.list_profiles()

    def delete_profile(self, voice_id: str) -> None:
        profile = self.get_profile(voice_id)
        path = Path(profile.audio_path)
        if path.exists():
            path.unlink()
        self._store.delete_profile(voice_id)
        logger.info(f"Voice profile deleted: {voice_id}")

    def get_profile_audio_path(self, voice_id: str) -> str | None:
        profile = self._store.get_profile(voice_id)
        if not profile:
            return None
        return profile.audio_path if profile.status == "active" else None
