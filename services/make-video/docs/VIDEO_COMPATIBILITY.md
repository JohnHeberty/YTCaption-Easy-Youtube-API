# 🎬 Sistema de Compatibilização de Vídeos

**Status**: ✅ Produção  
**Versão**: 2.1.0  
**Data**: 2026-02-20

---

## 📋 Visão Geral

Sistema automático de detecção e correção de incompatibilidades de vídeo que garante que todos os vídeos usados na concatenação tenham as mesmas especificações (resolução, FPS, codec).

**Problema resolvido**: Jobs falhavam com `VideoIncompatibleException` quando vídeos com diferentes resoluções ou FPS eram concatenados.

**Solução**: Conversão automática in-place para HD 720p (1280x720 @ 30fps).

---

## 🎯 Características Principais

### 1. **Conversão In-Place** (Economia de Disco)
- ✅ **Sobrescreve originais** ao invés de criar cópias
- ✅ **Economia massiva**: 82% de redução de espaço (44M → 9.5M em testes)
- ✅ **Operação atômica**: Usa arquivo temporário + `shutil.move()`

### 2. **Configuração Flexível** (.env)
```env
TARGET_VIDEO_HEIGHT=720       # Altura padrão (HD 720p)
TARGET_VIDEO_WIDTH=1280       # Largura padrão
TARGET_VIDEO_FPS=30.0         # FPS padrão
TARGET_VIDEO_CODEC=h264       # Codec padrão
```

### 3. **Processamento Paralelo**
- ✅ **Máximo 3 conversões simultâneas** (asyncio.Semaphore)
- ✅ **Timeout de 5 minutos** por vídeo
- ✅ **FFmpeg com filtros otimizados** (scale, pad, fps)

### 4. **Integração Transparente**
- ✅ **Automático** no pipeline de video_builder
- ✅ **Manual** via comando `make compatibility DIR=...`
- ✅ **Zero configuração adicional** necessária

---

## 🔧 Uso

### Comando Makefile (Manual)

**Compatibilizar vídeos em um diretório**:
```bash
make compatibility DIR=data/approved/videos
```

**Verificar compatibilidade sem converter**:
```bash
make compatibility-check DIR=data/approved/videos
```

**Exemplo de saída**:
```
✅ Compatibilização concluída:
   Processados:      11 vídeos
   Convertidos:      9 vídeos (1080x1920 → 1280x720)
   Já compatíveis:   2 vídeos
   Erros:            0
```

### Integração Automática (Produção)

O sistema é **100% automático** durante a concatenação de vídeos:

```python
# Em app/services/video_builder.py
async def concatenate_videos_list(self, video_files: List[Path]) -> Path:
    # ✅ Garante compatibilidade ANTES de concatenar
    fixer = VideoCompatibilityFixer()
    video_files = await fixer.ensure_compatibility(
        video_paths=[Path(vf) for vf in video_files],
        output_dir=None,  # Conversão in-place
        target_spec=None,  # Usa defaults do .env (720p HD)
        force_reconvert=False
    )
    
    # Prossegue com concatenação (vídeos já compatíveis)
    return await self._concatenate_with_ffmpeg(video_files)
```

---

## 🏗️ Arquitetura

### Componentes

**1. VideoSpec** (Dataclass)
```python
@dataclass
class VideoSpec:
    width: int
    height: int
    fps: float
    codec: str
    audio_codec: str
    audio_sample_rate: int
    
    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}"
```

**2. VideoCompatibilityFixer** (Main Class)
```python
class VideoCompatibilityFixer:
    async def ensure_compatibility(
        self,
        video_paths: List[Path],
        output_dir: Optional[Path],
        target_spec: Optional[VideoSpec] = None,
        force_reconvert: bool = False
    ) -> List[Path]:
        # Detecta specs de todos os vídeos
        # Converte incompatíveis para HD 720p
        # Sobrescreve originais com conversão
        # Retorna mesmas paths (agora compatíveis)
```

**3. Conversão FFmpeg**
```bash
ffmpeg -y -i input.mp4 \
  -vf "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,fps=30.0" \
  -c:v h264 -preset medium -crf 23 \
  -c:a aac -ar 48000 -ac 2 -b:a 128k \
  output.mp4
```

---

## 📊 Fluxo de Conversão

```
┌─────────────────────────────────────────────────────────┐
│ 1. DETECÇÃO (ffprobe)                                   │
├─────────────────────────────────────────────────────────┤
│ video1.mp4: 1080x1920 @ 30fps → ❌ Incompatível         │
│ video2.mp4: 1280x720 @ 30fps  → ✅ Já compatível        │
│ video3.mp4: 640x480 @ 29.97fps → ❌ Incompatível        │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ 2. CONVERSÃO IN-PLACE (paralelo, max 3)                │
├─────────────────────────────────────────────────────────┤
│ video1.mp4 → .temp_conversion/temp_video1.mp4           │
│              (1080x1920 → 1280x720 @ 30fps)             │
│                                                          │
│ video3.mp4 → .temp_conversion/temp_video3.mp4           │
│              (640x480 → 1280x720 @ 30fps)               │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ 3. SUBSTITUIÇÃO ATÔMICA (shutil.move)                   │
├─────────────────────────────────────────────────────────┤
│ temp_video1.mp4 → video1.mp4 (SOBRESCREVE)             │
│ temp_video3.mp4 → video3.mp4 (SOBRESCREVE)             │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ 4. RESULTADO FINAL                                      │
├─────────────────────────────────────────────────────────┤
│ video1.mp4: 1280x720 @ 30fps ✅ (convertido)            │
│ video2.mp4: 1280x720 @ 30fps ✅ (já era compatível)    │
│ video3.mp4: 1280x720 @ 30fps ✅ (convertido)            │
│                                                          │
│ DISK: 9.5M (antes: 44M + 9.5M = 53.5M)                 │
│ ECONOMIA: 44M (82% de redução) 💾                       │
└─────────────────────────────────────────────────────────┘
```

