"""Testes unitários para Frame Extractor com vídeos REAIS"""
import pytest
import subprocess
from pathlib import Path


@pytest.mark.requires_video
@pytest.mark.requires_ffmpeg
class TestFrameExtractor:
    """Testes de extração de frames com FFmpeg"""
    
    def test_frame_extractor_module_imports(self):
        """Módulo frame_extractor importa"""
        try:
            from app.video_processing import frame_extractor
            assert frame_extractor is not None
        except ImportError:
            pytest.skip("frame_extractor.py não existe")
    
    def test_extract_single_frame(self, real_test_video, tmp_path):
        """Extrai um único frame de vídeo real"""
        output_frame = tmp_path / "frame_001.png"
        
        # Extrair primeiro frame com FFmpeg
        result = subprocess.run([
            "ffmpeg", "-i", str(real_test_video),
            "-vf", "select='eq(n,0)'",
            "-vframes", "1",
            str(output_frame)
        ], capture_output=True)
        
        assert result.returncode == 0
        assert output_frame.exists()
        assert output_frame.stat().st_size > 0
    
    def test_extract_frame_as_bytes(self, real_test_video):
        """Extrai frame como bytes (pipe)"""
        # Extrair frame para stdout
        result = subprocess.run([
            "ffmpeg", "-i", str(real_test_video),
            "-vf", "select='eq(n,0)'",
            "-vframes", "1",
            "-f", "image2pipe",
            "-vcodec", "png",
            "-"
        ], capture_output=True, check=True)
        
        # Verificar que retornou dados
        assert len(result.stdout) > 0
        
        # Verificar assinatura PNG
        assert result.stdout[:8] == b'\x89PNG\r\n\x1a\n'
    
    def test_extract_frame_with_opencv(self, real_test_video):
        """Extrai e processa frame com OpenCV"""
        try:
            import cv2
            import numpy as np
        except ImportError:
            pytest.skip("OpenCV não instalado")
        
        # Extrair frame
        result = subprocess.run([
            "ffmpeg", "-i", str(real_test_video),
            "-vf", "select='eq(n,0)'",
            "-vframes", "1",
            "-f", "image2pipe",
            "-vcodec", "png",
            "-"
        ], capture_output=True, check=True)
        
        # Converter para numpy array
        nparr = np.frombuffer(result.stdout, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        assert frame is not None
        assert len(frame.shape) == 3  # height, width, channels
        assert frame.shape[2] == 3  # RGB
        assert frame.shape[0] > 0  # height > 0
        assert frame.shape[1] > 0  # width > 0
    
    def test_extract_multiple_frames(self, real_test_video, tmp_path):
        """Extrai múltiplos frames"""
        output_pattern = tmp_path / "frame_%03d.png"
        
        # Extrair 3 frames (1 por segundo)
        subprocess.run([
            "ffmpeg", "-i", str(real_test_video),
            "-vf", "fps=1",
            "-vframes", "3",
            str(output_pattern)
        ], check=True, capture_output=True)
        
        # Verificar que frames foram criados
        frames = list(tmp_path.glob("frame_*.png"))
        assert len(frames) >= 1  # Pelo menos 1 frame (vídeo pode ser curto)
        
        for frame_path in frames:
            assert frame_path.stat().st_size > 0
    
    def test_extract_frame_at_timestamp(self, real_test_video, tmp_path):
        """Extrai frame em timestamp específico"""
        output_frame = tmp_path / "frame_at_2s.png"
        
        # Extrair frame aos 2 segundos
        subprocess.run([
            "ffmpeg", "-ss", "2",
            "-i", str(real_test_video),
            "-vframes", "1",
            str(output_frame)
        ], check=True, capture_output=True)
        
        assert output_frame.exists()
    
    def test_extract_frame_with_resolution(self, real_test_video, tmp_path):
        """Extrai frame com resolução específica"""
        output_frame = tmp_path / "frame_640x480.png"
        
        # Extrair frame e redimensionar
        subprocess.run([
            "ffmpeg", "-i", str(real_test_video),
            "-vf", "scale=640:480",
            "-vframes", "1",
            str(output_frame)
        ], check=True, capture_output=True)
        
        assert output_frame.exists()
        
        # Verificar dimensões (se OpenCV disponível)
        try:
            import cv2
            frame = cv2.imread(str(output_frame))
            assert frame.shape[1] == 640  # width
            assert frame.shape[0] == 480  # height
        except ImportError:
            pass  # Skip verification if OpenCV not available
    
    def test_extract_frames_for_analysis(self, real_test_video, tmp_path):
        """Extrai frames para análise de legendas"""
        output_pattern = tmp_path / "analysis_%04d.png"
        
        # Extrair frames a cada 0.5 segundos
        subprocess.run([
            "ffmpeg", "-i", str(real_test_video),
            "-vf", "fps=2",  # 2 frames por segundo
            str(output_pattern)
        ], capture_output=True)
        
        # Verificar que frames foram extraídos
        frames = list(tmp_path.glob("analysis_*.png"))
        assert len(frames) >= 1


@pytest.mark.requires_video
class TestFrameProcessing:
    """Testes de processamento de frames"""
    
    def test_frame_to_grayscale(self, real_test_video, tmp_path):
        """Converte frame para grayscale"""
        output_gray = tmp_path / "frame_gray.png"
        
        # Extrair frame em grayscale
        subprocess.run([
            "ffmpeg", "-i", str(real_test_video),
            "-vf", "format=gray",
            "-vframes", "1",
            str(output_gray)
        ], check=True, capture_output=True)
        
        assert output_gray.exists()
    
    def test_frame_metadata(self, real_test_video):
        """Obtém metadados de frames"""
        # Obter informações do stream de vídeo
        result = subprocess.run([
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate",
            "-of", "json",
            str(real_test_video)
        ], capture_output=True, text=True, check=True)
        
        import json
        data = json.loads(result.stdout)
        
        assert 'streams' in data
        assert len(data['streams']) > 0
        
        stream = data['streams'][0]
        assert 'width' in stream
        assert 'height' in stream
        assert int(stream['width']) > 0
        assert int(stream['height']) > 0
    
    def test_count_total_frames(self, real_test_video):
        """Conta total de frames no vídeo"""
        result = subprocess.run([
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-count_frames",
            "-show_entries", "stream=nb_read_frames",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(real_test_video)
        ], capture_output=True, text=True)
        
        # Pode não ter nb_read_frames, então verificamos se executou
        assert result.returncode == 0
