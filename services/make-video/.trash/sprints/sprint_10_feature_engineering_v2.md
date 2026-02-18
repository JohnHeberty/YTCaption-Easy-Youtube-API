# Sprint 10: Feature Engineering V2 - Features Visuais Avançadas

**Duração:** 4-5 dias  
**Dependências:** Sprints 01-09 (especialmente Sprint 04 - Feature Extraction V1)  
**Objetivo:** Adicionar features visuais avançadas para melhorar robustez do classificador em edge cases (top subtitles, low contrast, stylized text).

---

## Contexto & Motivação

### Problema Atual

Sprint 04 implementou **15 features base** extraídas por frame:
- Spatial: 5 features (bbox dimensions, areas, aspect ratios)
- Text: 3 features (length, char types)
- Confidence: 5 features (mean, std, min/max OCR confidence)
- Positional: 2 features (Y position, bottom coverage)

Agregadas por vídeo (mean/std/max) → **45 features espaciais**

Sprint 05 adicionou **11 features temporais** → **Total V1: 56 features**

**Limitações das Features V1 (Sprints 04-05)**:

```
┌─────────────────────────────────────────────────────────────────┐
│ CASOS ONDE V1 FEATURES FALHAM (do baseline Sprint 00)          │
├─────────────────────────────────────────────────────────────────┤
│ 1. TOP SUBTITLES (10 vídeos, recall 40%):                      │
│    → Features posicionais focam em bottom (Y > 70%)            │
│    → Top subs (Y < 30%) têm features "invertidas"              │
│    → Modelo não captura "dual-mode" (top + bottom)             │
│                                                                 │
│ 2. BAIXO CONTRASTE (40 vídeos, F1 59%):                        │
│    → Brightness/contrast features globais, não locais           │
│    → Legends com fundo escuro vs claro não diferenciadas        │
│    → OCR confidence baixa → features temporal fracas            │
│                                                                 │
│ 3. STYLIZED TEXT (colorido, outlined, sombras):                │
│    → Não capturamos "estilo" de legenda (cor, borda, sombra)   │
│    → Bbox pode ser largo (outline) mas texto estreito           │
│    → Features V1 tratam tudo como "texto branco simples"        │
│                                                                 │
│ 4. MULTI-LINE SUBTITLES (2-3 linhas simultâneas):              │
│    → Features temporais assumem 1 bbox/frame                    │
│    → Multi-line gera múltiplos bboxes próximos                  │
│    → Spatial clustering não captura "line groups"               │
│                                                                 │
│ 5. SHORT-DURATION CAPTIONS (<2s, flash text):                  │
│    → Temporal features baseadas em "runs" quebram               │
│    → Frame consistency assume persistência longa                │
│    → Flash captions legítimas tratadas como noise               │
└─────────────────────────────────────────────────────────────────┘
```

**Análise de Erros (Holdout Test Set - Sprint 00):**

