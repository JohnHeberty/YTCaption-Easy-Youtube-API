# SPRINTS_WEBUI_AUDIO – Plano de Implementação

**Data:** 29 de novembro de 2025  
**Baseado em:** QA_WEBUI_AUDIO.md  
**Objetivo:** Tornar WebUI 100% funcional e coerente com backend

---

## 🎯 OBJETIVO GERAL

Resolver **18 problemas** identificados na auditoria (7 críticos P0, 6 médios P1, 5 melhorias P2), transformando a WebUI de "estática/decorativa" em **totalmente funcional** e alinhada com o backend FastAPI.

### Princípios de Trabalho
1. ✅ Sprints pequenas (1-3 dias cada)
2. ✅ Começar sempre com validação/teste
3. ✅ Implementar front + back de forma atômica
4. ✅ Testar manualmente após cada sprint
5. ✅ Documentar decisões técnicas

---

## 📋 SPRINT 0 – PREPARAÇÃO E LIMPEZA (0.5 dia)

### Objetivo
Remover duplicações e preparar ambiente para desenvolvimento limpo.

### Tarefas
- [ ] **T0.1** - Analisar endpoints duplicados `/quality-profiles`
  - Decisão: Manter endpoint NOVO (JSON, linha 1241) ou LEGACY (Form, linha 858)
  - **Recomendação:** Manter NOVO (suporta XTTS + F5-TTS)
  - Ação: Renomear LEGACY para `/quality-profiles-legacy-form` ou remover
  
- [ ] **T0.2** - Criar branch de desenvolvimento
  ```bash
  git checkout -b feature/webui-full-integration
  ```

- [ ] **T0.3** - Backup da WebUI atual
  ```bash
  cp app/webui/full-control.html app/webui/full-control.html.backup
  ```

- [ ] **T0.4** - Preparar ambiente de teste local
  - Docker containers rodando
  - Logs monitorados
  - Postman/Thunder Client para testes de API

### Critérios de Aceitação
- ✅ Branch criada
- ✅ Backup feito
- ✅ Decisão sobre endpoints duplicados tomada e implementada
- ✅ API testável via Postman

---

## 🔴 SPRINT 1 – QUALITY PROFILES: CRUD BÁSICO (2 dias)

### Objetivo
Fazer **criar, listar, deletar** profiles funcionar 100% (front + back alinhados).

### Problemas Resolvidos
- 🔴 P0-1: Conflito JSON vs Form Data
- 🔴 P0-2: Endpoint duplicado
- 🟡 P1-1: Sem feedback visual de erro
- 🟡 P1-2: Lista não atualiza

### Tarefas Backend

- [ ] **T1.1** - Decidir endpoint final para Quality Profiles
  - **Decisão:** Usar endpoint NOVO (linha 1241) que aceita JSON
  - Ação: Remover ou deprecar endpoint LEGACY (linha 858)
  - Arquivo: `app/main.py`
  
- [ ] **T1.2** - Garantir endpoint `POST /quality-profiles` aceita JSON
  ```python
  @app.post("/quality-profiles", status_code=201)
  async def create_quality_profile(request: QualityProfileCreate):
      # Já implementado na linha 1241
  ```

- [ ] **T1.3** - Testar endpoints manualmente via Postman
  - POST /quality-profiles (criar XTTS)
  - POST /quality-profiles (criar F5-TTS)
  - GET /quality-profiles (listar todos)
  - DELETE /quality-profiles/{engine}/{profile_id}
  - Validar respostas 201, 200, 204, 404, 400

### Tarefas Frontend

- [ ] **T1.4** - Corrigir `createProfile()` para usar estrutura JSON correta
  - Arquivo: `app/webui/full-control.html` linha ~450
  - Garantir que `parameters` seja objeto aninhado correto
  - Verificar que engine seja string válida ('xtts' ou 'f5tts')

- [ ] **T1.5** - Adicionar elemento `<div id="profile-msg" class="msg"></div>` no DOM
  - Localização: Antes do formulário de criar profile
  - Garantir que `msg('profile-msg', 'success/error', text)` funcione