---

## 🧪 Testes e Validação

### Cobertura de Testes: 16 testes (100% passing)

**TestVideoSpec** (3 testes)
- ✅ Propriedade resolution
- ✅ Aspect ratio 9:16 (vertical)
- ✅ Aspect ratio 16:9 (horizontal)

**TestVideoCompatibilityFixer** (10 testes)
- ✅ Vídeo único não precisa conversão
- ✅ VideoNotFoundException quando arquivo não existe
- ✅ Parsing de FPS (30/1 → 30.0, 29.97, etc.)
- ✅ Compatibilidade: mesmas specs
- ✅ Incompatibilidade: resoluções diferentes
- ✅ Tolerância de FPS (±0.5)
- ✅ Defaults em erro de detecção
- ✅ Target spec usa HD 720p do .env
- ✅ Conversão in-place com mock
- ✅ Edge cases

**TestReprocessingWorkflow** (3 testes)
- ✅ Diretório vazio retorna 0 processados
- ✅ Reprocessamento em lote
- ✅ Tratamento gracioso de erros

---

## 🎛️ Configuração Avançada

### Alterar Resolução Padrão

**Para 1080p**:
```env
TARGET_VIDEO_HEIGHT=1080
TARGET_VIDEO_WIDTH=1920
```

**Para 480p** (mobile):
```env
TARGET_VIDEO_HEIGHT=480
TARGET_VIDEO_WIDTH=854
```

### Desabilitar Conversão Automática

Não é recomendado, mas possível comentando linha no video_builder.py:
```python
# video_files = await fixer.ensure_compatibility(...)  # Desabilitado
```

---

## 📈 Métricas de Produção

### Teste Real (11 vídeos)

**Antes (sistema antigo)**:
```
data/approved/videos/           44M (originais 1080x1920)
data/approved/videos/compatible/ 9.5M (convertidos 1280x720)
TOTAL:                          53.5M
```

**Depois (conversão in-place)**:
```
data/approved/videos/           9.5M (convertidos 1280x720)
TOTAL:                          9.5M
ECONOMIA:                       44M (82% de redução) ✅
```

### Performance
- **Tempo médio por vídeo**: ~3-5 segundos (1080p → 720p)
- **Conversões paralelas**: 3 simultâneas
- **Timeout**: 5 minutos por vídeo
- **Taxa de sucesso**: 100% (9/9 conversões em teste real)

---

## 🔒 Segurança e Confiabilidade

### Operação Atômica
```python
# 1. Converter para arquivo temporário
temp_path = video_path.parent / ".temp_conversion" / f"temp_{video_path.name}"
await self._convert_and_replace(video_path, temp_path, target_spec)

# 2. Validar conversão
if not temp_path.exists():
    raise FFmpegFailedException("Output file not created")

# 3. Substituir original (operação atômica)
import shutil
shutil.move(str(temp_path), str(video_path))
```

### Cleanup Automático
- ✅ Diretório `.temp_conversion/` limpo após sucesso
- ✅ Arquivos temporários deletados em caso de erro
- ✅ Nenhum lixo deixado no filesystem

---

## 🐛 Troubleshooting

### Problema: "FFmpegFailedException: Output file not created"
**Causa**: FFmpeg falhou na conversão  
**Solução**: Verificar logs do FFmpeg, codec válido, espaço em disco

### Problema: "Timeout após 5 minutos"
**Causa**: Vídeo muito grande ou sistema lento  
**Solução**: Aumentar timeout ou reduzir resolução-alvo

### Problema: Qualidade baixa após conversão
**Causa**: CRF muito alto  
**Solução**: Modificar `-crf 23` para valor menor (15-18) em `_convert_and_replace()`

---

## 📚 Referências

- **Código**: `app/services/video_compatibility_fixer.py` (415 linhas)
- **Testes**: `tests/unit/services/test_video_compatibility_fixer.py` (16 testes)
- **Scripts**: 
  - `scripts/compatibility_fixer.py` (CLI para `make compatibility`)
  - `scripts/compatibility_checker.py` (CLI para `make compatibility-check`)
- **Configuração**: `.env` (TARGET_VIDEO_HEIGHT/WIDTH/FPS/CODEC)
- **Integração**: `app/services/video_builder.py` (linhas 155-180)

---

**Última Atualização**: 2026-02-20  
**Status**: ✅ Produção (validado com 11 vídeos reais)  
**Maintainer**: Sistema Make-Video v2.1.0