```python
# Análise dos 200 vídeos de teste (baseline Sprint 00)

Falsos Negativos (22 vídeos, Recall = 78%):
  - 6 vídeos: Top subtitles (ROI sem fallback perdeu)
  - 8 vídeos: Baixo contraste (OCR conf < 0.50, features fracas)
  - 4 vídeos: Stylized text (colorido, outlined - bbox estranho)
  - 2 vídeos: Multi-line subs (clustering falhou)
  - 2 vídeos: Flash captions (<2s, temporal features zeros)

Falsos Positivos (14 vídeos, Precision = 88%):
  - 8 vídeos: Text de HUD/menu (alto em
4. **Visual Avançado**: OCR confidence, scene changes, color histograms

---

## Métrica Impactada

| Métrica | Sprint 04-05 (V1 - 56 features) | Sprint 10 (V2 - 70 features) | Impacto | Status |
|---------|------------------------------|------------------------------|---------|--------|
| **F1 Score** | ~93.5% | ~95.0% (projetado) | ✅ +1.5pp | 🟢 |
| **Recall** | ~92.0% | ~94.5% (projetado) | ✅ +2.5pp (menos FN) | 🟢 |
| **Precision** | ~95.0% | ~95.5% (projetado) | ✅ +0.5pp | 🟢 |
| **FN (200 videos)** | 8 vídeos | 5 vídeos (projetado) | ✅ -37.5% FN | 🟢 |
| **FP (200 videos)** | 3 vídeos | 2 vídeos (projetado) | ✅ -33% FP | 🟢 |
| **Feature Count** | 56 features | 70 features (+14) | ✅ +25% sinais visuais | 🟢 |
| **Feature Engineering Time** | ~5s/vídeo | ~8s/vídeo (+3s) | ⚠️ +60% tempo (aceitável) | 🟡 |

**Trade-off**: Features V2 adiciona ~3s/vídeo processamento (análise visual avançada). Ainda viável:
- Throughput: 100 vídeos/min → 70 vídeos/min (suficiente)
- Custo: +$0.005/vídeo (processamento adicional)
- Benefício: -37.5% FN em edge cases visuais (top subs, low contrast, stylized text)

**Definição de Sucesso:**

Sprint 10 **ACEITA** se:
- F1 ≥94.5% em test set (200 vídeos)
- Recall ≥94.0% (prioridade: reduzir FN em edge cases visuais)
- Feature engineering time <10s/vídeo (viável para produção)
- Backward compatible: pode rollback para V1 features (56) se V2 falhar

---

## Arquitetura de Feature Engineering V2

### Visão Geral

```
┌────────────────────────────────────────────────────────────────────────────┐
│ FEATURE ENGINEERING V2 PIPELINE                                            │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  [Input: Video File]                                                       │
│         │                                                                  │
│         ├──────> [V1 Features - Sprint 02] (56 features, 5s)              │
│         │           ├─> Visual: brightness, contrast, resolution           │
│         │           ├─> Temporal: duration, fps, frame_count               │
│         │           ├─> Audio: has_audio, bitrate                          │
│         │           └─> Metadata: filesize                                 │
│         │                                                                  │
│         ├──────> [V2 Audio Features] (15 features, 8s)                    │
│         │           ├─> Spectrograma (energy, entropy)                     │
│         │           ├─> MFCC (13 coefficients)                             │
│         │           ├─> Speech detection (prob_speech)                     │
│         │           └─> Audio fingerprinting (chromagram)                  │
│         │                                                                  │
│         ├──────> [V2 NLP Features] (12 features, 1s)                      │
│         │           ├─> Título TF-IDF (top 5 keywords)                     │
│         │           ├─> Embedding similarity (title vs "subtitle")         │
│         │           ├─> Keyword match (has "legenda", "subtitle", etc)     │
│         │           └─> Description length, language                       │
│         │                                                                  │
│         ├──────> [V2 Visual Avançado] (8 features, 3s)                    │
│         │           ├─> OCR confidence (avg_text_confidence)               │
│         │           ├─> Scene changes (n_scene_changes)                    │
│         │           ├─> Color histogram (hist_red, hist_green, hist_blue)  │
│         │           └─> Edge density (sharpness)                           │
│         │                                                                  │
│         └──────> [V2 Metadata Temporal] (5 features, 0.5s)                │
│                     ├─> upload_date (days_since_upload)                    │
│                     ├─> views_growth_rate                                  │
│                     ├─> trending_score                                     │
│                     └─> platform_version (YouTube API version)             │
│                                                                            │
│  [Output: 96 features total]                                               │
│     V1: 56 features                                                        │
│     V2: 40 features (15 audio + 12 NLP + 8 visual + 5 temporal)            │
└────────────────────────────────────────────────────────────────────────────┘
```

**Total time**: ~17s/vídeo (vs 5s V1) - aceitável para produção.

---

## Tarefas do Sprint 10

### 1. Audio Features V2 (15 features)

**Motivação**: Podcasts e vídeos audio-heavy têm características únicas (ritmo de fala, pausa, música de fundo) que correlacionam com presença de legendas.

---

#### 1.1) Spectrograma (Energy & Entropy)

```python
# app/feature_engineering/audio_v2.py

import librosa
import numpy as np

class AudioFeaturesV2:
    """
    Features avançadas de áudio usando librosa.
    """
    
    @staticmethod
    def extract_spectral_features(audio_path: str) -> dict:
        """
        Extrai features do espectrograma (energia, entropia).
        
        Returns:
            {
              'spectral_centroid_mean': float,
              'spectral_centroid_std': float,
              'spectral_rolloff_mean': float,
              'spectral_bandwidth_mean': float,
              'spectral_entropy': float
            }
        """
        
        # Load audio (librosa)
        y, sr = librosa.load(audio_path, sr=22050, duration=60)  # Primeiros 60s
        
        # Spectral centroid (onde está a "massa" da frequência)
        # Valores altos: voz aguda, música eletrônica
        # Valores baixos: voz grave, música clássica
        spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        
        # Spectral rolloff (até qual freq está 85% da energia)
        spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, roll_percent=0.85)[0]
        
        # Spectral bandwidth (largura do espectro)
        spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)[0]
        
        # Spectral entropy (quão "organizado" é o som)
        # Alta entropia: ruído, ambiente caótico
        # Baixa entropia: voz humana, música estruturada
        S = np.abs(librosa.stft(y))
        p = S / S.sum(axis=0, keepdims=True)
        spectral_entropy = -np.sum(p * np.log2(p + 1e-10), axis=0).mean()
        
        return {
            'spectral_centroid_mean': float(spectral_centroid.mean()),
            'spectral_centroid_std': float(spectral_centroid.std()),
            'spectral_rolloff_mean': float(spectral_rolloff.mean()),
            'spectral_bandwidth_mean': float(spectral_bandwidth.mean()),
            'spectral_entropy': float(spectral_entropy)
        }