- [ ] **T1.6** - Melhorar `loadProfiles()` para tratar erros
  ```javascript
  async function loadProfiles() {
      try {
          const res = await fetch('/quality-profiles');
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          const data = await res.json();
          // ... resto do código
      } catch (e) {
          msg('profile-msg', 'error', 'Erro ao carregar profiles: ' + e.message);
      }
  }
  ```

- [ ] **T1.7** - Adicionar validação client-side no formulário
  - Nome não pode ser vazio
  - Descrição opcional
  - Parâmetros dentro dos ranges corretos

- [ ] **T1.8** - Testar fluxo completo no browser
  - Criar profile XTTS → Ver na lista → Deletar → Sumir da lista
  - Criar profile F5-TTS → Ver na lista → Deletar → Sumir da lista
  - Tentar criar com nome vazio → Ver mensagem de erro
  - Tentar criar duplicado → Ver mensagem de erro backend

### Critérios de Aceitação
- ✅ Criar profile funciona (XTTS e F5-TTS)
- ✅ Mensagens de sucesso/erro aparecem na tela
- ✅ Lista atualiza automaticamente após criar/deletar
- ✅ Delete funciona com confirmação
- ✅ Validação client-side previne envios inválidos
- ✅ Sem erros no console do browser
- ✅ Logs backend mostram operações corretas

---

## 🔴 SPRINT 2 – QUALITY PROFILES: EDITAR (1 dia)

### Objetivo
Implementar edição de profiles existentes (front + back).

### Tarefas Backend

- [ ] **T2.1** - Verificar endpoint `PATCH /quality-profiles/{engine}/{profile_id}`
  - Já existe (linha 1338)
  - Testar via Postman
  - Validar que aceita partial updates

### Tarefas Frontend

- [ ] **T2.2** - Adicionar botão "Edit" nos profile cards
  ```html
  <button class="btn-secondary btn-sm" onclick="editProfile('${p.engine}','${p.id}')">
      Edit
  </button>
  ```

- [ ] **T2.3** - Criar modal/formulário de edição
  - Opção A: Modal overlay
  - Opção B: Inline editing (expandir card)
  - **Recomendação:** Modal por clareza

- [ ] **T2.4** - Implementar função `editProfile(engine, id)`
  ```javascript
  async function editProfile(engine, id) {
      // 1. Fetch profile atual via GET /quality-profiles/{engine}/{id}
      // 2. Preencher modal com valores atuais
      // 3. Ao salvar, PATCH /quality-profiles/{engine}/{id}
      // 4. Atualizar lista
  }
  ```

- [ ] **T2.5** - Testar edição
  - Editar nome → Salvar → Ver mudança
  - Editar parâmetros → Salvar → Ver mudança
  - Cancelar edição → Não mudar nada

### Critérios de Aceitação
- ✅ Botão "Edit" aparece em todos os profiles
- ✅ Modal/formulário de edição funciona
- ✅ Valores atuais preenchem o formulário
- ✅ Salvar atualiza profile no backend
- ✅ Lista atualiza após edição
- ✅ Cancelar não muda nada

---

## 🔴 SPRINT 3 – RVC MODELS: UPLOAD E LISTAGEM (2 dias)

### Objetivo
Permitir upload de modelos RVC (.pth + .index) e listá-los.

### Problemas Resolvidos
- 🔴 P0-3: Sem interface de upload
- 🔴 P0-4: Sem botão delete

### Tarefas Backend

- [ ] **T3.1** - Verificar endpoint `POST /rvc-models`
  - Já existe (linha 706)
  - Aceita Form Data (multipart/form-data)
  - Testar upload via Postman com arquivo .pth real

- [ ] **T3.2** - Verificar endpoint `DELETE /rvc-models/{model_id}`
  - Já existe (linha 816)
  - Testar delete via Postman

### Tarefas Frontend

