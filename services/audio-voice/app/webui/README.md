# 🎙️ Audio Voice Service - WebUI Profissional

## 📋 Visão Geral

Esta é a **nova WebUI profissional** do Audio Voice Service, desenvolvida com **HTML5 + Bootstrap 5 + JavaScript ES6+** (vanilla, sem frameworks).

Substitui a WebUI anterior com um painel administrativo completo, moderno e totalmente funcional, cobrindo **100% dos endpoints da API REST**.

---

## 🚀 Acesso

- **URL de Produção:** `https://clone.loadstask.com/webui-new`
- **URL Local (desenvolvimento):** `http://localhost:8001/webui-new`

---

## ✨ Recursos Implementados

### 📊 **Dashboard**
- Status da API (health check básico e profundo)
- Estatísticas do sistema (admin/stats)
- Estatísticas de modelos RVC
- Últimos jobs criados (5 mais recentes)
- Últimas vozes clonadas (5 mais recentes)
- Botão de atualização manual

### 🎤 **Dublar Texto (Criar Job de TTS)**
- ✅ Formulário completo para criação de jobs de dublagem
- ✅ Suporte aos dois modos:
  - **Dubbing:** Voz genérica (presets)
  - **Dubbing with Clone:** Voz clonada (voice_id)
- ✅ Seleção de idioma de origem e destino
- ✅ Seleção de engine (XTTS ou F5-TTS)
- ✅ Seleção de perfil de qualidade (filtra por engine)
- ✅ Texto de referência opcional (F5-TTS)
- ✅ **Configurações avançadas RVC** (colapsável):
  - Toggle para ativar/desativar RVC
  - Seleção de modelo RVC
  - Sliders para pitch, index rate, filter radius, RMS mix rate, protect
  - Dropdown de método F0 (rmvpe, fcpe, pm, harvest, dio, crepe)
- ✅ Validação de campos obrigatórios conforme modo
- ✅ Contador de caracteres (1-10.000)
- ✅ Feedback visual (toasts, spinners em botões)

### 📋 **Jobs & Downloads**
- ✅ Listagem de jobs (com limite configurável)
- ✅ Auto-refresh opcional (10s)
- ✅ Busca de job por ID
- ✅ Tabela com:
  - Job ID, Status (badges coloridos), Engine, Mode, Data de criação
  - Ações por job:
    - **Detalhes:** Modal com JSON completo
    - **Formatos:** Lista formatos disponíveis
    - **Download WAV:** Link direto
    - **Excluir:** Com confirmação
- ✅ Estados vazios amigáveis

### 👥 **Vozes Clonadas**
- ✅ **Formulário de clonagem de voz:**
  - Upload de áudio (WAV, MP3, OGG, etc.)
  - Nome, idioma, engine (XTTS/F5-TTS)
  - Descrição e texto de referência opcional
  - Retorna job_id (HTTP 202)
- ✅ **Área "Clonagens em Andamento":**
  - Polling automático dos jobs de clonagem
  - Atualização de status em tempo real
  - Notificação quando concluído
  - Remoção automática após 10s da conclusão
- ✅ **Lista de vozes clonadas:**
  - Cards responsivos com informações completas
  - Ações: Detalhes (modal JSON), Excluir (confirmação)
  - Filtros por engine, idioma, data

### 🖥️ **Modelos RVC**
- ✅ **Upload de modelo RVC:**
  - Nome (único), descrição
  - Arquivo .pth (obrigatório)
  - Arquivo .index (opcional)
  - Validação de tamanho
- ✅ **Estatísticas:** Total de modelos, tamanho total em MB
- ✅ **Lista de modelos:**
  - Cards com informações (nome, tamanho, data, índice)
  - Ordenação por: Nome, Data, Tamanho
  - Ações: Detalhes, Excluir

### ⚙️ **Perfis de Qualidade**
- ✅ **Listagem agrupada por engine (tabs):**
  - XTTS: perfis XTTS
  - F5-TTS: perfis F5-TTS
- ✅ **Criar novo perfil:**
  - Modal com formulário JSON
  - Nome, engine, descrição, is_default
  - Parâmetros específicos do engine (JSON)
