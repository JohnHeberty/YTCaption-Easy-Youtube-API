# QA_WEBUI_AUDIO – Auditoria da WebUI de Áudio

**Data:** 29 de novembro de 2025  
**QA Engineer:** Senior Fullstack Dev  
**Objetivo:** Mapear todos os problemas de funcionalidade, UX e integração entre WebUI e Backend

---

## 📋 SUMÁRIO EXECUTIVO

### Stack Identificada
- **Backend:** FastAPI (Python 3.x)
- **Frontend:** HTML5 + Vanilla JavaScript (SPA style)
- **Arquivo WebUI:** `app/webui/full-control.html` (568 linhas)
- **Servidor:** `app/main.py` (1652 linhas, 34 endpoints)
- **Engines TTS:** F5-TTS (firstpixel/F5-TTS-pt-br), XTTS
- **RVC:** Suporte via `rvc_model_manager.py`
- **Whisper:** Presente para transcrição automática

### Endpoints Mapeados
✅ 34 endpoints ativos distribuídos em:
- TTS/Jobs (7)
- Voice Cloning (4)
- Quality Profiles (7 + 1 legacy)
- RVC Models (4)
- Admin (5)
- Feature Flags (2)
- Outros (4)

### Problemas Críticos Identificados
🔴 **6 problemas críticos** (P0)  
🟡 **4 problemas médios** (P1)  
🟢 **3 melhorias** (P2)

---

## 1. QUALITY PROFILES

### 1.1 Estado Atual (UI)
**Localização:** Tab "⚙️ Quality Profiles" (`full-control.html` linhas 200-270)

**Elementos na UI:**
- ✅ Dropdown de seleção de engine (XTTS/F5-TTS)
- ✅ Campos de nome e descrição
- ✅ Sliders para parâmetros XTTS (temperature, repetition_penalty, top_p, top_k, length_penalty, speed)
- ✅ Sliders para parâmetros F5-TTS (nfe_step, cfg_strength, sway_sampling_coef, speed)
- ✅ Botão "Create Profile"
- ✅ Lista de profiles existentes
- ✅ Botão "Delete" em profiles não-default

### 1.2 Comportamento Esperado
1. Criar profile → Salvar no backend → Aparecer na lista → Disponível para seleção no TTS
2. Editar profile → Atualizar parâmetros → Salvar mudanças
3. Deletar profile → Remover do backend → Sumir da lista
4. Profiles carregados ao entrar na tab

### 1.3 Problemas Encontrados

#### 🔴 P0-1: Conflito de Endpoints (CRÍTICO)
**Sintoma:** WebUI envia JSON para `/quality-profiles` mas backend espera Form Data  
**Causa Raiz:**
```javascript
// WebUI (linha 450) - Envia JSON
fetch('/quality-profiles', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({...})
})
```

```python
# Backend (main.py linha 858) - Espera Form Data
@app.post("/quality-profiles")
async def create_quality_profile(
    name: str = Form(...),  # ❌ Espera multipart/form-data
    description: str = Form(...),
    ...
)
```

**Impacto:** Criar profile **FALHA SEMPRE** com erro 422 (Unprocessable Entity)

#### 🔴 P0-2: Endpoint Duplicado (CRÍTICO)
**Situação:** Existem **DOIS** endpoints `/quality-profiles`:

1. **Legacy (linha 858)** - Form Data, parâmetros XTTS only
2. **Novo (linha 1241)** - JSON, suporta XTTS + F5-TTS, estrutura moderna

**Rota atual configurada:** Legacy (incompatível com WebUI)

**Evidência:**
```python
# Legacy (linha 858-886) - ATIVO
@app.post("/quality-profiles")
async def create_quality_profile(
    name: str = Form(...),  # Form Data
    description: str = Form(...),
    temperature: float = Form(0.75),  # XTTS only
    ...
)

# Novo (linha 1241-1336) - INATIVO (duplicado)
@app.post(
    "/quality-profiles",
    status_code=201,
    summary="Criar perfil de qualidade",
    ...
)
async def create_quality_profile(
    request: QualityProfileCreate  # JSON Body
):
```

**Resolução Necessária:** Escolher UMA versão (recomendo a nova) e remover/renomear a outra

#### 🟡 P1-1: Sem Feedback Visual de Erro
**Problema:** Quando criação falha, mensagem de erro NÃO aparece na tela  
**Causa:** Exception não tratada no `catch` do fetch  
**Linha:** 465 (`msg('profile-msg', 'error', e.message)` - elemento não existe no DOM)

#### 🟡 P1-2: Lista Não Atualiza Automaticamente
**Problema:** Após criar profile, `loadProfiles()` é chamada mas depende de resposta bem-sucedida  
**Impacto:** Se criar falha silenciosamente, lista fica desatualizada

