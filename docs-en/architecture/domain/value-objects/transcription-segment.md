# TranscriptionSegment Value Object

Value Object que representa um segmento de transcrição.

---

## Visão Geral

`TranscriptionSegment` é um **Value Object** imutável que representa:
- Texto transcrito
- Timestamp de início (segundos)
- Timestamp de fim (segundos)
- Formatação para SRT/VTT

**Arquivo**: `src/domain/value_objects/transcription_segment.py`

---

## Estrutura

```python
@dataclass(frozen=True)  # Imutável
class TranscriptionSegment:
    text: str    # Texto transcrito
    start: float # Timestamp inicial (segundos)
    end: float   # Timestamp final (segundos)
```

---

## Propriedades

### `duration` (readonly)
Retorna a duração do segmento em segundos.

```python
segment = TranscriptionSegment(
    text="Hello world",
    start=1.5,
    end=3.8
)
print(segment.duration)  # 2.3
```

---

## Validação

O `__post_init__` valida:

```python
# ✅ Válido
segment = TranscriptionSegment("Hello", start=0, end=2.5)

# ❌ Inválido: start negativo
TranscriptionSegment("Hello", start=-1, end=2)  # ValueError

# ❌ Inválido: end < start
TranscriptionSegment("Hello", start=5, end=3)  # ValueError

# ❌ Inválido: texto vazio
TranscriptionSegment("", start=0, end=2)  # ValueError
```

---

## Métodos de Formatação

### `to_srt_format(index: int) -> str`
Formata para SubRip (SRT) - usa **vírgula** como separador decimal.

```python
segment = TranscriptionSegment("Hello world", start=1.5, end=3.8)
print(segment.to_srt_format(1))

# Output:
# 1
# 00:00:01,500 --> 00:00:03,800
# Hello world
```

### `to_vtt_format() -> str`
Formata para WebVTT - usa **ponto** como separador decimal.

```python
segment = TranscriptionSegment("Hello world", start=1.5, end=3.8)
print(segment.to_vtt_format())

# Output:
# 00:00:01.500 --> 00:00:03.800
# Hello world
```

---

## Formato de Timestamp

Ambos os métodos usam `HH:MM:SS,mmm` (SRT) ou `HH:MM:SS.mmm` (VTT):

```python
# Exemplos:
0.0    → 00:00:00,000
1.5    → 00:00:01,500
65.250 → 00:01:05,250
3661.5 → 01:01:01,500
```

---

## Exemplo Completo

```python
from src.domain.value_objects import TranscriptionSegment

# Criar segmentos
segments = [
    TranscriptionSegment("Never gonna give you up", start=0.0, end=2.5),
    TranscriptionSegment("Never gonna let you down", start=2.5, end=5.0),
    TranscriptionSegment("Never gonna run around", start=5.0, end=7.8),
]

# Exportar para SRT
srt_content = "\n\n".join(
    seg.to_srt_format(i+1) for i, seg in enumerate(segments)
)
print(srt_content)

# Exportar para VTT
vtt_content = "WEBVTT\n\n" + "\n\n".join(
    seg.to_vtt_format() for seg in segments
)
print(vtt_content)

# Calcular duração total
total_duration = sum(seg.duration for seg in segments)
print(f"Duração: {total_duration:.2f}s")  # 7.80s
```

---

## Regras de Negócio

1. **Imutabilidade**: `frozen=True` impede modificações
2. **Timestamps Positivos**: `start >= 0`
3. **Ordem Temporal**: `end >= start`
4. **Texto Obrigatório**: Não pode ser vazio
5. **Formato Decimal**: 3 casas decimais (milissegundos)

---

## Testes

```python
def test_segment_creation():
    segment = TranscriptionSegment("Hello", start=1.0, end=3.0)
    assert segment.text == "Hello"
    assert segment.duration == 2.0

def test_segment_validation_negative_start():
    with pytest.raises(ValueError):
        TranscriptionSegment("Hello", start=-1, end=2)

def test_segment_validation_end_before_start():
    with pytest.raises(ValueError):
        TranscriptionSegment("Hello", start=5, end=3)

def test_segment_validation_empty_text():
    with pytest.raises(ValueError):
        TranscriptionSegment("", start=0, end=2)

def test_segment_srt_format():
    segment = TranscriptionSegment("Hello", start=1.5, end=3.8)
    srt = segment.to_srt_format(1)
    assert "1\n" in srt
    assert "00:00:01,500 --> 00:00:03,800" in srt
    assert "Hello" in srt

def test_segment_vtt_format():
    segment = TranscriptionSegment("Hello", start=1.5, end=3.8)
    vtt = segment.to_vtt_format()
    assert "00:00:01.500 --> 00:00:03.800" in vtt
    assert "Hello" in vtt

def test_segment_immutable():
    segment = TranscriptionSegment("Hello", start=0, end=2)
    with pytest.raises(FrozenInstanceError):
        segment.text = "Goodbye"
```

---

[⬅️ Voltar](../README.md)

**Versão**: 3.0.0