- [ ] **T3.3** - Criar formulário de upload na tab RVC
  ```html
  <div class="card">
      <h2>Upload RVC Model</h2>
      <div id="rvc-msg" class="msg"></div>
      <div class="form-group">
          <label>Model Name *</label>
          <input type="text" id="rvc-name">
      </div>
      <div class="form-group">
          <label>Description</label>
          <input type="text" id="rvc-desc">
      </div>
      <div class="form-group">
          <label>PTH File * (.pth)</label>
          <input type="file" id="rvc-pth" accept=".pth">
      </div>
      <div class="form-group">
          <label>Index File (.index, optional)</label>
          <input type="file" id="rvc-index" accept=".index">
      </div>
      <button onclick="uploadRVCModel()">Upload Model</button>
  </div>
  ```

- [ ] **T3.4** - Implementar `uploadRVCModel()`
  ```javascript
  async function uploadRVCModel() {
      const formData = new FormData();
      formData.append('name', document.getElementById('rvc-name').value);
      const desc = document.getElementById('rvc-desc').value;
      if (desc) formData.append('description', desc);
      
      const pthFile = document.getElementById('rvc-pth').files[0];
      if (!pthFile) return msg('rvc-msg', 'error', 'Select PTH file');
      formData.append('pth_file', pthFile);
      
      const indexFile = document.getElementById('rvc-index').files[0];
      if (indexFile) formData.append('index_file', indexFile);
      
      try {
          const res = await fetch('/rvc-models', { method: 'POST', body: formData });
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || 'Upload failed');
          msg('rvc-msg', 'success', 'Model uploaded: ' + data.model_id);
          loadRVCModels();
      } catch (e) {
          msg('rvc-msg', 'error', e.message);
      }
  }
  ```

- [ ] **T3.5** - Adicionar botão delete nos model cards
  ```javascript
  list.innerHTML = data.models.map(m => `
      <div style="...">
          <strong>${m.name}</strong>
          <br><small>ID: ${m.model_id}</small>
          <br><button class="btn-danger btn-sm" onclick="deleteRVCModel('${m.model_id}')">
              Delete
          </button>
      </div>
  `).join('');
  ```

- [ ] **T3.6** - Implementar `deleteRVCModel(id)`
  ```javascript
  async function deleteRVCModel(id) {
      if (!confirm('Delete RVC model?')) return;
      try {
          await fetch('/rvc-models/' + id, { method: 'DELETE' });
          msg('rvc-msg', 'success', 'Model deleted');
          loadRVCModels();
      } catch (e) {
          msg('rvc-msg', 'error', e.message);
      }
  }
  ```

- [ ] **T3.7** - Testar fluxo completo
  - Upload modelo → Ver na lista
  - Upload sem nome → Ver erro
  - Upload sem arquivo → Ver erro
  - Delete modelo → Sumir da lista

### Critérios de Aceitação
- ✅ Formulário de upload funciona
- ✅ Upload aceita .pth + .index
- ✅ Validação previne uploads inválidos
- ✅ Modelos aparecem na lista após upload
- ✅ Delete funciona
- ✅ Mensagens de sucesso/erro aparecem

---

## 🔴 SPRINT 4 – RVC INTEGRATION NO TTS (1.5 dias)

### Objetivo
Permitir selecionar modelo RVC e usar na geração de áudio.

### Problemas Resolvidos
- 🔴 P0-5: Sem seleção de modelo para uso
- 🟡 P1-6: Sem opção RVC na criação de job

### Tarefas Frontend

- [ ] **T4.1** - Adicionar seção RVC no formulário TTS
  ```html
  <!-- Adicionar após Quality Profile -->
  <div class="form-group">
      <label>
          <input type="checkbox" id="tts-enable-rvc"> 
          Enable RVC Voice Conversion
      </label>
  </div>
  <div id="rvc-options" style="display:none;">
      <div class="form-group">
          <label>RVC Model *</label>
          <select id="tts-rvc-model">
              <option value="">Select model...</option>
          </select>
      </div>
      <div class="form-group">
          <label>Pitch Shift: <span class="slider-val" id="val-pitch">0</span></label>
          <input type="range" class="slider" id="tts-rvc-pitch" 
                 min="-12" max="12" value="0" 
                 oninput="updateSlider('pitch')">
      </div>
      <!-- Adicionar outros parâmetros RVC se necessário -->
  </div>
  ```