```

**Intuição**:
- Vídeos com fala humana clara (podcasts, tutoriais) → **maior chance de legenda**
- `spectral_centroid`: Fala humana ≈ 2000-3000 Hz
- `spectral_entropy`: Fala estruturada → baixa entropia

**Tempo**: ~2s por vídeo (60s de áudio).

---

#### 1.2) MFCC (Mel-Frequency Cepstral Coefficients)

```python
    @staticmethod
    def extract_mfcc(audio_path: str, n_mfcc: int = 13) -> dict:
        """
        Extrai MFCCs (feature padrão para reconhecimento de voz).
        
        MFCCs capturam características da fala humana.
        Usado em: speech recognition, speaker identification.
        
        Returns:
            {
              'mfcc_1_mean': float,
              'mfcc_1_std': float,
              ...
              'mfcc_13_mean': float,
              'mfcc_13_std': float
            }
        """
        
        y, sr = librosa.load(audio_path, sr=22050, duration=60)
        
        # MFCC (13 coefficients)
        mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=n_mfcc)
        
        features = {}
        for i in range(n_mfcc):
            features[f'mfcc_{i+1}_mean'] = float(mfccs[i].mean())
            features[f'mfcc_{i+1}_std'] = float(mfccs[i].std())
        
        return features
```

**Intuição**:
- MFCCs são **fingerprint** da voz humana
- Se MFCC similar a padrões de fala → provável tem legenda
- 13 coefficients × 2 (mean, std) = **26 features**

**Redução**: Usar apenas **top 5 MFCCs** mais informativos (via feature importance de Sprint 06) para evitar overfitting.

```python
# Selecionar top-5 MFCCs por importância (após treino inicial)
top_mfcc_indices = [1, 2, 3, 5, 8]  # Determinado empiricamente

features_reduced = {
    f'mfcc_{i}_mean': features[f'mfcc_{i}_mean']
    for i in top_mfcc_indices
}
# Total: 5 features (mean only, ignorar std para simplificar)
```

**Tempo**: ~3s por vídeo.

---

#### 1.3) Speech Detection (Probabilidade de Fala)

```python
    @staticmethod
    def detect_speech(audio_path: str) -> dict:
        """
        Detecta presença de fala humana (vs música, ruído).
        
        Usa VAD (Voice Activity Detection) via WebRTC.
        
        Returns:
            {
              'prob_speech': float,  # 0-1
              'speech_duration_ratio': float  # % do áudio que é fala
            }
        """
        
        import webrtcvad
        import wave
        
        # Load audio como WAV (WebRTC VAD requer PCM)
        audio = AudioSegment.from_file(audio_path)
        audio = audio.set_frame_rate(16000).set_channels(1)  # Mono, 16kHz
        wav_path = '/tmp/audio_temp.wav'
        audio.export(wav_path, format='wav')
        
        # VAD
        vad = webrtcvad.Vad(mode=2)  # Mode 2: balance entre sensibilidade/especificidade
        
        with wave.open(wav_path, 'rb') as wf:
            sample_rate = wf.getframerate()
            frames = wf.readframes(wf.getnframes())
        
        # Dividir áudio em chunks de 30ms
        frame_duration = 30  # ms
        frame_length = int(sample_rate * frame_duration / 1000) * 2  # 2 bytes/sample
        
        speech_frames = 0
        total_frames = 0
        
        for i in range(0, len(frames) - frame_length, frame_length):
            frame = frames[i:i+frame_length]
            if len(frame) < frame_length:
                break
            
            is_speech = vad.is_speech(frame, sample_rate)
            speech_frames += int(is_speech)
            total_frames += 1
        
        prob_speech = speech_frames / total_frames if total_frames > 0 else 0.0
        
        return {
            'prob_speech': float(prob_speech),
            'speech_duration_ratio': float(prob_speech)  # Alias para clareza
        }
```

**Intuição**:
- Vídeos com **>50% de fala** → alta probabilidade de legenda
- Vídeos com música/ruído → baixa probabilidade

**Tempo**: ~2s por vídeo.

---

#### 1.4) Chromagram (Tonalidade Musical)

```python
    @staticmethod
    def extract_chroma_features(audio_path: str) -> dict:
        """
        Extrai chromagram (distribuição de notas musicais).
        
        Útil para distinguir:
          - Música de fundo (chroma distribuído) vs Fala (chroma concentrado)
        
        Returns:
            {
              'chroma_stft_mean': float,
              'chroma_stft_std': float
            }
        """
        
        y, sr = librosa.load(audio_path, sr=22050, duration=60)
        
        # Chromagram (12 pitch classes: C, C#, D, ..., B)
        chroma = librosa.feature.chroma_stft(y=y, sr=sr)
        
        return {
            'chroma_stft_mean': float(chroma.mean()),
            'chroma_stft_std': float(chroma.std())
        }
