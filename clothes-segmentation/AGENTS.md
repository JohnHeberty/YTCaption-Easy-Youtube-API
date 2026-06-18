# AGENTS.md - Segmentação de Roupas

## Memória

### Memória de Curto Prazo (MEMORY.md)
**LEIA MEMORY.md antes de qualquer ação.** Ele contém o estado atual, decisões, descobertas e log de sessões.
Atualize MEMORY.md ao completar um milestone ou ao final da sessão.

### Memória de Longo Prazo (.opencode/memory/)
- **O que é**: Log cronológico detalhado de cada dia em `.opencode/memory/YYYY-MM-DD.md`
- **Quando escrever**: Após CADA ação significativa (comando rodado, erro encontrado, decisão tomada)
- **O que registrar**: Comandos + resultado, erros + resolução, decisões, descobertas, mudanças de plano
- **Regra**: Não espere o final da sessão. Escreva ao longo do dia para não perder contexto.

## Ambiente
- **OS**: Windows, PowerShell 5.1
- **Python**: 3.12.7 via `python` (NUNCA use `python3` - alias quebrado no Windows)
- **Node.js**: v24.15.0 (winget). PATH precisa ser fixado a cada nova sessão:
  ```powershell
  $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
  ```
- **Sem GPU CUDA** - projetos que exigem GPU irão cair em fallback para CPU (lento ou falhar)

## Estrutura (3 projetos para testar)

### segformer-clothes-tfjs
- Web app React + TF.js para segmentação de roupas (17 classes)
- Modelo TF.js em `public/clothes_model_web_model/`
- Entrada: `npm run start` (Vite, porta 3000/3001)
- Atualmente usa webcam; adaptar `App.jsx` para aceitar arquivo de imagem
- `renderBox.js` desenha máscaras, não bounding boxes (é Segformer não YOLO)

### Virtual_Try_on_FashionGenAi
- Python: U2NET segmentação + Stable Diffusion inpainting
- Entrada: `python main/main.py --image <path> --part upper --prompt "<desc>" --output <path>`
- Problema linha 43: `git clone` hardcoded (comentado, mas checkpoint faltando)
- Checkpoint esperado: `trained_checkpoint/../cloth_segm_u2net_latest.pth` (falta baixar)
- 91 dependências, muitas incompatíveis com Python 3.12 (torch 1.13, diffusers antigo)
- Sem GPU: Stable Diffusion será extremamente lento ou vai falhar (OOM)

### Grounded-SAM-2-clothes-extraction
- Notebook Jupyter (.ipynb) 800+ linhas
- Precisa: SAM-2 + GroundingDINO (instalar repos separados)
- Modelos SAM2 + GroundingDINO para baixar do HuggingFace
- Complexo para testar rapidamente

## Imagens de Teste
- `TEST.jpg` - Foto de homem, polo preta, jeans azul, cinto amarelo
- `images.jpeg` - validação adicional

## Regras de Execuçao
- SEMPRE usar timeout nos comandos bash (max 120000ms)
- Rodar leituras/instalações em paralelo quando possível
- Nunca usar `cd` - usar parametro `workdir` do Bash
- Nunca instalar pacotes sem verificar versoes compatíveis primeiro
- **NUNCA** rodar processos em background direto no terminal (npm start, python server, etc)
- **SEMPRE** criar um `.bat` ou `.ps1` e usar `Start-Process` para lançar em janela separada
- O script deve abrir nova janela e NÃO prender o terminal atual
- Exemplo correto: `Start-Process -FilePath "script.bat" -WindowStyle Normal`
- **REGRAS CRÍTICAS - VIOLAR CAUSA PROBLEMAS GRAVES**:
  - **NUNCA** iniciar um processo longo (npm start, python server, pip install, build) sem timeout — o terminal fica TRAVADO
  - **SEMPRE** matar processos órfãos antes de iniciar novos (`Get-Process node, python | Stop-Process -Force`)
  - **SEMPRE** verificar se a porta está livre antes de rodar servidor (`netstat -ano | Select-String "3000"`)
  - **NUNCA** usar `pty_spawn` para processos que devem rodar síncrono com timeout — use Bash com `timeout`
  - **SEMPRE** limpar processos leftover do run anterior antes de tentar novamente

## Regras de Planejamento (CRÍTICO - SEGUIR SEMPRE)
- **GASTAR MAIS TEMPO PENSANDO DO QUE EXECUTANDO** - planejamento > ação
- **SEMPRE analisar pelo menos 3 opções** antes de tomar qualquer decisão
- **Avaliar prós e contras de CADA opção** antes de escolher
- **Arquitetar o fluxo COMPLETO antes** de executar qualquer passo
- **Antever problemas**: o que pode dar errado? quais dependências? quebras compatibilidade?
- **Verificar requisitos PRÉ-instalação**: versões, GPU, memória, checkpoints, tamanho
- **Verificar estado atual ANTES de agir**: o que já está feito? o que está rodando?
- **Evitar ações reativas** - pensar ahead para não ficar preso ou fazer retrabalho
- **NUNCA começar a executar sem ter o plano completo mapeado**
- **Comunicar o plano ao usuário ANTES de executar** (resumido, claro)
- **Se algo pode quebrar ou travar, planejar o fallback antes**

## Prioridade
1. segformer (executavel agora, sem GPU)
2. Virtual_Try_on (dependencias incompatíveis, sem GPU)
3. Grounded-SAM-2 ( complexo, precisa GPU)

## Objetivo Final
Substituir `frozen.h5` do Fashion-AI-segmentation (segmentacao pessima). Escolher melhor modelo criar API unificada.

## Checklist (ver TASK.md)
TASK.md na raiz tem checklist de testes por projeto. Atualizar ao completar cada teste.