- [ ] **T4.2** - Adicionar lógica de show/hide para opções RVC
  ```javascript
  document.getElementById('tts-enable-rvc').addEventListener('change', function() {
      document.getElementById('rvc-options').style.display = 
          this.checked ? 'block' : 'none';
  });
  ```

- [ ] **T4.3** - Modificar `loadRVCModels()` para popular select do TTS
  ```javascript
  async function loadRVCModels() {
      const res = await fetch('/rvc-models');
      const data = await res.json();
      
      // Popular lista na tab RVC
      const list = document.getElementById('rvc-list');
      // ... código existente ...
      
      // Popular select na tab TTS
      const select = document.getElementById('tts-rvc-model');
      if (data.models && data.models.length > 0) {
          select.innerHTML = '<option value="">Select model...</option>' + 
              data.models.map(m => 
                  `<option value="${m.model_id}">${m.name}</option>`
              ).join('');
      }
  }
  ```

- [ ] **T4.4** - Modificar `createTTSJob()` para incluir parâmetros RVC
  ```javascript
  // Adicionar após quality_profile_id
  const enableRvc = document.getElementById('tts-enable-rvc').checked;
  if (enableRvc) {
      formData.append('enable_rvc', 'true');
      const rvcModel = document.getElementById('tts-rvc-model').value;
      if (!rvcModel) {
          return msg('tts-msg', 'error', 'Select RVC model');
      }
      formData.append('rvc_model_id', rvcModel);
      formData.append('rvc_pitch', document.getElementById('tts-rvc-pitch').value);
      // Adicionar outros parâmetros...
  }
  ```

- [ ] **T4.5** - Testar integração RVC
  - Criar job sem RVC → Funciona normal
  - Ativar RVC sem selecionar modelo → Ver erro
  - Criar job com RVC + modelo → Ver job processar
  - Baixar áudio → Verificar se RVC foi aplicado

### Critérios de Aceitação
- ✅ Checkbox "Enable RVC" funciona
- ✅ Opções RVC aparecem/somem dinamicamente
- ✅ Select de modelos RVC populado
- ✅ Validação exige modelo se RVC ativado
- ✅ Job criado com parâmetros RVC corretos
- ✅ Áudio gerado com RVC aplicado

---

## 🔴 SPRINT 5 – BINDING PROFILE ↔ ENGINE (1 dia)

### Objetivo
Filtrar quality profiles pelo engine TTS selecionado.

### Problemas Resolvidos
- 🔴 P0-7: Sem binding Profile ↔ Engine

### Tarefas Frontend

- [ ] **T5.1** - Adicionar evento `onchange` no select de engine
  ```javascript
  document.getElementById('tts-engine').addEventListener('change', function() {
      filterProfilesByEngine();
  });
  ```

- [ ] **T5.2** - Implementar `filterProfilesByEngine()`
  ```javascript
  function filterProfilesByEngine() {
      const selectedEngine = document.getElementById('tts-engine').value;
      const select = document.getElementById('tts-profile');
      
      // Buscar profiles da memória (ou refetch)
      const xttsProfiles = window.cachedProfiles?.xtts_profiles || [];
      const f5ttsProfiles = window.cachedProfiles?.f5tts_profiles || [];
      
      const filtered = selectedEngine === 'xtts' ? xttsProfiles : f5ttsProfiles;
      
      select.innerHTML = '<option value="">Default</option>' + filtered.map(p => 
          `<option value="${p.id}">${p.name}</option>`
      ).join('');
  }
  ```

- [ ] **T5.3** - Modificar `loadProfiles()` para cachear dados
  ```javascript
  async function loadProfiles() {
      const res = await fetch('/quality-profiles');
      const data = await res.json();
      
      // Cachear para uso no filtro
      window.cachedProfiles = data;
      
      // ... resto do código ...
      
      // Aplicar filtro inicial
      filterProfilesByEngine();
  }
  ```

- [ ] **T5.4** - Testar filtro dinâmico
  - Selecionar XTTS → Ver só profiles XTTS
  - Selecionar F5-TTS → Ver só profiles F5-TTS
  - Trocar engine → Select atualiza dinamicamente