```

**Intuição**:
- Fala humana: chroma concentrado (poucas notas)
- Música: chroma distribuído (várias notas)

**Tempo**: ~1s por vídeo.

---

**Total Audio V2 Features**: 15 features
- Spectral: 5 features (centroid, rolloff, bandwidth, entropy)
- MFCC: 5 features (top-5 reduced)
- Speech: 2 features (prob_speech, duration_ratio)
- Chroma: 2 features (mean, std)
- **Zero-crossing rate**: 1 feature (taxa de mudança de sinal → voz vs música)

**Total time**: ~8s por vídeo.

---

### 2. NLP Features (12 features)

**Motivação**: Títulos como "Tutorial de legendas" → provável tem legenda. "Vlog sem edição" → provável não tem.

---

#### 2.1) TF-IDF sobre Títulos

```python
# app/feature_engineering/nlp_features.py

from sklearn.feature_extraction.text import TfidfVectorizer
import re

class NLPFeatures:
    """
    Features baseadas em texto (títulos, descrições).
    """
    
    def __init__(self):
        # TF-IDF pre-fitted em dataset de treino
        self.tfidf = TfidfVectorizer(
            max_features=100,  # Top-100 palavras mais informativas
            stop_words='english',
            ngram_range=(1, 2)  # Unigrams + bigrams
        )
        # Assumindo já fitted em Sprint 02 (treino inicial)
    
    def extract_tfidf_features(self, title: str) -> dict:
        """
        Extrai top-5 TF-IDF scores do título.
        
        Returns:
            {
              'tfidf_1': float,  # Score da palavra mais relevante
              'tfidf_2': float,
              ...
              'tfidf_5': float
            }
        """
        
        if not title:
            return {f'tfidf_{i+1}': 0.0 for i in range(5)}
        
        # Transformar título
        tfidf_vec = self.tfidf.transform([title]).toarray()[0]
        
        # Top-5 scores
        top_indices = np.argsort(tfidf_vec)[-5:][::-1]
        
        return {
            f'tfidf_{i+1}': float(tfidf_vec[idx]) if idx < len(tfidf_vec) else 0.0
            for i, idx in enumerate(top_indices)
        }
```

**Intuição**:
- Palavras como "subtitle", "legenda", "captions" → TF-IDF alto → provável tem legenda
- Palavras genéricas → TF-IDF baixo

**Tempo**: <0.1s por vídeo.

---

#### 2.2) Embedding Similarity (Title vs "Subtitle")

```python
    def extract_embedding_similarity(self, title: str) -> dict:
        """
        Calcula similaridade entre título e palavra "subtitle".
        
        Usa Sentence-BERT (modelo pré-treinado).
        
        Returns:
            {
              'title_subtitle_similarity': float  # Cosine similarity 0-1
            }
        """
        
        from sentence_transformers import SentenceTransformer, util
        
        # Modelo lightweight (all-MiniLM-L6-v2, 80MB)
        model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Embeddings
        emb_title = model.encode(title, convert_to_tensor=True)
        emb_subtitle = model.encode("subtitle caption closed captions", convert_to_tensor=True)
        
        # Cosine similarity
        similarity = util.cos_sim(emb_title, emb_subtitle).item()
        
        return {
            'title_subtitle_similarity': float(similarity)
        }
```

**Intuição**:
- Título "How to add subtitles" → similarity ≈ 0.8 → provável tem legenda
- Título "Unboxing my new phone" → similarity ≈ 0.1 → provável não tem

**Tempo**: ~0.5s por vídeo (inferência Sentence-BERT).

---

#### 2.3) Keyword Matching

```python
    @staticmethod
    def extract_keyword_features(title: str, description: str) -> dict:
        """
        Verifica presença de keywords específicas.
        
        Keywords relacionados a legendas:
          - "subtitle", "caption", "CC", "subtitles", "legenda", "legendado"
          - "closed captions", "SDH" (Subtitles for Deaf and Hard of hearing)
        
        Returns:
            {
              'has_subtitle_keyword': int,  # 0 ou 1
              'has_caption_keyword': int,
              'has_cc_keyword': int,
              'subtitle_keyword_count': int  # Quantas vezes aparece
            }
        """
        
        text = (title + " " + description).lower()
        
        keywords = {
            'subtitle': ['subtitle', 'subtitles', 'legenda', 'legendado'],
            'caption': ['caption', 'captions', 'closed captions'],
            'cc': ['cc', 'sdh']
        }
        
        features = {}
        total_count = 0
        
        for key, patterns in keywords.items():
            count = sum(text.count(pattern) for pattern in patterns)
            features[f'has_{key}_keyword'] = int(count > 0)
            total_count += count
        
        features['subtitle_keyword_count'] = total_count
        
        return features
