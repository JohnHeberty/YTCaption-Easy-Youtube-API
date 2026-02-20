"""
Testes para Video Compatibility Fixer

Valida:
- Detecção de especificações
- Conversão de vídeos incompatíveis
- Garantia de compatibilidade
- Re-processamento de diretórios
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from app.services.video_compatibility_fixer import (
    VideoCompatibilityFixer,
    VideoSpec
)
from app.shared.exceptions_v2 import (
    VideoNotFoundException,
    FFmpegFailedException
)


@pytest.fixture
def fixer():
    """Cria VideoCompatibilityFixer para testes."""
    return VideoCompatibilityFixer()


@pytest.fixture
def video_spec_1080p():
    """Especificação de vídeo 1080p @ 30fps."""
    return VideoSpec(
        width=1080,
        height=1920,
        fps=30.0,
        codec="h264",
        audio_codec="aac",
        audio_sample_rate=48000
    )


@pytest.fixture
def video_spec_720p():
    """Especificação de vídeo 720p @ 30fps."""
    return VideoSpec(
        width=720,
        height=1280,
        fps=30.0,
        codec="h264",
        audio_codec="aac",
        audio_sample_rate=48000
    )


class TestVideoSpec:
    """Testa VideoSpec dataclass."""
    
    def test_resolution_property(self, video_spec_1080p):
        """Testa propriedade resolution."""
        assert video_spec_1080p.resolution == "1080x1920"
    
    def test_aspect_ratio_9_16(self, video_spec_1080p):
        """Testa cálculo de aspect ratio para 9:16."""
        assert video_spec_1080p.aspect_ratio == "9:16"
    
    def test_aspect_ratio_16_9(self):
        """Testa cálculo de aspect ratio para 16:9."""
        spec = VideoSpec(
            width=1920, height=1080, fps=30.0,
            codec="h264", audio_codec="aac", audio_sample_rate=48000
        )
        assert spec.aspect_ratio == "16:9"


class TestVideoCompatibilityFixer:
    """Testa VideoCompatibilityFixer."""
    
    @pytest.mark.asyncio
    async def test_single_video_no_conversion_needed(self, fixer, tmp_path):
        """Se só tem 1 vídeo, não precisa compatibilização."""
        video_file = tmp_path / "video1.mp4"
        video_file.touch()
        
        result = await fixer.ensure_compatibility(
            video_paths=[video_file],
            output_dir=tmp_path / "output",
            target_spec=None
        )
        
        assert len(result) == 1
        assert result[0] == video_file  # Mesmo arquivo, sem conversão
    
    @pytest.mark.asyncio
    async def test_video_not_found_raises_exception(self, fixer, tmp_path):
        """Se vídeo não existe, lança VideoNotFoundException."""
        non_existent = tmp_path / "non_existent.mp4"
        
        with pytest.raises(VideoNotFoundException):
            await fixer.ensure_compatibility(
                video_paths=[non_existent],
                output_dir=tmp_path / "output"
            )
    
    @pytest.mark.asyncio
    async def test_fps_parsing(self, fixer):
        """Testa parse de FPS em diferentes formatos."""
        assert fixer._parse_fps("30/1") == 30.0
        assert fixer._parse_fps("60/1") == 60.0
        assert fixer._parse_fps("30.0") == 30.0
        assert fixer._parse_fps("29.97") == 29.97
        assert fixer._parse_fps("invalid") == 30.0  # Fallback
    
    def test_compatibility_check_same_specs(
        self,
        fixer,
        video_spec_1080p
    ):
        """Vídeos com mesmas specs são compatíveis."""
        spec2 = VideoSpec(
            width=1080, height=1920, fps=30.0,
            codec="h264", audio_codec="aac", audio_sample_rate=48000
        )
        
        assert fixer._is_compatible(spec2, video_spec_1080p)
    
    def test_compatibility_check_different_resolution(
        self,
        fixer,
        video_spec_1080p,
        video_spec_720p
    ):
        """Vídeos com resoluções diferentes são incompatíveis."""
        assert not fixer._is_compatible(video_spec_720p, video_spec_1080p)
    
    def test_compatibility_check_fps_tolerance(self, fixer):
        """FPS é compatível dentro de tolerância (±0.5)."""
        spec1 = VideoSpec(
            width=1080, height=1920, fps=30.0,
            codec="h264", audio_codec="aac", audio_sample_rate=48000
        )
        spec2 = VideoSpec(
            width=1080, height=1920, fps=30.3,
            codec="h264", audio_codec="aac", audio_sample_rate=48000
        )
        
        # Dentro da tolerância
        assert fixer._is_compatible(spec2, spec1)
        
        # Fora da tolerância
        spec3 = VideoSpec(
            width=1080, height=1920, fps=25.0,
            codec="h264", audio_codec="aac", audio_sample_rate=48000
        )
        assert not fixer._is_compatible(spec3, spec1)
    
    @pytest.mark.asyncio
    async def test_detect_specs_default_on_error(self, fixer, tmp_path):
        """Se detecção falhar, usa specs padrão."""
        video_file = tmp_path / "corrupt.mp4"
        video_file.touch()
        
        # Arquivo inválido vai causar erro no ffprobe
        spec = await fixer._detect_specs(video_file)
        
        # Deve retornar specs padrão
        assert spec.width == VideoCompatibilityFixer.DEFAULT_SPECS.width
        assert spec.height == VideoCompatibilityFixer.DEFAULT_SPECS.height
    
    @pytest.mark.asyncio
    async def test_determine_target_spec_uses_env_default(
        self,
        fixer,
        video_spec_1080p,
        video_spec_720p
    ):
        """Target spec deve usar padrão do .env (720p HD)."""
        specs_map = {
            Path("video1.mp4"): video_spec_1080p,
            Path("video2.mp4"): video_spec_720p
        }
        video_paths = [Path("video1.mp4"), Path("video2.mp4")]
        
        target = fixer._determine_target_spec(specs_map, video_paths)
        
        # Deve usar resolução padrão do .env (720p = 1280x720)
        assert target.width == 1280
        assert target.height == 720
    
    @pytest.mark.asyncio
    async def test_ensure_compatibility_with_mock_conversion(
        self,
        fixer,
        tmp_path
    ):
        """Testa fluxo completo com conversão in-place mockada."""
        # Criar arquivos de teste
        video1 = tmp_path / "video1.mp4"
        video2 = tmp_path / "video2.mp4"
        video1.touch()
        video2.touch()
        
        # Mock de detecção de specs: um 720p (compatível), outro 480p (precisa conversão)
        spec1 = VideoSpec(
            width=1280, height=720, fps=30.0,
            codec="h264", audio_codec="aac", audio_sample_rate=48000
        )
        spec2 = VideoSpec(
            width=640, height=480, fps=30.0,
            codec="h264", audio_codec="aac", audio_sample_rate=48000
        )
        
        async def mock_detect(path):
            if path == video1:
                return spec1
            else:
                return spec2
        
        # Mock de conversão in-place
        async def mock_convert_and_replace(original_path, temp_path, target_spec):
            # Simular conversão: criar temp e sobrescrever original
            temp_path.touch()
            import shutil
            shutil.move(str(temp_path), str(original_path))
        
        with patch.object(fixer, '_detect_specs', side_effect=mock_detect):
            with patch.object(fixer, '_convert_and_replace', side_effect=mock_convert_and_replace):
                result = await fixer.ensure_compatibility(
                    video_paths=[video1, video2],
                    output_dir=None,  # Não usado mais
                    target_spec=None
                )
                
                # Deve retornar 2 vídeos (mesmos paths, convertidos in-place)
                assert len(result) == 2
                
                # MESMOS arquivos originais (sobrescritos)
                assert result[0] == video1
                assert result[1] == video2


class TestReprocessingWorkflow:
    """Testa re-processamento de vídeos existentes."""
    
    @pytest.mark.asyncio
    async def test_reprocess_empty_directory(self, fixer, tmp_path):
        """Re-processar diretório vazio retorna 0 processados."""
        result = await fixer.reprocess_incompatible_videos(
            video_dir=tmp_path,
            pattern="*.mp4"
        )
        
        assert result["processed"] == 0
        assert result["converted"] == 0
    
    @pytest.mark.asyncio
    async def test_reprocess_with_videos(self, fixer, tmp_path):
        """Re-processar diretório com vídeos (conversão in-place)."""
        # Criar alguns vídeos de teste
        (tmp_path / "video1.mp4").touch()
        (tmp_path / "video2.mp4").touch()
        
        # Mock de ensure_compatibility
        async def mock_ensure(video_paths, output_dir, **kwargs):
            # Simular conversão in-place: retorna MESMAS paths
            return video_paths
        
        # Mock de _detect_specs e _is_compatible
        spec_compatible = VideoSpec(
            width=1280, height=720, fps=30.0,
            codec="h264", audio_codec="aac", audio_sample_rate=48000
        )
        spec_incompatible = VideoSpec(
            width=640, height=480, fps=30.0,
            codec="h264", audio_codec="aac", audio_sample_rate=48000
        )
        
        call_count = [0]
        async def mock_detect(path):
            call_count[0] += 1
            # Primeiro vídeo compatível, segundo incompatível
            return spec_compatible if call_count[0] == 1 else spec_incompatible
        
        with patch.object(fixer, 'ensure_compatibility', side_effect=mock_ensure):
            with patch.object(fixer, '_detect_specs', side_effect=mock_detect):
                result = await fixer.reprocess_incompatible_videos(
                    video_dir=tmp_path,
                    pattern="*.mp4"
                )
                
                assert result["processed"] == 2
                assert result["converted"] == 1  # Apenas 1 incompatível
                assert result["already_compatible"] == 1
                assert result["errors"] == 0
    
    @pytest.mark.asyncio
    async def test_reprocess_handles_errors(self, fixer, tmp_path):
        """Re-processamento trata erros gracefully."""
        (tmp_path / "video1.mp4").touch()
        
        # Mock de ensure_compatibility que falha
        async def mock_ensure_fail(**kwargs):
            raise Exception("Conversion failed")
        
        with patch.object(
            fixer,
            'ensure_compatibility',
            side_effect=mock_ensure_fail
        ):
            result = await fixer.reprocess_incompatible_videos(
                video_dir=tmp_path,
                pattern="*.mp4"
            )
            
            assert result["errors"] == 1
            assert "error_message" in result


class TestIntegrationScenarios:
    """Testes de cenários de integração."""
    
    @pytest.mark.asyncio
    async def test_mixed_resolutions_get_compatible(
        self,
        fixer,
        tmp_path
    ):
        """Vídeos com resoluções mistas são compatibilizados (in-place)."""
        # Criar vídeos de teste
        videos = [tmp_path / f"video{i}.mp4" for i in range(3)]
        for v in videos:
            v.touch()
        
        # Mock: primeiro vídeo 720p (compatível), outros são 1080p e 480p (precisam conversão)
        specs = [
            VideoSpec(1280, 720, 30.0, "h264", "aac", 48000),  # 720p - compatível
            VideoSpec(1920, 1080, 30.0, "h264", "aac", 48000),  # 1080p - downscale para 720p
            VideoSpec(640, 480, 30.0, "h264", "aac", 48000)  # 480p - upscale para 720p
        ]
        
        async def mock_detect(path):
            idx = videos.index(path)
            return specs[idx]
        
        async def mock_convert_and_replace(original_path, temp_path, target_spec):
            # Simular conversão in-place
            temp_path.touch()
            import shutil
            shutil.move(str(temp_path), str(original_path))
        
        with patch.object(fixer, '_detect_specs', side_effect=mock_detect):
            with patch.object(fixer, '_convert_and_replace', side_effect=mock_convert_and_replace):
                result = await fixer.ensure_compatibility(
                    video_paths=videos,
                    output_dir=None  # Conversão in-place
                )
                
                # Todos os 3 vídeos retornados (mesmos paths, convertidos no lugar)
                assert len(result) == 3
                
                # TODOS os vídeos mantêm seus paths originais
                assert result[0] == videos[0]
                assert result[1] == videos[1]
                assert result[2] == videos[2]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