### Critérios de Aceitação
- ✅ Select de profiles filtra por engine
- ✅ Mudança de engine atualiza profiles automaticamente
- ✅ Impossível selecionar profile incompatível
- ✅ Default sempre disponível

---

## 🟡 SPRINT 6 – VOICES: LIMPEZA E DECISÃO SOBRE REF_TEXT (1.5 dias)

### Objetivo
Decidir sobre `ref_text` e limpar página de Voices.

### Problemas Resolvidos
- 🔴 P0-6: Reference Text redundante
- 🟡 P1-3: Delete sem confirmação visual

### Decisão Técnica Necessária

**Opção A: Remover ref_text completamente**
- Whisper transcreve automaticamente
- UI mais simples
- Sem risco de inconsistência

**Opção B: Manter como override opcional**
- Usuários avançados podem corrigir transcrição
- Documentar claramente que Whisper é primário
- Adicionar toggle "Use custom transcription"

**Opção C: Mostrar transcrição Whisper (read-only)**
- UI mostra resultado do Whisper
- Usuário vê o que foi transcrito
- Sem edição

**RECOMENDAÇÃO:** Opção A (simplicidade) ou C (transparência)

### Tarefas (Assumindo Opção A)

- [ ] **T6.1** - Remover campo ref_text do backend
  ```python
  # app/main.py linha 589
  # Remover parâmetro ref_text da função clone_voice
  async def clone_voice(
      file: UploadFile = File(...),
      name: str = Form(...),
      language: str = Form(...),
      description: Optional[str] = Form(None),
      tts_engine: TTSEngine = Form(TTSEngine.XTTS),
      # ref_text: Optional[str] = Form(None)  # ❌ REMOVER
  ):
  ```

- [ ] **T6.2** - Remover campo ref_text da UI
  ```html
  <!-- Remover textarea de reference text -->
  ```

- [ ] **T6.3** - Adicionar mensagem de sucesso ao deletar voz
  ```javascript
  async function deleteVoice(id) {
      if (!confirm('Delete voice?')) return;
      try {
          await fetch('/voices/' + id, { method: 'DELETE' });
          msg('voice-msg', 'success', 'Voice deleted');  // ✅ Adicionar
          loadVoices();
      } catch (e) {
          msg('voice-msg', 'error', e.message);
      }
  }
  ```

- [ ] **T6.4** - Truncar IDs longos na listagem
  ```javascript
  <small style="color: var(--text-dim);">
      ID: ${v.voice_id.substring(0, 16)}...
  </small>
  ```

- [ ] **T6.5** - Adicionar elemento `<div id="voice-msg">` no DOM

- [ ] **T6.6** - Testar fluxo de voices
  - Clone voz sem ref_text → Whisper transcreve → Voz criada
  - Delete voz → Ver mensagem de sucesso

### Tarefas (Se escolher Opção C)

- [ ] **T6.1-ALT** - Adicionar campo read-only para mostrar transcrição
  ```html
  <div class="form-group">
      <label>Auto-transcription (Whisper)</label>
      <textarea id="voice-transcription" readonly 
                placeholder="Transcription will appear here after upload..."></textarea>
  </div>
  ```

- [ ] **T6.2-ALT** - Implementar preview da transcrição
  - Após upload, processar com Whisper
  - Mostrar resultado no textarea read-only
  - Usuário confirma ou cancela

### Critérios de Aceitação
- ✅ Decisão sobre ref_text implementada
- ✅ UI consistente com decisão
- ✅ Delete mostra mensagem de sucesso
- ✅ IDs truncados para melhor UX
- ✅ Mensagens de erro/sucesso funcionam

---

## 🟡 SPRINT 7 – MODE/PRESET: LÓGICA CONDICIONAL (1 dia)

### Objetivo
Implementar lógica condicional para Mode/Voice Preset/Voice ID.

### Problemas Resolvidos
- 🟡 P1-4: Sem lógica condicional Mode/Voice Preset
- 🟡 P1-5: Voice Preset sempre enviado

### Tarefas Frontend