```

**Tempo**: <0.01s por vídeo.

---

#### 2.4) Text Length & Language

```python
    @staticmethod
    def extract_text_metadata(title: str, description: str) -> dict:
        """
        Metadata sobre texto (comprimento, idioma).
        
        Returns:
            {
              'title_length': int,
              'description_length': int,
              'title_language': str,  # 'en', 'pt', 'es', etc
              'is_english': int  # 0 ou 1
            }
        """
        
        from langdetect import detect
        
        # Language detection
        try:
            title_lang = detect(title) if title else 'unknown'
        except:
            title_lang = 'unknown'
        
        return {
            'title_length': len(title),
            'description_length': len(description),
            'is_english': int(title_lang == 'en')
        }
```

**Intuição**:
- Títulos longos (>100 chars) → vídeos profissionais → mais provável legenda
- Inglês → YouTube US → maior taxa de legendas

**Tempo**: <0.1s por vídeo.

---

**Total NLP Features**: 12 features
- TF-IDF: 5 features
- Embedding: 1 feature
- Keywords: 4 features (has_subtitle, has_caption, has_cc, count)
- Text metadata: 2 features (title_length, is_english)

**Total time**: ~0.7s por vídeo.

---

### 3. Visual Features V2 (8 features)

**Motivação**: OCR pode detectar "texto queimado" no vídeo (legendas hardcoded), scene changes indicam edição profissional.

---

#### 3.1) OCR Confidence

```python
# app/feature_engineering/visual_v2.py

import pytesseract
from PIL import Image

class VisualFeaturesV2:
    """
    Features visuais avançadas.
    """
    
    @staticmethod
    def extract_ocr_features(video_path: str, n_frames: int = 10) -> dict:
        """
        Aplica OCR em frames aleatórios, mede confidence.
        
        Vídeos com legendas hardcoded (texto queimado) → OCR confidence alto.
        
        Returns:
            {
              'avg_ocr_confidence': float,  # 0-100
              'max_ocr_confidence': float,
              'has_text_overlay': int  # 1 se confidence > 50 em algum frame
            }
        """
        
        # Sample frames
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_indices = np.linspace(0, total_frames - 1, n_frames, dtype=int)
        
        confidences = []
        
        for idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret:
                continue
            
            # Convert to PIL Image
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            
            # OCR com confidence
            ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            
            # Média de confidence das palavras detectadas
            word_confidences = [
                int(conf) for conf in ocr_data['conf'] if conf != '-1'
            ]
            
            if word_confidences:
                confidences.append(np.mean(word_confidences))
        
        cap.release()
        
        if not confidences:
            return {
                'avg_ocr_confidence': 0.0,
                'max_ocr_confidence': 0.0,
                'has_text_overlay': 0
            }
        
        return {
            'avg_ocr_confidence': float(np.mean(confidences)),
            'max_ocr_confidence': float(np.max(confidences)),
            'has_text_overlay': int(np.max(confidences) > 50)
        }
```

**Intuição**:
- Vídeos com legendas hardcoded → OCR detecta texto → confidence alto → **provável tem legenda**
- PORÉM: OCR não diferencia "legenda" de "texto aleatório" (logo, watermark) → feature adicional, não definitiva

**Tempo**: ~2s por vídeo (10 frames).

---

#### 3.2) Scene Changes

```python
    @staticmethod
    def detect_scene_changes(video_path: str) -> dict:
        """
        Detecta mudanças de cena (transições, cortes).
        
        Vídeos editados profissionalmente → mais scene changes → mais provável legenda.
        
        Returns:
            {
              'n_scene_changes': int,
              'scene_change_rate': float  # Changes por segundo
            }
        """
        
        from scenedetect import VideoManager, SceneManager
        from scenedetect.detectors import ContentDetector
        
        video_manager = VideoManager([video_path])
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector(threshold=30))
        
        video_manager.start()
        scene_manager.detect_scenes(frame_source=video_manager)
        
        scene_list = scene_manager.get_scene_list()
        n_scenes = len(scene_list)
        
        duration = video_manager.get_duration().get_seconds()
        scene_change_rate = n_scenes / duration if duration > 0 else 0.0
        
        video_manager.release()
        
        return {
            'n_scene_changes': int(n_scenes),
            'scene_change_rate': float(scene_change_rate)
        }
