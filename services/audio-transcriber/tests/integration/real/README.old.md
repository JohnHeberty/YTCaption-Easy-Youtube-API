# 🌐 Real Integration Tests

⚠️ **ATENÇÃO**: Estes testes usam APIs e serviços REAIS externos!

## ⚠️ Avisos Importantes

- 🐌 **LENTOS**: Podem levar minutos para executar
- 🌐 **REQUEREM REDE**: Precisam de conexão com internet
- 💰 **PODEM TER CUSTO**: Alguns serviços podem cobrar
- 🔐 **REQUEREM CREDENCIAIS**: Necessitam de API keys reais
- 🔄 **NÃO IDEMPOTENTES**: Podem criar/modificar dados reais

## 🚫 Quando NÃO executar

- ❌ Em CI/CD (exceto branch principal)
- ❌ Durante desenvolvimento regular
- ❌ Em ambientes sem credenciais
- ❌ Quando serviços externos estão indisponíveis

## ✅ Quando executar

- ✅ Validação final antes de deploy
- ✅ Testes de integração em staging
- ✅ Debugging de problemas com APIs reais
- ✅ Validação de mudanças em integrações externas

## 🚀 Como executar

### Executar apenas testes reais
```bash
pytest tests/integration/real/ -v -m real
```

### Executar com output detalhado
```bash
pytest tests/integration/real/ -vv -s -m real
```

### Executar teste específico
```bash
pytest tests/integration/real/test_real_whisper_api.py::test_real_transcription -v
```

### Pular testes reais (padrão)
```bash
# Executar todos os testes EXCETO os reais
pytest tests/ -v -m "not real"
```

## 🔧 Configuração

### Variáveis de ambiente necessárias

```bash
# Opcionalmente, se usar API externa
export OPENAI_API_KEY="sk-..."

# Configurações de rede
export REQUEST_TIMEOUT=120  # Timeout maior para APIs lentas
```

### Pré-requisitos

1. **Serviços rodando**:
   - Redis em localhost:6379
   - Celery workers ativos (se testando tasks)

2. **Modelos baixados**:
   - faster-whisper models em `./models/`

3. **Internet estável**:
   - Baixa latência para APIs

## 📝 Testes Disponíveis

### `test_real_whisper_api.py`

Testa modelo Faster-Whisper real com áudio de teste.

```python
@pytest.mark.real
@pytest.mark.slow
def test_real_whisper_transcription():
    """Testa transcrição com modelo Whisper real."""
    # Usa arquivo TEST-.ogg real
    # Carrega modelo faster-whisper
    # Executa transcrição completa
    # Valida word timestamps
```

**Duração**: ~30-60 segundos  
**Requer**: Modelo faster-whisper baixado

## 🎯 Critérios de Sucesso

Testes reais devem validar:

1. ✅ **Conectividade**: APIs acessíveis
2. ✅ **Autenticação**: Credenciais funcionando
3. ✅ **Formato**: Responses no formato esperado
4. ✅ **Performance**: Dentro de timeouts aceitáveis
5. ✅ **Funcionalidade**: Resultados corretos e completos

## 🐛 Debugging

### Se testes falharem

1. **Verificar conectividade**:
   ```bash
   curl -I https://api.example.com
   ```

2. **Validar credenciais**:
   ```bash
   echo $OPENAI_API_KEY  # Deve estar configurada
   ```

3. **Verificar logs**:
   ```bash
   tail -f logs/audio-transcriber.json
   ```

4. **Executar com debug**:
   ```bash
   pytest tests/integration/real/ -vv -s --pdb
   ```

## 📊 Métricas Esperadas

| Teste | Duração | Taxa de Sucesso |
|-------|---------|-----------------|
| Whisper Real | ~30-60s | > 95% |
| API Externa | ~10-30s | > 90% |
| Pipeline Completo | ~60-120s | > 85% |

## 🔒 Segurança

- ⚠️ **NUNCA commite credenciais** nos testes
- ✅ Use variáveis de ambiente
- ✅ Use dotenv para desenvolvimento local
- ✅ Rotacione keys periodicamente
- ✅ Revogue keys se expostas

## 📝 Adicionando Novos Testes

Template para novo teste real:

```python
import pytest

@pytest.mark.real
@pytest.mark.slow
def test_my_real_integration():
    """
    Descrição: O que este teste valida
    
    Pré-requisitos:
    - Serviço X rodando
    - Credenciais Y configuradas
    
    Duração esperada: ~Xs
    """
    # 1. Setup
    # ...
    
    # 2. Executar ação real
    # ...
    
    # 3. Validar resultado
    # ...
```

Sempre adicione:
- ✅ Marker `@pytest.mark.real`
- ✅ Marker `@pytest.mark.slow` se > 5s
- ✅ Docstring detalhada
- ✅ Timeouts apropriados
- ✅ Cleanup de recursos

## ⚡ Performance

Para testes mais rápidos:
- Use modelos menores (`tiny`, `base`)
- Reduza áudio de teste (< 10s)
- Paralelização: `pytest -n auto` (com cuidado!)
- Cache de modelos
- Mock de partes não críticas

---

**Lembre-se**: Testes reais são valiosos mas caros. Use com sabedoria! 💡
