# 🔧 SPRINT 7 - SERVICES

**Status**: ⏳ Pendente  
**Prioridade**: 🟡 ALTA  
**Duração Estimada**: 4-5 horas  
**Pré-requisitos**: Sprint 1, 3, 4

---

## 🎯 OBJETIVOS

1. ✅ Testar VideoBuilder com assets reais
2. ✅ Validar crop de vídeo para 9:16
3. ✅ Testar VideoStatusStore com SQLite real
4. ✅ Validar persistência de dados

---

## 📁 ARQUIVOS

```
app/services/
├── video_builder.py          # Construtor de vídeo
├── video_status_factory.py   # Factory de status
└── [outros serviços]
```

---

## 🧪 TESTES

```python
# tests/integration/services/test_video_builder.py
import pytest
import subprocess
from pathlib import Path


@pytest.mark.requires_video
@pytest.mark.requires_audio
@pytest.mark.requires_ffmpeg
@pytest.mark.slow
class TestVideoBuilder:
    """Testes com assets REAIS"""
    
    def test_crop_video_to_9_16(self, real_test_video, tmp_path):
        """Crop de vídeo para 9:16"""
        output = tmp_path / "cropped.mp4"
        
        # Crop com FFmpeg
        subprocess.run([
            "ffmpeg", "-i", str(real_test_video),
            "-vf", "crop=ih*9/16:ih",  # Crop para 9:16
            "-y", str(output)
        ], check=True, capture_output=True)
        
        assert output.exists()
        
        # Verificar aspect ratio
        result = subprocess.run([
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0", str(output)
        ], capture_output=True, text=True, check=True)
        
        width, height = map(int, result.stdout.strip().split(','))
        ratio = height / width
        
        # 9:16 = 1.777
        assert abs(ratio - (16/9)) < 0.1
    
    def test_merge_video_audio_subtitles(
        self, 
        real_test_video, 
        real_test_audio, 
        sample_ass_file, 
        tmp_path
    ):
        """Merge de vídeo + áudio + legendas"""
        output = tmp_path / "final.mp4"
        
        # Merge com FFmpeg
        subprocess.run([
            "ffmpeg", 
            "-i", str(real_test_video),
            "-i", str(real_test_audio),
            "-vf", f"ass={sample_ass_file}",
            "-map", "0:v", "-map", "1:a",
            "-c:v", "libx264", "-c:a", "aac",
            "-y", str(output)
        ], check=True, capture_output=True)
        
        assert output.exists()
        assert output.stat().st_size > 0


# tests/integration/services/test_video_status.py
@pytest.mark.integration
class TestVideoStatusStore:
    """Testes com SQLite REAL"""
    
    def test_store_approved_video(self, tmp_path):
        """Armazena vídeo aprovado"""
        import sqlite3
        
        db_path = tmp_path / "status.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Criar tabela
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS approved_videos (
                video_id TEXT PRIMARY KEY,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Inserir
        video_id = "test_001"
        cursor.execute(
            "INSERT INTO approved_videos (video_id) VALUES (?)",
            (video_id,)
        )
        conn.commit()
        
        # Verificar
        cursor.execute(
            "SELECT video_id FROM approved_videos WHERE video_id = ?",
            (video_id,)
        )
        result = cursor.fetchone()
        
        assert result is not None
        assert result[0] == video_id
        
        conn.close()
    
    def test_store_rejected_video(self, tmp_path):
        """Armazena vídeo rejeitado"""
        import sqlite3
        
        db_path = tmp_path / "status.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rejected_videos (
                video_id TEXT PRIMARY KEY,
                reason TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        video_id = "test_002"
        reason = "has_subtitles"
        
        cursor.execute(
            "INSERT INTO rejected_videos (video_id, reason) VALUES (?, ?)",
            (video_id, reason)
        )
        conn.commit()
        
        # Verificar
        cursor.execute(
            "SELECT reason FROM rejected_videos WHERE video_id = ?",
            (video_id,)
        )
        result = cursor.fetchone()
        
        assert result[0] == reason
        
        conn.close()
```

---

## 📋 IMPLEMENTAÇÃO

```bash
mkdir -p tests/integration/services
touch tests/integration/services/__init__.py
touch tests/integration/services/test_video_builder.py
touch tests/integration/services/test_video_status.py

pytest tests/integration/services/ -v -m "requires_video and requires_ffmpeg"
```

---

## ✅ CRITÉRIOS

- [ ] VideoBuilder funciona
- [ ] Crop validado
- [ ] Status store persiste
- [ ] Cobertura > 85%

---

**Status**: ⏳ Pendente