- ✅ **Editar perfil:**
  - Carrega dados existentes
  - Permite atualizar nome, descrição, parâmetros
  - Validação JSON
- ✅ **Excluir perfil:**
  - Apenas perfis não-padrão
  - Confirmação modal
- ✅ **Definir como padrão:**
  - Botão para marcar perfil como default
  - Atualização visual instantânea

### 🛠️ **Admin & Health**
- ✅ Health check básico (`GET /`)
- ✅ Health check profundo (`GET /health`)
- ✅ Estatísticas detalhadas (`GET /admin/stats`)
- ✅ **Limpeza de sistema:**
  - Checkbox para deep cleanup
  - Confirmação antes de executar
  - Resultado exibido em modal

### 🚩 **Feature Flags**
- ✅ Listagem de todas as feature flags
- ✅ Tabela com nome, status, valor
- ✅ Consulta de flag específica:
  - Por nome
  - Com user_id opcional
  - Resultado em card

---

## 🎨 Design & UX

### **Layout**
- **Navbar fixa** no topo com logo e navegação
- **Single-page application** (SPA leve, navegação via JS)
- **Seções separadas** (hide/show via JS)
- **Responsivo** (mobile-first, funciona em smartphones, tablets, desktops)

### **Componentes Bootstrap 5**
- Cards, modals, toasts, badges, alerts
- Tabelas responsivas, forms validados
- Botões com spinners durante loading
- Progress bars, sliders (range inputs)
- Tabs, collapse (áreas colapsáveis)

### **Feedback Visual**
- ✅ **Toasts** para sucesso/erro/warning/info
- ✅ **Spinners** em botões durante requisições
- ✅ **Badges coloridos** para status de jobs
- ✅ **Estados vazios** amigáveis
- ✅ **Loading states** em todas as seções
- ✅ **Modals** para confirmações e detalhes

### **Cores & Status**
- **Jobs:**
  - `queued`: Cinza
  - `processing`: Azul claro
  - `completed`: Verde
  - `failed`: Vermelho
- **Toasts:**
  - Success: Verde
  - Error: Vermelho
  - Warning: Amarelo
  - Info: Azul

---

## 📁 Estrutura de Arquivos

```
app/webui_new/
├── index.html              # HTML principal (SPA)
├── assets/
│   ├── css/
│   │   └── styles.css      # CSS customizado (em cima do Bootstrap)
│   └── js/
│       └── app.js          # Toda a lógica de API e DOM
```

---

## 🔧 Arquitetura Técnica

### **Frontend Stack**
- **HTML5** semântico
- **CSS3** + Bootstrap 5.3.2 (via CDN)
- **JavaScript ES6+** (async/await, Fetch API, Modules)
- **Bootstrap Icons** 1.11.1

### **API Integration**
- **Base URL:** `https://clone.loadstask.com`
- **Fetch API** para todas as requisições
- **Content-Types suportados:**
  - `application/json` (GET, POST JSON)
  - `application/x-www-form-urlencoded` (POST /jobs)
  - `multipart/form-data` (uploads)
- **Tratamento de erros:**
  - HTTP 422: Extrai `detail` array e formata mensagens
  - Outros erros: Toast genérico
- **Polling:** Jobs de clonagem (5s, max 60 tentativas)

### **Estado Global (app.js)**
```javascript
app.state = {
    currentSection: 'dashboard',
    languages: [],
    presets: [],
    voices: [],
    rvcModels: [],
    qualityProfiles: { xtts_profiles: [], f5tts_profiles: [] },
    cloningJobs: {},
    jobsAutoRefreshInterval: null,
}
```

### **Funções Principais**
- `app.init()`: Inicialização
- `app.navigate(section)`: Navegação entre seções
- `app.fetchJson(url, options)`: Wrapper para fetch com tratamento de erros
- `app.showToast(title, message, type)`: Sistema de notificações
- `app.createJob()`, `app.cloneVoice()`, `app.uploadRvcModel()`: Operações de criação
- `app.loadJobs()`, `app.loadVoices()`, `app.loadRvcModels()`: Carregamento de listas
- `app.pollCloningJob(jobId)`: Polling de jobs de clonagem