```

**Intuição**:
- Vlogs caseiros: poucas scene changes (1 take contínuo) → menos provável legenda
- Vídeos profissionais: muitas scene changes (edição) → mais provável legenda

**Tempo**: ~1s por vídeo.

---

#### 3.3) Color Histogram (Distribuição de Cores)

```python
    @staticmethod
    def extract_color_histogram(video_path: str, n_frames: int = 5) -> dict:
        """
        Calcula histograma de cores (RGB).
        
        Returns:
            {
              'hist_red_mean': float,
              'hist_green_mean': float,
              'hist_blue_mean': float
            }
        """
        
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_indices = np.linspace(0, total_frames - 1, n_frames, dtype=int)
        
        histograms = {'red': [], 'green': [], 'blue': []}
        
        for idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret:
                continue
            
            # Histograma para cada canal
            hist_r = cv2.calcHist([frame], [2], None, [256], [0, 256])
            hist_g = cv2.calcHist([frame], [1], None, [256], [0, 256])
            hist_b = cv2.calcHist([frame], [0], None, [256], [0, 256])
            
            histograms['red'].append(hist_r.mean())
            histograms['green'].append(hist_g.mean())
            histograms['blue'].append(hist_b.mean())
        
        cap.release()
        
        return {
            'hist_red_mean': float(np.mean(histograms['red'])) if histograms['red'] else 0.0,
            'hist_green_mean': float(np.mean(histograms['green'])) if histograms['green'] else 0.0,
            'hist_blue_mean': float(np.mean(histograms['blue'])) if histograms['blue'] else 0.0
        }
```

**Intuição**:
- Vídeos com color grading profissional → histograma balanceado → mais provável legenda
- Vídeos caseiros → histograma desbalanceado (ex: muito azul - webcam)

**Tempo**: ~0.5s por vídeo.

---

**Total Visual V2 Features**: 8 features
- OCR: 3 features
- Scene changes: 2 features
- Color histogram: 3 features

**Total time**: ~3.5s por vídeo.

---

### 4. Metadata Temporal (5 features)

**Motivação**: Vídeos recentes (2023+) → formato novo (WebVTT) → mais legendas. Vídeos trending → profissionais → mais legendas.

---

```python
# app/feature_engineering/temporal_features.py

from datetime import datetime

class TemporalFeatures:
    """
    Features temporais (upload date, views growth).
    """
    
    @staticmethod
    def extract_temporal_features(metadata: dict) -> dict:
        """
        Extrai features temporais do metadata do vídeo.
        
        Args:
            metadata: {
              'upload_date': '2024-12-25',
              'view_count': 10000,
              'like_count': 500,
              'comment_count': 100
            }
        
        Returns:
            {
              'days_since_upload': int,
              'views_per_day': float,
              'engagement_rate': float,  # (likes + comments) / views
              'is_recent_video': int,  # 1 se upload < 30 dias
              'is_old_video': int  # 1 se upload > 2 anos
            }
        """
        
        upload_date_str = metadata.get('upload_date', '2020-01-01')
        upload_date = datetime.strptime(upload_date_str, '%Y-%m-%d')
        days_since_upload = (datetime.now() - upload_date).days
        
        view_count = metadata.get('view_count', 0)
        like_count = metadata.get('like_count', 0)
        comment_count = metadata.get('comment_count', 0)
        
        views_per_day = view_count / days_since_upload if days_since_upload > 0 else 0.0
        engagement_rate = (like_count + comment_count) / view_count if view_count > 0 else 0.0
        
        return {
            'days_since_upload': int(days_since_upload),
            'views_per_day': float(views_per_day),
            'engagement_rate': float(engagement_rate),
            'is_recent_video': int(days_since_upload < 30),
            'is_old_video': int(days_since_upload > 730)  # 2 anos
        }
```

**Intuição**:
- Vídeos recentes → formato novo → mais legendas
- High engagement → vídeos profissionais → mais legendas
- Vídeos antigos (>2 anos) → formato antigo (SRT) → menos legendas

**Tempo**: <0.1s por vídeo (metadata já disponível).

---

**Total Temporal Features**: 5 features

**Total time**: ~0.1s por vídeo.

---

## Schema V2 (Feature Schema Update)

**CRITICAL**: Schema freeze (Sprint 06) precisa ser atualizado.

```python
# app/model_training/schemas/feature_schema_v2.json

{
  "version": "2.0",
  "n_features": 96,
  "feature_groups": {
    "v1_visual": {
      "features": ["brightness", "contrast", "resolution", ...],  # 20 features
      "source": "Sprint 02"
    },
    "v1_temporal": {
      "features": ["duration", "fps", "frame_count", ...],  # 15 features
      "source": "Sprint 02"
    },
    "v1_audio": {
      "features": ["has_audio", "audio_bitrate", ...],  # 8 features
      "source": "Sprint 02"
    },
    "v1_metadata": {
      "features": ["filesize", "codec", ...],  # 13 features
      "source": "Sprint 02"
    },
    "v2_audio": {
      "features": [
        "spectral_centroid_mean", "spectral_centroid_std",
        "spectral_rolloff_mean", "spectral_bandwidth_mean", "spectral_entropy",
        "mfcc_1_mean", "mfcc_2_mean", "mfcc_3_mean", "mfcc_5_mean", "mfcc_8_mean",
        "prob_speech", "speech_duration_ratio",
        "chroma_stft_mean", "chroma_stft_std",
        "zero_crossing_rate"
      ],  # 15 features
      "source": "Sprint 10"
    },
    "v2_nlp": {
      "features": [
        "tfidf_1", "tfidf_2", "tfidf_3", "tfidf_4", "tfidf_5",
        "title_subtitle_similarity",
        "has_subtitle_keyword", "has_caption_keyword", "has_cc_keyword", "subtitle_keyword_count",
        "title_length", "is_english"
      ],  # 12 features
      "source": "Sprint 10"
    },
    "v2_visual": {
      "features": [
        "avg_ocr_confidence", "max_ocr_confidence", "has_text_overlay",
        "n_scene_changes", "scene_change_rate",
        "hist_red_mean", "hist_green_mean", "hist_blue_mean"
      ],  # 8 features
      "source": "Sprint 10"
    },
    "v2_temporal": {
      "features": [
        "days_since_upload", "views_per_day", "engagement_rate",
        "is_recent_video", "is_old_video"
      ],  # 5 features
      "source": "Sprint 10"
    }
  },
  "total_features": 96,
  "backward_compatible": true,  # V1 features (56) são subset de V2
  "feature_types": {
    "numeric": 91,
    "binary": 5
  }
}
```

---

## Retraining com Features V2

### Abordagem 1: Full Retraining (Recomendada)

```python
# Retreinar modelo DO ZERO com 96 features

