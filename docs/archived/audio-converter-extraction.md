# AudioConverter Extraction — processor.py SRP (MELHORE 1.2)

## Problema resolvido
`processor.py` continha ~180 linhas de lógica de conversão e validação de áudio (`_has_audio_stream`, `_convert_to_wav`) violando o Single Responsibility Principle. O método era autocontido, com dependência apenas no settings dict.

## Arquivos alterados
- **Criado:** `app/shared/audio_converter.py` (~130 linhas) — funções standalone `has_audio_stream()` e `convert_to_wav(input_path, settings)` que realizam detecção de stream via ffprobe + conversão ffmpeg para WAV 16kHz mono pcm_s16le.
- **Modificado:** `app/services/processor.py` — removidos `_has_audio_stream()` (lines 908-967) e `_convert_to_wav()` (lines 969-1087). Call site na linha ~453 atualizado para usar função importada.

## Como validar
```bash
# AST parse local
python3 -c "import ast; ast.parse(open('services/se4-audio-transcriber/app/services/processor.py').read())"
python3 -c "import ast; ast.parse(open('services/se4-audio-transcriber/app/shared/audio_converter.py').read())"

# Import no container Docker
docker exec ytcaption-se4-audio-transcriber-api python3 -c "from app.shared.audio_converter import convert_to_wav, has_audio_stream; print('OK')"
```

## Riscos e observações
- Funções são standalone (não dependem de estado da classe), tornando-as testáveis isoladamente.
- `convert_to_wav` importa `AudioTranscriptionException` internamente para evitar circular imports.
- Settings dict é passado explicitamente como argumento, removendo acoplamento implícito ao processador.