- [ ] **T7.1** - Adicionar evento onchange no select de Mode
  ```javascript
  document.getElementById('tts-mode').addEventListener('change', function() {
      const mode = this.value;
      const presetDiv = document.querySelector('#tts-preset').closest('.form-group');
      const voiceIdDiv = document.querySelector('#tts-voice-id').closest('.form-group');
      
      if (mode === 'dubbing_with_clone') {
          presetDiv.style.display = 'none';
          voiceIdDiv.style.display = 'block';
      } else {
          presetDiv.style.display = 'block';
          voiceIdDiv.style.display = 'none';
      }
  });
  ```

- [ ] **T7.2** - Modificar `createTTSJob()` para enviar preset condicionalmente
  ```javascript
  const mode = document.getElementById('tts-mode').value;
  formData.append('mode', mode);
  
  if (mode === 'dubbing') {
      formData.append('voice_preset', document.getElementById('tts-preset').value);
  } else if (mode === 'dubbing_with_clone') {
      const voiceId = document.getElementById('tts-voice-id').value;
      if (!voiceId) {
          return msg('tts-msg', 'error', 'Select a cloned voice');
      }
      formData.append('voice_id', voiceId);
  }
  ```

- [ ] **T7.3** - Adicionar validação para Mode/Voice ID
  - Se mode = dubbing_with_clone e voice_id vazio → Erro
  - Se mode = dubbing e voice_preset vazio → Usar default

- [ ] **T7.4** - Testar lógica condicional
  - Selecionar "Generic Voice" → Ver Voice Preset, esconder Voice ID
  - Selecionar "Cloned Voice" → Ver Voice ID, esconder Voice Preset
  - Criar job em cada modo → Validar parâmetros enviados

### Critérios de Aceitação
- ✅ Voice Preset some quando mode = dubbing_with_clone
- ✅ Voice ID some quando mode = dubbing
- ✅ Validação exige voice_id em modo clone
- ✅ Voice Preset não enviado em modo clone
- ✅ Jobs criados corretamente em ambos os modos

---

## 🟢 SPRINT 8 – MELHORIAS E POLISH (1 dia)

### Objetivo
Implementar melhorias de UX e funcionalidades extras.

### Problemas Resolvidos
- 🟢 P2-1: Validação client-side
- 🟢 P2-4: Filtro por status em Jobs
- 🟢 P2-5: Paginação em Jobs

### Tarefas Frontend

- [ ] **T8.1** - Adicionar filtros na tab Jobs
  ```html
  <div style="margin-bottom: 12px;">
      <label>Filter by status:</label>
      <select id="jobs-status-filter" onchange="loadJobs()">
          <option value="">All</option>
          <option value="completed">Completed</option>
          <option value="processing">Processing</option>
          <option value="failed">Failed</option>
          <option value="pending">Pending</option>
      </select>
      <label style="margin-left: 16px;">Limit:</label>
      <select id="jobs-limit" onchange="loadJobs()">
          <option value="20">20</option>
          <option value="50" selected>50</option>
          <option value="100">100</option>
      </select>
  </div>
  ```

- [ ] **T8.2** - Modificar `loadJobs()` para aplicar filtros
  ```javascript
  const status = document.getElementById('jobs-status-filter').value;
  const limit = document.getElementById('jobs-limit').value;
  
  let jobs = data.jobs || [];
  if (status) {
      jobs = jobs.filter(j => j.status === status);
  }
  // Limitar manualmente se necessário
  ```

- [ ] **T8.3** - Adicionar validações nos formulários
  - Quality Profile: nome obrigatório, validar ranges
  - Voice Clone: nome obrigatório, arquivo obrigatório
  - RVC Upload: nome obrigatório, arquivo .pth obrigatório
  - TTS Job: texto obrigatório

- [ ] **T8.4** - Melhorar mensagens de erro
  - Erros de rede: "Network error. Check API connection."
  - Erros 400: Mostrar `detail` do backend
  - Erros 500: "Server error. Check logs."

- [ ] **T8.5** - Adicionar indicadores de loading
  - Spinner nos botões durante operações
  - Desabilitar botões durante fetch
  - Texto "Loading..." nos selects