X_train_v2 = engineer_features_v2(train_videos)  # 96 features
model_v2 = train_model(X_train_v2, y_train)
```

**PROS**:
- Modelo aprende correlações entre features V1 + V2
- Performance máxima

**CONS**:
- Requer retreino completo (~1-2h)

---

### Abordagem 2: Feature Augmentation (Fallback)

```python
# Carregar modelo V1 (56 features), adicionar V2 como "features extras"
# ⚠️ NÃO RECOMENDADO - apenas para emergência

model_v1 = load_model_v1()  # 56 features
X_v1 = X_train[:, :56]
X_v2_extra = X_train[:, 56:]

# Treinar modelo auxiliar V2 (só features novas)
model_v2_extra = train_model(X_v2_extra, y_train)

# Ensemble: average probabilities
y_proba = 0.7 * model_v1.predict_proba(X_v1)[:, 1] + \
          0.3 * model_v2_extra.predict_proba(X_v2_extra)[:, 1]
```

**Decisão**: Usar **Full Retraining** (Abordagem 1).

---

## Backward Compatibility

**Desafio**: Produção atual usa 56 features. Como migrar para 96 sem breaking changes?

**Solução**: Feature flag + gradual rollout.

```python
# app/feature_engineering/pipeline.py

class FeatureEngineeringPipeline:
    def __init__(self, version: str = 'v1'):
        """
        Args:
            version: 'v1' (56 features) ou 'v2' (96 features)
        """
        self.version = version
    
    def transform(self, video_path: str) -> np.ndarray:
        if self.version == 'v1':
            return self._extract_v1_features(video_path)  # 56 features
        elif self.version == 'v2':
            features_v1 = self._extract_v1_features(video_path)  # 56
            features_v2_extra = self._extract_v2_features(video_path)  # 40
            return np.concatenate([features_v1, features_v2_extra])  # 96
        else:
            raise ValueError(f"Unknown version: {self.version}")
```

**Rollout Strategy**:
1. Deploy modelo V2 como **canary** (10% traffic) - usa 96 features
2. Modelo V1 continua servindo 90% traffic - usa 56 features
3. Após 4h sem issues → promote V2 to 100%

---

## Testes

### Test 1: Feature Extraction Performance

```python
# tests/test_feature_extraction_v2.py

def test_audio_features_v2_performance():
    """Verifica que audio V2 features <10s por vídeo."""
    
    video_path = 'tests/fixtures/sample_video.mp4'
    
    start = time.time()
    features = AudioFeaturesV2.extract_spectral_features(video_path)
    features.update(AudioFeaturesV2.extract_mfcc(video_path))
    features.update(AudioFeaturesV2.detect_speech(video_path))
    features.update(AudioFeaturesV2.extract_chroma_features(video_path))
    elapsed = time.time() - start
    
    assert elapsed < 10.0, f"Audio V2 extraction too slow: {elapsed:.2f}s"
    assert len(features) == 15, "Expected 15 audio V2 features"


def test_nlp_features_performance():
    """Verifica que NLP features <1s."""
    
    title = "How to add subtitles to YouTube videos"
    description = "Tutorial showing step-by-step process..."
    
    nlp = NLPFeatures()
    
    start = time.time()
    features = nlp.extract_tfidf_features(title)
    features.update(nlp.extract_embedding_similarity(title))
    features.update(nlp.extract_keyword_features(title, description))
    features.update(nlp.extract_text_metadata(title, description))
    elapsed = time.time() - start
    
    assert elapsed < 1.0, f"NLP extraction too slow: {elapsed:.2f}s"
    assert len(features) == 12, "Expected 12 NLP features"
```

---

### Test 2: Model Performance (F1 Improvement)

```python
# tests/test_model_v2_performance.py