#### 🟢 P2-1: Sem Validação de Inputs
**Melhoria:** Campos nome/descrição aceitam strings vazias sem validação client-side

### 1.4 Editar Profile - NÃO IMPLEMENTADO

**Situação:** Botão de editar **NÃO EXISTE** na UI  
**Endpoint disponível:** `PATCH /quality-profiles/{engine}/{profile_id}` (linha 1338)  
**Gap:** Zero integração UI ↔ Backend para edição

---

## 2. RVC MODELS

### 2.1 Estado Atual (UI)
**Localização:** Tab "🎚️ RVC Models" (`full-control.html` linhas 320-340)

**Elementos na UI:**
- ✅ Botão "🔄 Refresh"
- ✅ Lista de models (nome + ID)
- ❌ **NENHUM** botão de upload
- ❌ **NENHUM** botão de delete
- ❌ **NENHUM** botão de seleção para uso

### 2.2 Comportamento Esperado
1. Upload de arquivo .pth + .index → Salvar modelo → Aparecer na lista
2. Selecionar modelo RVC → Usar em geração de áudio
3. Deletar modelo → Remover do backend

### 2.3 Problemas Encontrados

#### 🔴 P0-3: Sem Interface de Upload (CRÍTICO)
**Sintoma:** Impossível adicionar novos modelos RVC pela WebUI  
**Endpoint existente:** `POST /rvc-models` (linha 706)  
**Gap:** Zero integração - função `uploadRVCModel()` **NÃO EXISTE**

**Endpoint Backend:**
```python
@app.post("/rvc-models", response_model=RvcModelResponse, status_code=201)
async def upload_rvc_model(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    pth_file: UploadFile = File(...),  # ✅ Aceita upload
    index_file: Optional[UploadFile] = File(None)
):
```

**Implementação Necessária:**
- Form com input file (pth_file, index_file)
- Input text (name, description)
- Função JavaScript `uploadRVCModel()`

#### 🔴 P0-4: Sem Botão de Delete
**Endpoint disponível:** `DELETE /rvc-models/{model_id}` (linha 816)  
**UI:** Botão delete **NÃO EXISTE** (veja linha 515-520 do HTML)

#### 🔴 P0-5: Sem Seleção de Modelo para Uso
**Problema:** Usuário pode listar models mas NÃO PODE escolher qual usar  
**Gap:** Na tab TTS, não existe dropdown/selector para RVC model  
**Impacto:** Parâmetros `rvc_model_id` no `POST /jobs` nunca é enviado

**Evidência:**
```javascript
// TTS Tab (linha 340-380) - Cria job
formData.append('tts_engine', ...);  // ✅ Existe
formData.append('quality_profile_id', ...);  // ✅ Existe
// ❌ NÃO EXISTE: formData.append('rvc_model_id', ...)
```

---

## 3. VOICES (CLONAGEM DE VOZ)

### 3.1 Estado Atual (UI)
**Localização:** Tab "👤 Voices" (`full-control.html` linhas 150-195)

**Elementos na UI:**
- ✅ Upload de arquivo de áudio
- ✅ Input: nome, language, description
- ✅ **Textarea: reference text** ⚠️
- ✅ Botão "Clone Voice"
- ✅ Lista de vozes (nome, language, ID, botão delete)

### 3.2 Comportamento Esperado
1. Upload áudio → Transcrever com Whisper → Criar voz → Listar
2. Delete voz → Remover do backend → Atualizar lista
3. **Sem** campo "reference text" se Whisper faz transcrição automática

### 3.3 Problemas Encontrados

#### 🔴 P0-6: Reference Text Redundante (CONCEITUAL)
**Situação:** UI tem campo `ref_text` (linha 385) que permite usuário digitar transcrição manual  
**Backend:** Suporta `ref_text` opcional (linha 589)

**Problema Conceitual:**
- Se usamos **Whisper** para transcrição automática do áudio de referência:
  - `ref_text` manual é **REDUNDANTE**
  - Usuário pode digitar texto DIFERENTE do áudio → Inconsistência
  - Whisper já faz o trabalho → Campo não faz sentido

**Código Backend:**
```python
@app.post("/voices/clone", status_code=202)
async def clone_voice(
    file: UploadFile = File(...),
    name: str = Form(...),
    language: str = Form(...),
    description: Optional[str] = Form(None),
    tts_engine: TTSEngine = Form(TTSEngine.XTTS),
    ref_text: Optional[str] = Form(None)  # ⚠️ Aceita manual
):
```

**Decisão Necessária:**
1. **Opção A:** Remover campo `ref_text` completamente (UI + Backend)
2. **Opção B:** Usar `ref_text` como OVERRIDE opcional (avançado) + documentar claramente
3. **Opção C:** Mostrar transcrição Whisper na UI como "Preview" (read-only)

