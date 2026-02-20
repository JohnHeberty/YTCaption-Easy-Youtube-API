# 📝 SPRINT 6 - SUBTITLE PROCESSING

**Status**: ⏳ Pendente  
**Prioridade**: 🟡 ALTA  
**Duração Estimada**: 4-5 horas  
**Pré-requisitos**: Sprint 0, 5

---

## 🎯 OBJETIVOS

1. ✅ Testar geração de arquivos .ass REAIS
2. ✅ Validar temporal tracker
3. ✅ Testar classificação de legendas
4. ✅ Validar formato .ass gerado

---

## 📁 ARQUIVOS

```
app/subtitle_processing/
├── ass_generator.py           # Gerador de .ass
├── temporal_tracker.py        # Tracking temporal
├── subtitle_classifier.py     # Classificador v1
├── subtitle_classifier_v2.py  # Classificador v2
├── subtitle_detector.py       # Detector (legado)
└── __init__.py
```

---

## 🧪 TESTES

```python
# tests/unit/subtitle_processing/test_ass_generator.py
import pytest
from pathlib import Path


class TestASSGenerator:
    """Testes de geração de .ass"""
    
    def test_generate_ass_file(self, tmp_path):
        """Gera arquivo .ass válido"""
        output = tmp_path / "subtitles.ass"
        
        # Dados de legenda
        subtitles = [
            {"start": 0.0, "end": 2.0, "text": "Hello World"},
            {"start": 2.5, "end": 4.5, "text": "Testing"},
        ]
        
        # Gerar manualmente (formato .ass)
        content = """[Script Info]
Title: Test Subtitle

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Black,22,&H00FFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,10,10,10,280,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        
        for sub in subtitles:
            start = self._format_time(sub['start'])
            end = self._format_time(sub['end'])
            content += f"Dialogue: 0,{start},{end},Default,,0,0,0,,{sub['text']}\n"
        
        output.write_text(content)
        
        # Validar
        assert output.exists()
        data = output.read_text()
        assert "[Script Info]" in data
        assert "[Events]" in data
        assert "Hello World" in data
    
    def _format_time(self, seconds):
        """Formata tempo para .ass"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centis = int((seconds % 1) * 100)
        return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"
    
    def test_ass_file_is_valid(self, tmp_path):
        """Arquivo .ass é válido"""
        ass_file = tmp_path / "valid.ass"
        ass_file.write_text("""[Script Info]
Title: Valid

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:02.00,Default,,0,0,0,,Test
""")
        
        content = ass_file.read_text()
        assert "Dialogue:" in content


# tests/unit/subtitle_processing/test_classifier.py
class TestSubtitleClassifier:
    """Testes de classificação"""
    
    def test_classifier_modules_import(self):
        """Módulos de classificação importam"""
        try:
            from app.subtitle_processing import subtitle_classifier
            assert subtitle_classifier is not None
        except ImportError:
            pytest.skip("classifier not found")
```

---

## 📋 IMPLEMENTAÇÃO

```bash
mkdir -p tests/unit/subtitle_processing
touch tests/unit/subtitle_processing/__init__.py
touch tests/unit/subtitle_processing/test_ass_generator.py
touch tests/unit/subtitle_processing/test_classifier.py

pytest tests/unit/subtitle_processing/ -v
```

---

## ✅ CRITÉRIOS

- [ ] Arquivos .ass válidos gerados
- [ ] Formato correto
- [ ] Cobertura > 85%

---

**Status**: ⏳ Pendente