---

## 🌐 Endpoints Cobertos

### **Health & Admin**
- `GET /` - Health básico
- `GET /health` - Health profundo
- `GET /admin/stats` - Estatísticas do sistema
- `POST /admin/cleanup?deep={bool}` - Limpeza

### **Jobs**
- `POST /jobs` - Criar job de dublagem
- `GET /jobs?limit={n}` - Listar jobs
- `GET /jobs/{job_id}` - Detalhes do job
- `DELETE /jobs/{job_id}` - Excluir job
- `GET /jobs/{job_id}/formats` - Formatos disponíveis
- `GET /jobs/{job_id}/download?format={format}` - Download

### **Vozes**
- `POST /voices/clone` - Clonar voz (retorna job_id)
- `GET /voices?limit={n}` - Listar vozes
- `GET /voices/{voice_id}` - Detalhes da voz
- `DELETE /voices/{voice_id}` - Excluir voz

### **RVC Models**
- `POST /rvc-models` - Upload de modelo
- `GET /rvc-models?sort_by={field}` - Listar modelos
- `GET /rvc-models/{model_id}` - Detalhes do modelo
- `DELETE /rvc-models/{model_id}` - Excluir modelo
- `GET /rvc-models/stats` - Estatísticas

### **Quality Profiles**
- `GET /quality-profiles` - Listar todos (agrupados)
- `POST /quality-profiles` - Criar perfil
- `GET /quality-profiles/{engine}` - Listar por engine
- `GET /quality-profiles/{engine}/{profile_id}` - Detalhes
- `PATCH /quality-profiles/{engine}/{profile_id}` - Atualizar
- `DELETE /quality-profiles/{engine}/{profile_id}` - Excluir
- `POST /quality-profiles/{engine}/{profile_id}/set-default` - Definir padrão

### **Presets & Idiomas**
- `GET /presets` - Listar vozes genéricas
- `GET /languages` - Listar idiomas suportados

### **Feature Flags**
- `GET /feature-flags` - Listar todas
- `GET /feature-flags/{feature_name}?user_id={id}` - Checar flag específica

---

## 🔐 Validações Implementadas

### **Formulário de Job**
- Texto: obrigatório, 1-10.000 chars
- Idioma origem: obrigatório
- Modo: obrigatório
- Voice preset: obrigatório se `mode=dubbing`
- Voice ID: obrigatório se `mode=dubbing_with_clone`
- RVC model ID: obrigatório se `enable_rvc=True`

### **Formulário de Clonagem**
- Arquivo de áudio: obrigatório
- Nome: obrigatório
- Idioma: obrigatório

### **Formulário de RVC Model**
- Nome: obrigatório, max 100 chars
- Arquivo .pth: obrigatório
- Descrição: max 500 chars

### **Formulário de Quality Profile**
- Nome: obrigatório
- Engine: obrigatório
- Parâmetros: JSON válido obrigatório

---

## 🎯 Diferenças da WebUI Antiga

| Aspecto | WebUI Antiga | Nova WebUI |
|---------|-------------|------------|
| **Framework** | HTML inline básico | Bootstrap 5 profissional |
| **Cobertura API** | ~30% (apenas TTS básico) | **100%** (todos os endpoints) |
| **UX/UI** | Simples, estática | Moderna, responsiva, interativa |
| **Feedback** | Básico (alerts) | Toasts, spinners, modals, badges |
| **Navegação** | Single page simples | SPA com seções organizadas |
| **Jobs** | Apenas criar | Criar, listar, buscar, excluir, download |
| **Vozes** | Não suportado | Clonar, listar, excluir, polling |
| **RVC** | Não suportado | Upload, listar, excluir, stats |
| **Quality Profiles** | Não suportado | CRUD completo + set default |
| **Admin** | Não suportado | Health, stats, cleanup |
| **Feature Flags** | Não suportado | Listar, checar flags |
| **Responsivo** | Não | ✅ Sim (mobile-first) |
| **Idioma** | Inglês | Português-BR |

---

## 🚀 Como Usar