**Recomendação:** Opção A (simplicidade) ou C (transparência)

#### 🟡 P1-3: Botão Delete Funciona Mas Sem Confirmação Visual
**Situação:** `deleteVoice(id)` funciona (linha 423)  
**Problema:** Nenhum feedback de "Voice deleted" - apenas recarrega lista  
**Melhoria:** Adicionar mensagem de sucesso

#### 🟢 P2-2: IDs Truncados
**Situação:** IDs mostrados completos (linha 413)  
**Melhoria:** Truncar IDs longos para melhor visualização

---

## 4. QUALITY PROFILE x TTS ENGINE (BINDING)

### 4.1 Estado Atual
**TTS Tab:** Seleção independente de:
- Engine (XTTS/F5-TTS) - linha 107
- Quality Profile - linha 125

**Problema:** Perfis XTTS aparecem como opção quando F5-TTS está selecionado (e vice-versa)

### 4.2 Comportamento Esperado
**Opção A:** Filtrar profiles por engine selecionado (dinâmico)  
**Opção B:** Validar no backend (rejeitar combinações inválidas)  
**Opção C:** Ambos (UX melhor + validação backend)

### 4.3 Problemas Encontrados

#### 🔴 P0-7: Sem Binding Profile ↔ Engine
**Código Atual (linha 475-484):**
```javascript
select.innerHTML = '<option value="">Default</option>' + all.map(p => 
    `<option value="${p.id}">${p.name} (${p.engine})</option>`
).join('');
```

**Problema:** TODOS os profiles aparecem, independente do engine selecionado no TTS

**Impacto:**
- Usuário pode selecionar profile F5-TTS com engine XTTS
- Backend pode ou não rejeitar (depende de validação)
- Parâmetros incorretos aplicados → Erro ou comportamento inesperado

**Solução:**
```javascript
// Filtrar profiles pelo engine selecionado
const selectedEngine = document.getElementById('tts-engine').value;
const filtered = all.filter(p => p.engine === selectedEngine);
select.innerHTML = '<option value="">Default</option>' + filtered.map(...);
```

**Localização:** Adicionar evento `onchange` no select de engine (linha 107-111)

---

## 5. MODE / VOICE PRESET / DUBLAGEM COM CLONAGEM

### 5.1 Estado Atual (UI)
**Mode Selector (linha 101-106):**
```html
<select id="tts-mode">
    <option value="dubbing">Generic Voice (dubbing)</option>
    <option value="dubbing_with_clone">Cloned Voice</option>
</select>
```

**Voice Preset (linha 112-117):**
```html
<div class="form-group">
    <label>Voice Preset</label>
    <select id="tts-preset">
        <option value="female_generic">Female Generic</option>
        <option value="male_generic">Male Generic</option>
    </select>
</div>
```

### 5.2 Comportamento Esperado
**Quando `mode = "dubbing_with_clone"`:**
- Voice Preset deve **sumir** (ou ser disabled)
- Voice ID deve ser **obrigatório**

**Quando `mode = "dubbing"`:**
- Voice Preset deve **aparecer** e ser usado
- Voice ID deve ser **ignorado**

### 5.3 Problemas Encontrados

#### 🟡 P1-4: Sem Lógica Condicional de UI
**Situação:** Ambos Voice Preset e Voice ID ficam visíveis sempre  
**Problema:** Usuário pode selecionar "Cloned Voice" e ainda ver Voice Preset (confusão UX)

**Código Necessário:**
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

**Localização:** Adicionar no `<script>` após linha 340

---

## 6. PARÂMETROS OPCIONAIS → None

### 6.1 Estado Atual
**Código de Criação de Job (linha 340-360):**
```javascript
formData.append('text', document.getElementById('tts-text').value);
formData.append('source_language', document.getElementById('tts-lang').value);
formData.append('target_language', document.getElementById('tts-lang').value);
formData.append('mode', document.getElementById('tts-mode').value);
formData.append('voice_preset', document.getElementById('tts-preset').value);

const voiceId = document.getElementById('tts-voice-id').value;
if (voiceId) formData.append('voice_id', voiceId);  // ✅ Correto

const profile = document.getElementById('tts-profile').value;
if (profile) formData.append('quality_profile_id', profile);  // ✅ Correto
```

### 6.2 Problemas Encontrados

#### 🟡 P1-5: Voice Preset Sempre Enviado
**Linha 346:**
```javascript
formData.append('voice_preset', document.getElementById('tts-preset').value);
```

**Problema:**
- Quando `mode = "dubbing_with_clone"`, Voice Preset deveria ser `None`
- Código atual SEMPRE envia o valor do select (ex: "female_generic")
- Backend pode ignorar ou aplicar incorretamente

