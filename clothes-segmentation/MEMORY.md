# MEMORY.md - Memória Persistente do Projeto

## 1. Meta do Projeto
Substituir `frozen.h5` do Fashion-AI-segmentation (ruim) por um modelo melhor de segmentação de roupas, criando uma API unificada.

**Status atual**: API FastAPI com Grounded-SAM-2 funcionando. Todos os 3 candidatos testados — apenas Grounded-SAM-2 viável.

## 2. Decisões Arquiteturais

| Decisão | Razão | Data |
|---------|-------|------|
| Grounded-SAM-2 como solução final | Único modelo que detectou roupas nas imagens de teste | 27/05 |
| API FastAPI com ThreadPoolExecutor | GroundingDINO+SAM2 bloqueiam event loop; executor resolve | 27/05 |
| numpy downgrade (1.26.4) | h5py 3.11.0 incompatível com numpy 2.x | 27/05 |
| Porta 8001 | Porta 8000 ocupada por outro serviço | 27/05 |
| Segformer descartado | Detectou apenas Face/Hair, ZERO roupas | 27/05 |
| Virtual_Try_on descartado | U2NET detectou 100% background, ZERO roupas | 27/05 |

### Alternativas descartadas
- **frozen.h5 original** - Segmentação péssima, motivo do projeto
- **Segformer (TF.js)** - Modelo treinado em dataset diferente; não detecta roupas em imagens reais
- **Virtual_Try_on U2NET** - Mesmo problema + propósito diferente (virtual try-on, não segmentação)

## 3. Estado dos Projetos

| Projeto | Status | Problema Principal | Decisão |
|---------|--------|-------------------|---------|
| segformer-clothes-tfjs | ❌ REPROVADO | Detectou apenas Face e Hair | Descartado |
| Virtual_Try_on_FashionGenAi | ❌ REPROVADO | 100% background, ZERO roupas | Descartado |
| Grounded-SAM-2-clothes-extraction | ✅ SELECIDO + API funcionando | Complexo deploy (5+ repos), mas funciona em CPU | Solução final |

## 4. Descobertas Críticas

### Ambiente
- **Sem GPU CUDA** - qualquer projeto que dependa de GPU vai ser lento ou falhar
- **Python 3.12.7** - usar `python`, NUNCA `python3` (alias quebrado no Windows)
- **Node.js v24.15.0** - PATH precisa ser fixado a cada sessão via `$env:Path = ...`
- **OneDrive sync deleta arquivos** - nunca salvar output na Área de Trabalho, usar `C:\Temp`
- **numpy 2.x incompatível com h5py** — downgrade para numpy<2 obrigatório

### API FastAPI (api/)
- `server.py` — FastAPI com `/segment` POST e `/health` GET
- `segmentor.py` — ClothesSegmentor class (GroundingDINO + SAM2)
- `run_server.bat` — Launch script (porta 8001)
- **Problema resolvido**: Event loop bloqueado → ThreadPoolExecutor com `run_in_executor`
- **Startup**: ~36s para carregar modelos

### Resultados API HTTP
| Imagem | Status | Objetos | Classes |
|--------|--------|---------|---------|
| 1-TEST.jpg | ✅ 200 | 27 | hat(10), pants(3), dress(3), blouse(3), shirt(2), boots(2), shoes(1), sunglasses(1), handbag(1), skirt(1) |
| 2-TEST.jpg | ✅ 200 | 6 | blouse(3), sunglasses(1), jacket(1), hat(1) |

### Lições Aprendidas
- **27/05 - Caminhos absolutos**: O Write tool interpretou `.opencode/memory/` como `C:\.opencode\memory\` (raiz do C:) em vez de dentro do projeto. SEMPRE usar caminho completo.
- **27/05 - Output dentro de imgs/**: Pasta `output/` deve ficar dentro de `imgs/output/`, NÃO na raiz do projeto. Estrutura correta: `imgs/input/` (imutável) e `imgs/output/<projeto>/<imagem>/`.
- **27/05 - NUNCA rodar servidor direto no terminal**: `npm run start` travou o terminal 2 vezes. SEMPRE usar Docker com CPU ou batch script em janela separada.
- **27/05 - FastAPI + torch = bloqueia event loop**: GroundingDINO+SAM2 são síncronos e pesados. Usar `run_in_executor` com ThreadPoolExecutor.

### Grounded-SAM-2 (testado 27/05 - BOM)
- 1-TEST.jpg: 67 detections → 28 after filter. Classes: pants, shoes, shirt, dress, hat, skirt, boots, handbag, blouse, sunglasses
- 2-TEST.jpg: 9 detections → 6 after filter. Classes: blouse, sunglasses, jacket, hat
- SAM2 tiny (150MB) + GroundingDINO SwinT funcionaram em CPU sem problemas

### segformer-clothes-tfjs (testado 27/05 - RUIM)
- Testado via Docker + Puppeteer, ~5s por imagem
- Detectou APENAS Face (rosto) e Hair (cabelo) — classes de roupa NÃO detectadas
- Modelo provavelmente treinado em dataset diferente (poses frontais, fundo limpo)

## 5. Comandos Que Funcionam

```powershell
# Fixar PATH do Node.js
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

# Matar processos órfãos
Get-Process node, python -ErrorAction SilentlyContinue | Stop-Process -Force

# Verificar porta livre
netstat -ano | Select-String "8001"

# Abrir servidor em janela separada
Start-Process -FilePath "api\run_server.bat" -WindowStyle Normal
```

## 6. Pendências / Blockers

### Blockers
- (nenhum)

### Pendências
- [x] Testar segformer com imagens (RUIM — apenas Face/Hair)
- [x] Testar Grounded-SAM-2 com ambas as imagens (BOM)
- [x] Criar API FastAPI com Grounded-SAM-2
- [x] Testar API HTTP com ambas as imagens
- [x] Documentar uso da API (`api/API.md`)
- [x] Consolidar scripts de teste (`test_api.py` substitui 3 scripts antigos)
- [ ] Comparar resultados visuais com frozen.h5 baseline (frozen.h5 não está no workspace — pular)

## 7. Log de Sessões

### 2026-05-27 - Sessão atual
- Criada estrutura MEMORY.md para persistência entre sessões
- Corrigida estrutura `imgs/output/` (duplicado removido)
- **Segformer**: testado via Docker + Puppeteer — RUIM (apenas Face/Hair detectados)
- **Grounded-SAM-2**: testado nas 2 imagens — BOM (classes relevantes detectadas)
- **Virtual_Try_on U2NET**: testado — RUIM (100% background, ZERO roupas)
- Criada API FastAPI (`api/segmentor.py` + `api/server.py`)
- Problema numpy/h5py resolvido com downgrade numpy<2
- Problema event loop bloqueado resolvido com ThreadPoolExecutor
- API testada com sucesso: 200 OK, ambas imagens detectaram roupas corretamente

### 2026-05-17 - Teste Grounded-SAM-2
- Testado com sucesso usando SAM2 tiny + GroundingDINO SwinT
- Problema OneDrive resolvido (output → C:\Temp)
- Problema modelo large resolvido (substituído por tiny)
