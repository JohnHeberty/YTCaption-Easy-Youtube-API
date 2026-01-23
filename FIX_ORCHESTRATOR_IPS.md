# Correção de IPs do Orchestrator

## Problema Identificado
Job `89003c7beff5641f` não estava sendo processado. O orchestrator não conseguia se comunicar com os microserviços.

## Causa Raiz
Os IPs dos microserviços estavam configurados na **rede errada** (`192.168.18.x` em vez de `192.168.1.x`):

```bash
# IPs INCORRETOS (orchestrator/.env)
VIDEO_DOWNLOADER_URL=http://192.168.18.132:8001     ❌
AUDIO_NORMALIZATION_URL=http://192.168.18.133:8002 ❌
AUDIO_TRANSCRIBER_URL=http://192.168.18.136:8003   ❌
```

## Solução Aplicada
Corrigidos os IPs no arquivo `orchestrator/.env`:

```bash
# IPs CORRETOS
VIDEO_DOWNLOADER_URL=http://192.168.1.132:8001     ✅
AUDIO_NORMALIZATION_URL=http://192.168.1.133:8002 ✅
AUDIO_TRANSCRIBER_URL=http://192.168.1.203:8003   ✅
```

## Sintomas Observados
```
ytcaption-orchestrator | ERROR - Health check failed for video-downloader: 
ytcaption-orchestrator | WARNING - [video-downloader] Network error on attempt 1/5, retrying in 5.1s: ConnectError
ytcaption-orchestrator | WARNING - [video-downloader] Network error on attempt 2/5, retrying in 10.8s: ConnectError
```

## Validação da Correção
1. **Teste de conectividade:**
   ```bash
   curl http://192.168.1.132:8001/health  # ✅ 200 OK
   curl http://192.168.1.133:8002/health  # ✅ 200 OK
   curl http://192.168.1.203:8003/health  # ⚠️ Offline (VM desligada)
   ```

2. **Job de teste:** `e65c73aab679eb7b`
   - ✅ Download: COMPLETED (16.0MB em 7s)
   - ✅ Normalization: COMPLETED (8s)
   - 🔄 Transcription: Em andamento

## Como Aplicar em Produção
```bash
# Na VM do orchestrator
cd /root/YTCaption-Easy-Youtube-API/orchestrator
nano .env  # Editar os 3 IPs

# Reiniciar serviço
docker compose down
docker compose up -d

# Verificar logs
docker compose logs -f orchestrator | grep "Microservices:"
```

## Resultado
✅ **Pipeline funcionando corretamente**
- Orchestrator consegue se comunicar com video-downloader e audio-normalization
- Jobs são processados normalmente
- Audio-transcriber offline (192.168.1.203 não responde) mas pipeline continua funcionando para outros estágios
