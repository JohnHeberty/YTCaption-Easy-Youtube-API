# ✅ Checklist de Validação em Produção

**Data**: 2026-02-20  
**Bug**: Exception Details Parameter Conflict  
**Status**: Correção deployada, aguardando validação em produção

---

## 🎯 Objetivo

Validar que a correção do bug de `details` funciona corretamente em produção com jobs reais.

---

## ✅ Pré-requisitos (Completos)

- [x] **Código corrigido** (3 camadas: base, parent, callers)
- [x] **Testes passando** (10/10 regression + 376/387 total)
- [x] **Build Docker successful** (9.7s)
- [x] **Deploy realizado** (containers healthy)
- [x] **Documentação atualizada** (CORRECAO_BUG_DETAILS_COMPLETA.md)

---

## 🧪 Cenários de Teste em Produção

### Cenário 1: Job Normal (Happy Path)
**Objetivo**: Validar que jobs normais ainda funcionam corretamente

- [ ] **Upload arquivo áudio** (.ogg, ~33s duration)
- [ ] **Criar job** via API POST /api/v1/jobs
- [ ] **Monitorar progresso**: 0% → 25% → 50% → 75% → 100%
- [ ] **Verificar status final**: `completed`
- [ ] **Validar outputs**: 
  - [ ] Video file gerado
  - [ ] Subtitles gerados
  - [ ] Thumbnails gerados

**Comando de teste**:
```bash
curl -X POST http://localhost:8004/api/v1/jobs \
  -F "audio_file=@test_audio_33s.ogg" \
  -F "config={...}"
```

---

### Cenário 2: Audio-Transcriber Indisponível (Bug Original)
**Objetivo**: Validar que o bug NÃO ocorre mais quando transcriber falha

- [ ] **Simular falha**: Parar container audio-transcriber
  ```bash
  docker stop ytcaption-audio-transcriber
  ```
- [ ] **Criar job** com arquivo áudio real
- [ ] **Esperar atingir 75%** (fase de transcrição)
- [ ] **Verificar erro esperado**: `TranscriberUnavailableException` (SEM TypeError)
- [ ] **Validar details no erro**:
  - [ ] Contém `service: "audio-transcriber"`
  - [ ] Contém reason da falha
  - [ ] NÃO contém TypeError sobre "multiple values"
- [ ] **Restart transcriber**: 
  ```bash
  docker start ytcaption-audio-transcriber
  ```

**Expected Error (CORRETO)**:
```json
{
  "error": "TranscriberUnavailableException",
  "message": "Audio transcriber unavailable: ...",
  "details": {
    "service": "audio-transcriber",
    "reason": "..."
  },
  "recoverable": true
}
```

**Old Error (BUG - NÃO deve mais acontecer)**:
```json
{
  "error": "TypeError",
  "message": "MakeVideoBaseException.__init__() got multiple values for keyword argument 'details'"
}
```

---

### Cenário 3: Timeout na Transcrição
**Objetivo**: Validar TranscriptionTimeoutException funciona corretamente

- [ ] **Configurar timeout baixo** (ex: 5s no .env)
- [ ] **Upload áudio longo** (>30s)
- [ ] **Criar job**
- [ ] **Esperar timeout**
- [ ] **Verificar erro esperado**: `TranscriptionTimeoutException`
- [ ] **Validar details**:
  - [ ] Contém `timeout_seconds`
  - [ ] Contém `job_id`
  - [ ] Contém `service: "audio-transcriber"`

---

## 📊 Métricas de Validação

### Logs
- [ ] **make-video logs**: Sem TypeError
- [ ] **audio-transcriber logs**: Sem erros não tratados
- [ ] **Celery logs**: Tasks executando normalmente

**Comando**:
```bash
docker logs -f ytcaption-make-video | grep -i "error\|exception"
```

### Redis (Job Status)
- [ ] Jobs com status corretos (`processing`, `completed`, `failed`)
- [ ] Progress atualizando (0% → 100%)
- [ ] Error details estruturados quando falhar

**Comando**:
```bash
redis-cli GET job:htRtccPHGyzJd8JSk2JcYB
```

### Health Checks
- [ ] Todas as APIs respondendo `/health`
- [ ] Containers em estado `healthy`

**Comando**:
```bash
curl http://localhost:8004/health
docker ps --filter "name=ytcaption" --format "{{.Names}}\t{{.Status}}"
```

---

## 🐛 Troubleshooting

### Se o bug AINDA ocorrer:

1. **Verificar versão deployada**:
   ```bash
   docker exec ytcaption-make-video python -c "from app.shared.exceptions_v2 import MakeVideoBaseException; import inspect; print(inspect.signature(MakeVideoBaseException.__init__))"
   ```
   - Deve conter `**kwargs` na assinatura

2. **Verificar código no container**:
   ```bash
   docker exec ytcaption-make-video cat /app/app/shared/exceptions_v2.py | grep -A 20 "class MakeVideoBaseException"
   ```

3. **Verificar api_client.py**:
   ```bash
   docker exec ytcaption-make-video grep -n "TranscriberUnavailableException" /app/app/api/api_client.py
   ```
   - NÃO deve haver `details=` nas chamadas (linhas 369, 425, 457)

---

## 📝 Registro de Testes

### Teste 1: [DATA/HORA]
- **Cenário**: _____________
- **Job ID**: _____________
- **Resultado**: ⬜ Pass / ⬜ Fail
- **Observações**: _____________

### Teste 2: [DATA/HORA]
- **Cenário**: _____________
- **Job ID**: _____________
- **Resultado**: ⬜ Pass / ⬜ Fail
- **Observações**: _____________

### Teste 3: [DATA/HORA]
- **Cenário**: _____________
- **Job ID**: _____________
- **Resultado**: ⬜ Pass / ⬜ Fail
- **Observações**: _____________

---

## ✅ Critérios de Aceitação

A correção será considerada 100% validada quando:

1. ✅ **Happy path funciona**: Job completo 0% → 100% sem erros
2. ✅ **Error handling correto**: TranscriberUnavailableException sem TypeError
3. ✅ **Details estruturados**: Todos os campos esperados presentes
4. ✅ **Sem regressões**: Jobs anteriormente estáveis ainda funcionam
5. ✅ **Logs limpos**: Sem traces de TypeError "multiple values"

---

## 🚀 Próximos Passos Após Validação

- [ ] Marcar issue como resolvida
- [ ] Atualizar changelog
- [ ] Deploy em staging/produção
- [ ] Monitoramento por 24h
- [ ] Fechar ticket

---

**Responsável**: _____________  
**Data início testes**: 2026-02-20  
**Data conclusão**: _____________  
**Status final**: ⬜ Aprovado / ⬜ Reprovado / ⬜ Em andamento