def test_model_v2_improves_f1():
    """Verifica que modelo V2 (96 features) > modelo V1 (56 features)."""
    
    # Load test set
    X_test_v1 = load_test_features_v1()  # 56 features
    X_test_v2 = load_test_features_v2()  # 96 features
    y_test = load_test_labels()
    
    # Load models
    model_v1 = joblib.load('models/model_v1.pkl')
    model_v2 = joblib.load('models/model_v2.pkl')
    
    # Evaluate
    y_pred_v1 = model_v1.predict(X_test_v1)
    y_pred_v2 = model_v2.predict(X_test_v2)
    
    f1_v1 = f1_score(y_test, y_pred_v1)
    f1_v2 = f1_score(y_test, y_pred_v2)
    
    print(f"F1 V1: {f1_v1:.4f}")
    print(f"F1 V2: {f1_v2:.4f}")
    
    # Assert improvement
    assert f1_v2 >= f1_v1 + 0.005, f"V2 should improve F1 by at least 0.5pp"


def test_model_v2_reduces_false_negatives():
    """Verifica que V2 reduz FN (podcasts, vídeos silenciosos)."""
    
    # Load apenas casos de FN do modelo V1
    fn_cases_v1 = load_false_negative_cases_v1()  # 5 vídeos
    
    X_fn_v2 = engineer_features_v2(fn_cases_v1)
    model_v2 = joblib.load('models/model_v2.pkl')
    
    y_pred_v2 = model_v2.predict(X_fn_v2)
    
    # Espera que ao menos 60% dos FN sejam corrigidos
    corrected = sum(y_pred_v2)
    assert corrected >= 3, f"Expected at least 3/5 FN corrected, got {corrected}/5"
```

---

## Estrutura de Arquivos

```
services/make-video/
├── app/
│   └── feature_engineering/
│       ├── pipeline_v2.py              # Main pipeline (v1 + v2) (~200 linhas)
│       ├── audio_v2.py                 # Audio features V2 (~300 linhas)
│       ├── nlp_features.py             # NLP features (~250 linhas)
│       ├── visual_v2.py                # Visual features V2 (~200 linhas)
│       └── temporal_features.py        # Temporal features (~100 linhas)
├── app/model_training/
│   └── schemas/
│       └── feature_schema_v2.json      # Schema V2 (96 features) (~150 linhas)
├── scripts/
│   ├── migrate_v1_to_v2.sh             # Migration script (~100 linhas)
│   └── benchmark_features_v2.py        # Benchmark extraction time (~150 linhas)
└── tests/
    ├── test_audio_v2.py                # Unit tests (~200 linhas)
    ├── test_nlp_features.py            # Unit tests (~200 linhas)
    ├── test_visual_v2.py               # Unit tests (~150 linhas)
    ├── test_temporal_features.py       # Unit tests (~100 linhas)
    ├── test_model_v2_performance.py    # Integration test (~250 linhas)
    └── fixtures/
        ├── podcast_video.mp4           # Test case: podcast (FN in V1)
        └── silent_video_with_text.mp4  # Test case: silent + text overlay (FN in V1)

**Total**: ~2,100 linhas de código (feature engineering + testes).
```

---

## Definição de Sucesso (Sprint 10)

Sprint 10 **ACEITA** se:

✅ **F1 Score melhora**:
  - F1 ≥ 98.5% (vs 97.8% em V1)
  - Improvement ≥ 0.7pp (estatisticamente significativo)

✅ **Recall melhora (prioridade FN)**:
  - Recall ≥ 98.5% (vs 97.5% em V1)
  - Ao menos 60% dos FN cases corrigidos (3/5 vídeos)

✅ **Feature extraction time aceitável**:
  - Total time <20s/vídeo (vs 5s V1)
  - Throughput ≥ 40 vídeos/min (suficiente para produção)

✅ **Backward compatibility**:
  - Modelo V1 (56 features) continua funcionando
  - Rollback para V1 possível se V2 falhar

✅ **Schema validation**:
  - Schema V2 (96 features) validado (Great Expectations)
  - Features sem missing values >5%

---

## Próximos Passos (Após Sprint 10)

- **Sprint 11**: Model Explainability (SHAP values, entender por que modelo prediz X)
- **Sprint 12**: Cost Optimization (reduzir tempo de feature extraction, quantization)
- **Sprint 13**: Multi-Model Ensemble (combinar LightGBM + XGBoost + NN)

---

## Referências

- [Librosa Documentation](https://librosa.org/doc/latest/index.html) (audio features)
- [Sentence-BERT](https://www.sbert.net/) (text embeddings)
- [PySceneDetect](https://pyscenedetect.readthedocs.io/) (scene detection)
- Sprint 02: Feature Engineering V1 (56 features baseline)
- Sprint 06: Schema Freeze & Feature Selection

---

**Status**: 📋 Documentation Complete  
**Próximo Sprint**: Sprint 11 (Model Explainability)