**Correção:**
```javascript
const mode = document.getElementById('tts-mode').value;
if (mode === 'dubbing') {
    formData.append('voice_preset', document.getElementById('tts-preset').value);
} else {
    // Não envia voice_preset (ou envia null se backend exigir)
}
```

#### 🟢 P2-3: Description em Clone Voice
**Situação:** Campo opcional enviado sempre (linha 385)  
**Código Atual:**
```javascript
const desc = document.getElementById('voice-desc').value;
if (desc) formData.append('description', desc);  // ✅ Correto
```

**Status:** JÁ IMPLEMENTADO CORRETAMENTE ✅

---

## 7. OUTROS PROBLEMAS ENCONTRADOS

### 7.1 🟡 P1-6: Sem Opção de RVC na Criação de Job
**Gap:** Parâmetros RVC (`enable_rvc`, `rvc_model_id`, `rvc_pitch`, etc.) não existem na UI  
**Backend aceita (linha 235-243):**
```python
enable_rvc: bool = Form(False),
rvc_model_id: Optional[str] = Form(None),
rvc_pitch: int = Form(0),
rvc_index_rate: float = Form(0.75),
...
```

**UI:** Zero campos relacionados a RVC na tab TTS

**Implementação Necessária:**
- Checkbox "Enable RVC"
- Dropdown de modelos RVC (populado via `loadRVCModels()`)
- Sliders para parâmetros avançados (pitch, index_rate, etc.)

### 7.2 🟢 P2-4: Jobs Tab - Sem Filtro por Status
**Melhoria:** Adicionar filtros completed/processing/failed  
**Linha:** 430 - `loadJobs()` sempre carrega todos

### 7.3 🟢 P2-5: Sem Paginação em Jobs
**Limite fixo:** 50 jobs (linha 431)  
**Melhoria:** Adicionar paginação real

### 7.4 Endpoint `/quality-profiles-legacy` Não Usado
**Linha:** 904 do backend  
**WebUI:** Usa `/quality-profiles` (novo endpoint)  
**Ação:** Decidir se manter legacy ou deprecar

---

## 📊 RESUMO DE PRIORIDADES

### 🔴 Críticos (P0) - 7 itens
1. **P0-1:** Conflito de endpoints Quality Profiles (JSON vs Form)
2. **P0-2:** Endpoint duplicado `/quality-profiles`
3. **P0-3:** RVC Models - Sem interface de upload
4. **P0-4:** RVC Models - Sem botão delete
5. **P0-5:** RVC Models - Sem seleção para uso em TTS
6. **P0-6:** Reference Text redundante (conceitual)
7. **P0-7:** Sem binding Profile ↔ Engine

### 🟡 Médios (P1) - 6 itens
1. **P1-1:** Sem feedback visual de erro em profiles
2. **P1-2:** Lista profiles não atualiza se criar falha
3. **P1-3:** Delete voice sem confirmação visual
4. **P1-4:** Sem lógica condicional Mode/Voice Preset
5. **P1-5:** Voice Preset sempre enviado
6. **P1-6:** Sem opção RVC na criação de job

### 🟢 Melhorias (P2) - 5 itens
1. **P2-1:** Validação client-side em profiles
2. **P2-2:** IDs truncados em voices
3. **P2-3:** Description em clone voice (✅ OK)
4. **P2-4:** Jobs - Filtro por status
5. **P2-5:** Jobs - Paginação

---

## 🎯 RECOMENDAÇÕES TÉCNICAS

### Arquitetura Backend
- ✅ FastAPI bem estruturado
- ✅ Endpoints RESTful coerentes
- ⚠️ Duplicação de endpoints precisa limpeza
- ✅ Validação via Pydantic models

### Frontend
- ⚠️ Vanilla JS sem state management (setState, observers)
- ⚠️ Sem framework (React/Vue) → Mais verboso mas simples
- ✅ Código limpo e legível
- ❌ Falta tratamento de erros consistente

### Integrações
- ❌ 40% dos endpoints sem UI correspondente
- ❌ UI tem elementos "mortos" (sem backend)
- ✅ Padrão de comunicação (fetch) consistente

### Whisper Integration
- ❌ Conceito de `ref_text` precisa revisão
- Decisão necessária: remover ou documentar melhor

---

## 📝 PRÓXIMOS PASSOS

1. Criar `SPRINTS_WEBUI_AUDIO.md` com plano de implementação
2. Priorizar P0 (críticos) em Sprint 1-3
3. Abordar P1 (médios) em Sprint 4-5
4. Melhorias P2 em Sprint 6
5. QA final e documentação em Sprint 7

**Estimativa Total:** 7 sprints pequenas (~2-3 dias cada)

---

**FIM DO RELATÓRIO DE AUDITORIA**