1. **Acessar:** `https://clone.loadstask.com/webui-new`

2. **Dashboard:**
   - Visão geral do sistema
   - Clique em "Atualizar Dashboard" para recarregar

3. **Criar Job de Dublagem:**
   - Navegue para "Dublar Texto"
   - Preencha o formulário
   - Se usar RVC, expanda "Configurações Avançadas RVC"
   - Clique em "Criar Job"
   - Será redirecionado para "Jobs & Downloads"

4. **Clonar Voz:**
   - Navegue para "Vozes Clonadas"
   - Upload de áudio
   - Preencha nome, idioma, engine
   - Clique em "Iniciar Clonagem"
   - Acompanhe em "Clonagens em Andamento"

5. **Upload de Modelo RVC:**
   - Navegue para "Modelos RVC"
   - Upload de .pth e .index (opcional)
   - Use o modelo na seção "Dublar Texto"

6. **Gerenciar Perfis de Qualidade:**
   - Navegue para "Perfis de Qualidade"
   - Crie, edite, exclua perfis
   - Defina perfis padrão por engine

---

## 🐛 Debugging

### **Console do Navegador**
Abra DevTools (F12) → Console para ver logs:
- `🚀 Inicializando Audio Voice Service WebUI...`
- `✅ WebUI inicializada com sucesso!`
- `📥 Carregando dados iniciais...`
- `🧭 Navegando para: {section}`

### **Network Tab**
Monitore requisições HTTP:
- Verifique payloads, headers, status codes
- Identifique erros 422 (validação)

### **Toasts**
Todas as operações exibem feedback via toast:
- **Verde:** Sucesso
- **Vermelho:** Erro
- **Amarelo:** Warning
- **Azul:** Info

---

## 🔮 Próximas Melhorias (Opcionais)

- [ ] Filtros avançados em tabelas (por status, engine, data)
- [ ] Gráficos de estatísticas (Chart.js)
- [ ] Drag & drop para upload de arquivos
- [ ] Preview de áudio antes de upload
- [ ] Histórico de jobs (paginação)
- [ ] Exportar logs/stats em CSV/JSON
- [ ] Dark mode toggle (já preparado no CSS)
- [ ] Internacionalização (i18n) EN/PT-BR
- [ ] WebSockets para updates em tempo real
- [ ] PWA (Progressive Web App) com service worker

---

## 📝 Notas Técnicas

### **Por que Bootstrap 5?**
- Biblioteca madura, bem documentada
- Grid system responsivo poderoso
- Componentes prontos (modals, toasts, cards)
- Sem dependências (bundle.js inclui Popper)
- Customização fácil via CSS

### **Por que Vanilla JS?**
- Simplicidade (sem build tools)
- Performance (sem overhead de frameworks)
- Manutenibilidade (código direto)
- Compatibilidade (ES6+ suportado por 95%+ navegadores)

### **Estrutura Modular**
- `app.js` organizado em "seções lógicas" com comentários
- Funções reutilizáveis (`fetchJson`, `showToast`, `renderEmptyState`)
- Estado centralizado (`app.state`)

---

## 👨‍💻 Desenvolvedor

Implementado por **DESENVOLVEDOR FRONT-END SÊNIOR** especializado em:
- HTML5 semântico
- CSS3 + Bootstrap 5
- JavaScript ES6+ (vanilla)
- Integração com APIs REST (FastAPI)

**Data de Criação:** 29 de Novembro de 2025

---

## 📄 Licença

Mesmo do projeto principal (Audio Voice Service).

---

## ✅ Checklist de Qualidade

- [x] Cobertura 100% dos endpoints da API
- [x] Responsivo (mobile, tablet, desktop)
- [x] Feedback visual completo (toasts, spinners, badges)
- [x] Tratamento de erros robusto
- [x] Validação de formulários
- [x] Estados vazios amigáveis
- [x] Documentação completa
- [x] Código organizado e comentado
- [x] Português-BR na interface
- [x] Acessibilidade básica (semântica HTML)

---

**🎉 WebUI pronta para uso em produção!**

Acesse: `https://clone.loadstask.com/webui-new`
