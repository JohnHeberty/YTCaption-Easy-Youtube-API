# Progress (Updated: 2025-11-26)

## Done

- Sprint 1: Análise modelo pt-BR (364 tensors, 2545 tokens)
- Sprint 2: Docker setup com F5-TTS repo install
- Sprint 3.1: F5TTSModelLoader custom loader
- Lazy loading (99.8% VRAM reduction: 5MB → 1.27GB)
- Whisper CPU config (saves ~1GB GPU VRAM)
- TTS pipeline implementation (90%)
- Vocos vocoder integration (standalone package)
- ✅ CRITICAL FIX: audio_path → reference_audio_path (4 locations)
- ✅ Code audit complete (AUDITORIA-ERROS.md created)
- ✅ Containers rebuilt successfully

## Doing

- Testing dubbing end-to-end with fix applied
- Implementing text normalization (num2words for pt-BR)

## Next

- Validate audio output quality (MOS scores)
- Complete Sprint 3.2 (final 10% - end-to-end testing)
- Performance profiling (latency, VRAM under load)
- Implement dynamic speed parameter from job.params
- Sprint 4: Automated testing & optimization