### Critérios de Aceitação
- ✅ Filtros de Jobs funcionam
- ✅ Validações client-side previnem erros comuns
- ✅ Mensagens de erro são claras e úteis
- ✅ Indicadores de loading melhoram feedback

---

## 🧪 SPRINT 9 – QA FINAL E DOCUMENTAÇÃO (1 dia)

### Objetivo
Testar fluxo completo end-to-end e documentar.

### Tarefas

- [ ] **T9.1** - Teste E2E completo
  1. Criar profile XTTS → Sucesso
  2. Criar profile F5-TTS → Sucesso
  3. Editar profile → Sucesso
  4. Upload modelo RVC → Sucesso
  5. Clone voz → Sucesso
  6. Criar job TTS com:
     - Engine XTTS + Profile XTTS + RVC → Sucesso
     - Engine F5-TTS + Profile F5-TTS + Voz clonada → Sucesso
  7. Listar jobs → Ver todos os jobs
  8. Filtrar jobs por status → Ver filtrados
  9. Download áudio → Funciona
  10. Delete profile/voice/rvc/job → Funciona

- [ ] **T9.2** - Testar edge cases
  - Criar profile duplicado → Ver erro
  - Upload arquivo inválido → Ver erro
  - Selecionar profile incompatível → Impossível (filtrado)
  - Criar job sem texto → Ver erro
  - Network offline → Ver erro amigável

- [ ] **T9.3** - Verificar console do browser
  - Zero erros JavaScript
  - Zero warnings relevantes
  - Fetch calls com status codes corretos

- [ ] **T9.4** - Verificar logs backend
  - Operações logadas corretamente
  - Sem stack traces de erro
  - Validações funcionando

- [ ] **T9.5** - Atualizar documentação
  - README.md: Adicionar seção sobre WebUI
  - FORUIX.md: Atualizar se necessário
  - Comentar funções complexas no código

- [ ] **T9.6** - Criar guia de usuário básico (opcional)
  - Como criar profile
  - Como usar RVC
  - Como clonar voz
  - Como gerar áudio

### Critérios de Aceitação
- ✅ Teste E2E completo sem erros
- ✅ Edge cases tratados corretamente
- ✅ Console limpo
- ✅ Logs backend corretos
- ✅ Documentação atualizada
- ✅ WebUI 100% funcional

---

## 📊 CRONOGRAMA E ESTIMATIVAS

| Sprint | Dias | Acumulado | Prioridade |
|--------|------|-----------|------------|
| Sprint 0 | 0.5 | 0.5 | P0 |
| Sprint 1 | 2.0 | 2.5 | P0 |
| Sprint 2 | 1.0 | 3.5 | P1 |
| Sprint 3 | 2.0 | 5.5 | P0 |
| Sprint 4 | 1.5 | 7.0 | P0 |
| Sprint 5 | 1.0 | 8.0 | P0 |
| Sprint 6 | 1.5 | 9.5 | P0/P1 |
| Sprint 7 | 1.0 | 10.5 | P1 |
| Sprint 8 | 1.0 | 11.5 | P2 |
| Sprint 9 | 1.0 | 12.5 | QA |

**Estimativa Total: 12.5 dias úteis (~2.5 semanas)**

---

## 🎯 DEFINIÇÃO DE PRONTO (DoD)

Para cada sprint ser considerada concluída:

- ✅ Todos os tasks marcados como completos
- ✅ Código testado manualmente no browser
- ✅ API testada via Postman (quando aplicável)
- ✅ Console do browser sem erros
- ✅ Logs backend sem stack traces
- ✅ Mensagens de erro/sucesso funcionando
- ✅ Critérios de aceitação atendidos
- ✅ Código commitado com mensagem descritiva

---

## 🚀 PRÓXIMOS PASSOS

1. **Review deste plano** com stakeholders
2. **Decidir sobre ref_text** (Opção A/B/C) antes de Sprint 6
3. **Decidir sobre endpoint duplicado** antes de Sprint 1
4. **Iniciar Sprint 0** após aprovação
5. **Executar sprints sequencialmente** respeitando DoD

---

**FIM DO PLANO DE IMPLEMENTAÇÃO**

**Pronto para FASE 3: Implementação!**
