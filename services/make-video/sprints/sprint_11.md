# Sprint Pack 11/12 - ASS Neon Pipeline + Font Management

**Escopo deste pack:** Implementar geração de ASS com preset neon 2-layer (NeonGlow + NeonText), correção de style_key mapping sem double underscore (MUST-FIX v1.6), cores ASS 8-digit &H00FFFFFF& (MUST-FIX), FontManager com fallback chain, burn_subtitles com flags FFmpeg corretos (MUST-FIX).

## Índice

- [S-123: Criar estrutura ASSGenerator](#s-123)
- [S-124: Implementar neon_preset com 2 layers](#s-124)
- [S-125: Corrigir style_key mapping sem double underscore (MUST-FIX)](#s-125)
- [S-126: Implementar cores ASS 8-digit (MUST-FIX)](#s-126)
- [S-127: Criar FontManager com fallback chain](#s-127)
- [S-128: Implementar font detection automática](#s-128)
- [S-129: Implementar generate_ass_file](#s-129)
- [S-130: Implementar burn_subtitles com flags corretos (MUST-FIX)](#s-130)
- [S-131: Validar path escaping no burn_subtitles](#s-131)
- [S-132: Criar testes de geração ASS](#s-132)
- [S-133: Validar cores ASS formato correto](#s-133)
- [S-134: Validar burn_subtitles não trava](#s-134)

---

<a name="s-123"></a>
## S-123: Criar estrutura ASSGenerator

**Objetivo:** Criar classe base para geração de arquivos ASS com preset neon.

**Escopo (IN/OUT):**
- **IN:** Classe e métodos skeleton
- **OUT:** Não implementar lógica ainda

**Arquivos tocados:**
- `services/make-video/app/ass_generator.py`

**Mudanças exatas:**
- Criar arquivo:
  ```python
  import logging
  from typing import List, Dict
  import os
  
  logger = logging.getLogger(__name__)
  
  class ASSGenerator:
      """
      Gerador de legendas ASS com preset neon (2-layer)
      
      Layers:
      1. NeonGlow: Background glow (cyan blur)
      2. NeonText: Foreground text (white crisp)
      """
      
      def __init__(self, font_name: str = 'Arial', font_size: int = 48):
          self.font_name = font_name
          self.font_size = font_size
          
          logger.info("ass_generator_initialized", font=font_name, size=font_size)
      
      def generate_ass_file(self, subtitles: list, output_path: str, preset: str = 'neon'):
          """Gera arquivo ASS com preset especificado"""
          pass
      
      def _neon_preset(self) -> str:
          """Retorna [V4+ Styles] para preset neon"""
          pass
      
      def _format_subtitle_line(self, subtitle: dict, layer: int, style: str) -> str:
          """Formata linha de legenda ASS"""
          pass
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Classe criada
- [ ] 3 métodos skeleton
- [ ] Docstrings adicionadas
- [ ] Logger configurado

**Testes:**
- Unit: `tests/test_ass_generator.py::test_class_initialization()`

**Observabilidade:**
- Log: `logger.info("ass_generator_initialized", ...)`

**Riscos/Rollback:**
- Risco: Nenhum
- Rollback: N/A

**Dependências:** S-001

---

<a name="s-124"></a>
## S-124: Implementar neon_preset com 2 layers

**Objetivo:** Implementar método que gera definições de estilos ASS para preset neon (2 camadas).

**Escopo (IN/OUT):**
- **IN:** Preset neon com glow + text
- **OUT:** Não implementar outros presets ainda

**Arquivos tocados:**
- `services/make-video/app/ass_generator.py`

**Mudanças exatas:**
- Implementar método:
  ```python
  def _neon_preset(self) -> str:
      """
      Preset neon: 2-layer subtitle
      
      Layer 0 (NeonGlow): Cyan blur para efeito glow
      Layer 1 (NeonText): White text crisp
      """
      
      # Cores ASS: &HAABBGGRR& (alpha, blue, green, red)
      # Serão corrigidas em S-126 para formato 8-digit
      
      styles = f"""[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding

Style: NeonGlow,{self.font_name},{self.font_size},&H00FFFF00,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,8,0,5,10,10,20,1
Style: NeonText,{self.font_name},{self.font_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,2,0,5,10,10,20,1
"""
      return styles
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] 2 estilos definidos: NeonGlow, NeonText
- [ ] NeonGlow: Outline=8 (blur forte)
- [ ] NeonText: Outline=2 (borda normal)
- [ ] Alignment=5 (center bottom) - corrigido de =2 em S-018
- [ ] MarginV=20 (distância do fundo)

**Testes:**
- Unit: `tests/test_ass_generator.py::test_neon_preset_structure()`

**Observabilidade:**
- N/A (geração de conteúdo)

**Riscos/Rollback:**
- Risco: Cores hardcoded não customizáveis
- Rollback: Adicionar parâmetros de cor

**Dependências:** S-123

---

<a name="s-125"></a>
## S-125: Corrigir style_key mapping sem double underscore (MUST-FIX)

**Objetivo:** Corrigir bug onde style_key é mapeado com double underscore incorreto (MUST-FIX v1.6).

**Escopo (IN/OUT):**
- **IN:** Corrigir mapping de layer → style name
- **OUT:** Não modificar formato ASS

**Arquivos tocados:**
- `services/make-video/app/ass_generator.py`

**Mudanças exatas:**
- Implementar mapping correto:
  ```python
  def _get_style_name(self, layer: int) -> str:
      """
      Mapeia layer para nome do estilo
      
      MUST-FIX v1.6: Usar mapping correto sem double underscore
      
      Layer 0 → NeonGlow
      Layer 1 → NeonText
      """
      
      # CORRETO (MUST-FIX)
      style_map = {
          0: 'NeonGlow',
          1: 'NeonText'
      }
      
      # INCORRETO (bug comum):
      # style_key = f"Neon__Glow"  # double underscore errado
      
      return style_map.get(layer, 'NeonText')  # Default: NeonText
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Mapping explícito com dict
- [ ] Sem double underscore
- [ ] Layer 0 → NeonGlow
- [ ] Layer 1 → NeonText
- [ ] Default para layer desconhecido

**Testes:**
- Unit: `tests/test_ass_generator.py::test_style_mapping_no_double_underscore()`

**Observabilidade:**
- N/A (correção de bug)

**Riscos/Rollback:**
- Risco: Nenhum
- Rollback: N/A

**Dependências:** S-124

---

<a name="s-126"></a>
## S-126: Implementar cores ASS 8-digit (MUST-FIX)

**Objetivo:** Corrigir formato de cores ASS para 8 dígitos hexadecimais &H00FFFFFF& (MUST-FIX v1.6).

**Escopo (IN/OUT):**
- **IN:** Formato correto 8-digit
- **OUT:** Não implementar conversão de cores RGB

**Arquivos tocados:**
- `services/make-video/app/ass_generator.py`

**Mudanças exatas:**
- Corrigir cores no `_neon_preset()`:
  ```python
  def _neon_preset(self) -> str:
      """
      Preset neon com cores ASS corretas
      
      MUST-FIX v1.6: Formato 8-digit &HAABBGGRR&
      - AA: Alpha (00 = opaco, FF = transparente)
      - BB: Blue
      - GG: Green
      - RR: Red
      """
      
      # Cores corretas (8-digit)
      cyan_glow = '&H00FFFF00'  # Alpha=00 (opaco), Cyan (BB=FF, GG=FF, RR=00)
      white_text = '&H00FFFFFF'  # Alpha=00 (opaco), White (BB=FF, GG=FF, RR=FF)
      black_outline = '&H00000000'  # Black
      semi_transparent_back = '&H80000000'  # Alpha=80 (semi-transparente), Black
      
      styles = f"""[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding

Style: NeonGlow,{self.font_name},{self.font_size},{cyan_glow},{white_text},{black_outline},{semi_transparent_back},1,0,0,0,100,100,0,0,1,8,0,5,10,10,20,1
Style: NeonText,{self.font_name},{self.font_size},{white_text},{white_text},{black_outline},{semi_transparent_back},1,0,0,0,100,100,0,0,1,2,0,5,10,10,20,1
"""
      return styles
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Cores no formato &H00FFFFFF& (8 dígitos)
- [ ] Cyan: &H00FFFF00
- [ ] White: &H00FFFFFF
- [ ] Black: &H00000000
- [ ] Semi-transparent: &H80000000

**Testes:**
- Unit: `tests/test_ass_generator.py::test_ass_colors_8_digit()`

**Observabilidade:**
- N/A (correção de formato)

**Riscos/Rollback:**
- Risco: Formato incorreto causa erro no FFmpeg
- Rollback: Validar com FFmpeg antes de deploy

**Dependências:** S-124, S-125

---

<a name="s-127"></a>
## S-127: Criar FontManager com fallback chain

**Objetivo:** Criar gerenciador de fontes que detecta fontes disponíveis e usa fallback.

**Escopo (IN/OUT):**
- **IN:** Fallback chain de fontes
- **OUT:** Não implementar download de fontes

**Arquivos tocados:**
- `services/make-video/app/font_manager.py`

**Mudanças exatas:**
- Criar arquivo:
  ```python
  import os
  import logging
  from typing import Optional, List
  
  logger = logging.getLogger(__name__)
  
  class FontManager:
      """
      Gerenciador de fontes com fallback
      
      Fallback chain:
      1. Font especificada pelo usuário
      2. Fonts populares (Arial, Helvetica, DejaVu)
      3. Fallback sistema
      """
      
      # Paths comuns de fontes no Linux
      FONT_PATHS = [
          '/usr/share/fonts',
          '/usr/local/share/fonts',
          '~/.fonts',
      ]
      
      # Fallback chain
      FALLBACK_FONTS = [
          'Arial',
          'Helvetica',
          'DejaVu Sans',
          'Liberation Sans',
          'Noto Sans',
      ]
      
      def __init__(self):
          self.available_fonts = self._scan_fonts()
          logger.info("font_manager_initialized", fonts_found=len(self.available_fonts))
      
      def _scan_fonts(self) -> List[str]:
          """Escaneia sistema para fontes disponíveis"""
          # Simplificado: assume fc-list disponível
          import subprocess
          try:
              result = subprocess.run(
                  ['fc-list', ':', 'family'],
                  capture_output=True,
                  text=True,
                  timeout=5
              )
              
              fonts = set()
              for line in result.stdout.split('\n'):
                  if line.strip():
                      # fc-list retorna: "Font Name,Alternative Name"
                      font = line.split(',')[0].strip()
                      fonts.add(font)
              
              return list(fonts)
          
          except Exception as e:
              logger.warning(f"Font scan failed: {e}")
              return []
      
      def get_font(self, preferred: Optional[str] = None) -> str:
          """
          Retorna fonte disponível
          
          Args:
              preferred: Fonte preferida (opcional)
          
          Returns:
              Nome da fonte a usar
          """
          # Tentar preferida
          if preferred and preferred in self.available_fonts:
              logger.info(f"using_preferred_font", font=preferred)
              return preferred
          
          # Fallback chain
          for fallback in self.FALLBACK_FONTS:
              if fallback in self.available_fonts:
                  logger.info(f"using_fallback_font", font=fallback, preferred=preferred)
                  return fallback
          
          # Último recurso: usar primeira disponível
          if self.available_fonts:
              font = self.available_fonts[0]
              logger.warning(f"using_first_available_font", font=font)
              return font
          
          # Desespero: hardcode
          logger.error("no_fonts_found_using_hardcoded")
          return 'Arial'
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Escaneia fontes com fc-list
- [ ] Fallback chain implementado
- [ ] Retorna primeira disponível se nenhuma do fallback
- [ ] Hardcode 'Arial' em último caso

**Testes:**
- Unit: `tests/test_font_manager.py::test_font_manager_scan()`
- Unit: `tests/test_font_manager.py::test_get_font_preferred()`
- Unit: `tests/test_font_manager.py::test_get_font_fallback()`

**Observabilidade:**
- Log: `logger.info("font_manager_initialized", fonts_found=...)`
- Log: `logger.info("using_fallback_font", font=..., preferred=...)`

**Riscos/Rollback:**
- Risco: fc-list não disponível em ambiente
- Rollback: Assumir Arial sempre disponível

**Dependências:** S-001

---

<a name="s-128"></a>
## S-128: Implementar font detection automática

**Objetivo:** Integrar FontManager no ASSGenerator para detecção automática.

**Escopo (IN/OUT):**
- **IN:** Detecção automática no init
- **OUT:** Não implementar caching de fontes

**Arquivos tocados:**
- `services/make-video/app/ass_generator.py`

**Mudanças exatas:**
- Modificar `__init__`:
  ```python
  from app.font_manager import FontManager
  
  def __init__(self, font_name: str = None, font_size: int = 48):
      # Detecção automática de fonte
      font_manager = FontManager()
      self.font_name = font_manager.get_font(preferred=font_name)
      self.font_size = font_size
      
      logger.info("ass_generator_initialized", font=self.font_name, size=font_size)
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] FontManager usado no init
- [ ] Fonte preferida passada como parâmetro
- [ ] Fallback automático se preferida não disponível
- [ ] Log indica fonte escolhida

**Testes:**
- Unit: `tests/test_ass_generator.py::test_font_auto_detection()`

**Observabilidade:**
- Log: `logger.info("ass_generator_initialized", font=...)`

**Riscos/Rollback:**
- Risco: FontManager lento causa latência no init
- Rollback: Cachear resultado

**Dependências:** S-127, S-123

---

<a name="s-129"></a>
## S-129: Implementar generate_ass_file

**Objetivo:** Implementar geração completa de arquivo ASS com header, styles e eventos.

**Escopo (IN/OUT):**
- **IN:** Geração completa do arquivo
- **OUT:** Não implementar validação de subtítulos

**Arquivos tocados:**
- `services/make-video/app/ass_generator.py`

**Mudanças exatas:**
- Implementar métodos:
  ```python
  def _format_timestamp(self, seconds: float) -> str:
      """
      Formata timestamp para ASS: H:MM:SS.CC
      
      Exemplo: 65.5 → 0:01:05.50
      """
      hours = int(seconds // 3600)
      minutes = int((seconds % 3600) // 60)
      secs = seconds % 60
      
      return f"{hours}:{minutes:02d}:{secs:05.2f}"
  
  def _format_subtitle_line(self, subtitle: dict, layer: int, style: str) -> str:
      """
      Formata linha de evento ASS
      
      Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
      """
      start = self._format_timestamp(subtitle['start'])
      end = self._format_timestamp(subtitle['end'])
      text = subtitle['text'].replace('\n', '\\N')  # ASS line break
      
      return f"Dialogue: {layer},{start},{end},{style},,0,0,0,,{text}"
  
  def generate_ass_file(self, subtitles: list, output_path: str, preset: str = 'neon'):
      """
      Gera arquivo ASS completo
      
      Args:
          subtitles: Lista de dicts com 'start', 'end', 'text'
          output_path: Path do arquivo ASS
          preset: 'neon' (2-layer)
      """
      
      # Header
      header = """[Script Info]
Title: YTCaption Make-Video
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes

"""
      
      # Styles
      if preset == 'neon':
          styles = self._neon_preset()
      else:
          raise ValueError(f"Unknown preset: {preset}")
      
      # Events
      events = "[Events]\n"
      events += "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
      
      # Gerar eventos para cada legenda (2 layers)
      for sub in subtitles:
          # Layer 0: Glow
          events += self._format_subtitle_line(sub, layer=0, style='NeonGlow') + '\n'
          # Layer 1: Text
          events += self._format_subtitle_line(sub, layer=1, style='NeonText') + '\n'
      
      # Escrever arquivo
      with open(output_path, 'w', encoding='utf-8') as f:
          f.write(header)
          f.write(styles)
          f.write(events)
      
      logger.info("ass_file_generated", output=output_path, subtitles=len(subtitles), lines=len(subtitles)*2)
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Header ASS completo
- [ ] Styles inseridos
- [ ] Eventos gerados (2 layers por legenda)
- [ ] Timestamps formatados corretamente
- [ ] Arquivo salvo com UTF-8

**Testes:**
- Unit: `tests/test_ass_generator.py::test_generate_ass_file_creates_file()`
- Unit: `tests/test_ass_generator.py::test_format_timestamp()`

**Observabilidade:**
- Log: `logger.info("ass_file_generated", output=..., subtitles=..., lines=...)`

**Riscos/Rollback:**
- Risco: Encoding issues com caracteres especiais
- Rollback: Validar UTF-8 antes de escrever

**Dependências:** S-125, S-126

---

<a name="s-130"></a>
## S-130: Implementar burn_subtitles com flags corretos (MUST-FIX)

**Objetivo:** Implementar queima de legendas ASS no vídeo com flags FFmpeg corretos (MUST-FIX v1.6).

**Escopo (IN/OUT):**
- **IN:** Flags corretos: -hide_banner, -nostdin, -map 0:a?
- **OUT:** Não implementar encode customizado

**Arquivos tocados:**
- `services/make-video/app/ass_generator.py`

**Mudanças exatas:**
- Adicionar método:
  ```python
  import subprocess
  import shlex
  
  def burn_subtitles(self, video_path: str, ass_path: str, output_path: str, timeout: int = 300) -> bool:
      """
      Queima legendas ASS no vídeo
      
      MUST-FIX v1.6: Flags corretos
      - -hide_banner: Ocultar banner FFmpeg
      - -nostdin: Não ler stdin (evita travamento)
      - -map 0:a?: Mapear áudio se existir (opcional)
      
      Args:
          video_path: Path do vídeo original
          ass_path: Path do arquivo ASS
          output_path: Path do vídeo com legendas queimadas
          timeout: Timeout em segundos
      
      Returns:
          True se sucesso, False se falha
      """
      
      # MUST-FIX: Path escaping para ASS (será validado em S-131)
      # Windows: C\:\\path\\file.ass
      # Linux: /path/file.ass (precisa escape de :)
      ass_escaped = ass_path.replace('\\', '\\\\').replace(':', '\\:')
      
      cmd = [
          'ffmpeg',
          '-hide_banner',  # MUST-FIX: Ocultar banner
          '-nostdin',  # MUST-FIX: Não ler stdin
          '-i', video_path,
          '-vf', f"ass={ass_escaped}",  # Filtro de legenda
          '-map', '0:v',  # Mapear vídeo
          '-map', '0:a?',  # MUST-FIX: Mapear áudio se existir (? = opcional)
          '-c:v', 'libx264',  # Codec vídeo
          '-c:a', 'copy',  # Copiar áudio
          '-y',  # Overwrite
          output_path
      ]
      
      try:
          logger.info("burning_subtitles", video=video_path, ass=ass_path, output=output_path)
          
          result = subprocess.run(
              cmd,
              capture_output=True,
              text=True,
              timeout=timeout,
              check=True
          )
          
          logger.info("subtitles_burned_successfully", output=output_path)
          return True
      
      except subprocess.TimeoutExpired:
          logger.error("burn_subtitles_timeout", timeout=timeout)
          return False
      
      except subprocess.CalledProcessError as e:
          logger.error("burn_subtitles_failed", stderr=e.stderr)
          return False
      
      except Exception as e:
          logger.error(f"burn_subtitles_error: {e}")
          return False
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Flag -hide_banner presente
- [ ] Flag -nostdin presente
- [ ] Flag -map 0:a? presente (áudio opcional)
- [ ] Path escaping implementado
- [ ] Timeout configurável
- [ ] Retorna bool de sucesso

**Testes:**
- Unit: `tests/test_ass_generator.py::test_burn_subtitles_flags()`

**Observabilidade:**
- Log: `logger.info("burning_subtitles", video=..., ass=..., output=...)`
- Log: `logger.error("burn_subtitles_timeout"|"burn_subtitles_failed", ...)`
- Métrica: `counter("subtitles_burned_total", tags={"status": "success"|"fail"})`

**Riscos/Rollback:**
- Risco: FFmpeg trava sem -nostdin
- Rollback: Já implementado com flag

**Dependências:** S-129, S-006 (timeout utils)

---

<a name="s-131"></a>
## S-131: Validar path escaping no burn_subtitles

**Objetivo:** Validar que path escaping está correto para diferentes sistemas operacionais.

**Escopo (IN/OUT):**
- **IN:** Validação de escaping
- **OUT:** Não implementar normalização de paths

**Arquivos tocados:**
- Nenhum (validação de S-130)

**Mudanças exatas:**
- Validar lógica de escaping:
  ```python
  # Linux: /path/to/file.ass
  # Problema: FFmpeg interpreta : como separador
  # Solução: Escape \:
  
  # Windows: C:\path\to\file.ass
  # Problema: FFmpeg interpreta \ como escape
  # Solução: Double backslash \\
  
  # Código correto (já em S-130):
  ass_escaped = ass_path.replace('\\', '\\\\').replace(':', '\\:')
  ```
- Adicionar testes com paths problemáticos:
  ```python
  def test_path_escaping_linux():
      generator = ASSGenerator()
      path = '/tmp/video:with:colons.ass'
      escaped = path.replace('\\', '\\\\').replace(':', '\\:')
      assert escaped == '/tmp/video\\:with\\:colons.ass'
  
  def test_path_escaping_windows():
      generator = ASSGenerator()
      path = 'C:\\Users\\video.ass'
      escaped = path.replace('\\', '\\\\').replace(':', '\\:')
      assert escaped == 'C\\:\\\\Users\\\\video.ass'
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Escaping valida para Linux
- [ ] Escaping valida para Windows
- [ ] Testes com colons e backslashes
- [ ] Não quebra com paths normais

**Testes:**
- Unit: `tests/test_ass_generator.py::test_path_escaping_linux()`
- Unit: `tests/test_ass_generator.py::test_path_escaping_windows()`

**Observabilidade:**
- N/A (validação)

**Riscos/Rollback:**
- Risco: Escaping incorreto causa erro no FFmpeg
- Rollback: Usar arquivos temporários em paths simples

**Dependências:** S-130

---

<a name="s-132"></a>
## S-132: Criar testes de geração ASS

**Objetivo:** Criar testes que validam geração de arquivo ASS.

**Escopo (IN/OUT):**
- **IN:** Testes de conteúdo ASS
- **OUT:** Não testar renderização visual

**Arquivos tocados:**
- `services/make-video/tests/test_ass_generator.py`

**Mudanças exatas:**
- Criar testes:
  ```python
  import tempfile
  import os
  
  def test_generate_ass_file_structure():
      generator = ASSGenerator()
      
      subtitles = [
          {'start': 0.0, 'end': 2.0, 'text': 'Hello'},
          {'start': 2.5, 'end': 5.0, 'text': 'World'},
      ]
      
      with tempfile.NamedTemporaryFile(suffix='.ass', delete=False) as f:
          output_path = f.name
      
      try:
          generator.generate_ass_file(subtitles, output_path, preset='neon')
          
          # Validar arquivo existe
          assert os.path.exists(output_path)
          
          # Validar conteúdo
          with open(output_path, 'r', encoding='utf-8') as f:
              content = f.read()
          
          # Validar seções
          assert '[Script Info]' in content
          assert '[V4+ Styles]' in content
          assert '[Events]' in content
          
          # Validar styles
          assert 'Style: NeonGlow' in content
          assert 'Style: NeonText' in content
          
          # Validar eventos (2 layers * 2 subtitles = 4 Dialogue lines)
          assert content.count('Dialogue:') == 4
          
          # Validar texto
          assert 'Hello' in content
          assert 'World' in content
      
      finally:
          if os.path.exists(output_path):
              os.unlink(output_path)
  
  def test_format_timestamp_various():
      generator = ASSGenerator()
      
      assert generator._format_timestamp(0.0) == '0:00:00.00'
      assert generator._format_timestamp(65.5) == '0:01:05.50'
      assert generator._format_timestamp(3661.25) == '1:01:01.25'
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Testa estrutura do arquivo
- [ ] Valida seções presentes
- [ ] Valida styles corretos
- [ ] Valida eventos gerados
- [ ] Testa formatação de timestamps

**Testes:**
- Unit: `tests/test_ass_generator.py::test_generate_ass_file_structure()`
- Unit: `tests/test_ass_generator.py::test_format_timestamp_various()`

**Observabilidade:**
- N/A (testing)

**Riscos/Rollback:**
- Risco: Nenhum
- Rollback: N/A

**Dependências:** S-129

---

<a name="s-133"></a>
## S-133: Validar cores ASS formato correto

**Objetivo:** Criar testes que validam formato de cores ASS.

**Escopo (IN/OUT):**
- **IN:** Validação de formato 8-digit
- **OUT:** Não testar renderização de cores

**Arquivos tocados:**
- `services/make-video/tests/test_ass_generator.py`

**Mudanças exatas:**
- Criar testes:
  ```python
  import re
  
  def test_ass_colors_8_digit_format():
      generator = ASSGenerator()
      styles = generator._neon_preset()
      
      # Regex para cores ASS: &H seguido de 8 dígitos hex
      color_pattern = r'&H[0-9A-F]{8}'
      
      colors = re.findall(color_pattern, styles)
      
      # Validar que todas as cores têm 8 dígitos
      assert len(colors) > 0
      for color in colors:
          assert len(color) == 10  # &H + 8 dígitos
      
      # Validar cores específicas
      assert '&H00FFFF00' in styles  # Cyan glow
      assert '&H00FFFFFF' in styles  # White text
      assert '&H00000000' in styles  # Black outline
      assert '&H80000000' in styles  # Semi-transparent back
  
  def test_no_6_digit_colors():
      """Valida que não há cores no formato errado (&HBBGGRR)"""
      generator = ASSGenerator()
      styles = generator._neon_preset()
      
      # Regex para cores 6-digit (formato errado)
      wrong_pattern = r'&H[0-9A-F]{6}(?![0-9A-F])'  # 6 dígitos não seguidos de mais dígitos
      
      wrong_colors = re.findall(wrong_pattern, styles)
      
      assert len(wrong_colors) == 0, f"Found 6-digit colors: {wrong_colors}"
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Valida formato 8-digit
- [ ] Valida cores específicas presentes
- [ ] Valida que não há cores 6-digit

**Testes:**
- Unit: `tests/test_ass_generator.py::test_ass_colors_8_digit_format()`
- Unit: `tests/test_ass_generator.py::test_no_6_digit_colors()`

**Observabilidade:**
- N/A (testing)

**Riscos/Rollback:**
- Risco: Nenhum
- Rollback: N/A

**Dependências:** S-126

---

<a name="s-134"></a>
## S-134: Validar burn_subtitles não trava

**Objetivo:** Criar testes que validam que burn_subtitles não trava indefinidamente.

**Escopo (IN/OUT):**
- **IN:** Testes de timeout
- **OUT:** Não testar com vídeos reais

**Arquivos tocados:**
- `services/make-video/tests/test_ass_generator.py`

**Mudanças exatas:**
- Criar testes:
  ```python
  from unittest.mock import Mock, patch
  import subprocess
  
  def test_burn_subtitles_respects_timeout(monkeypatch):
      """Valida que timeout é respeitado"""
      generator = ASSGenerator()
      
      # Mock subprocess.run para simular timeout
      def mock_run(*args, **kwargs):
          raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs['timeout'])
      
      monkeypatch.setattr('subprocess.run', mock_run)
      
      result = generator.burn_subtitles(
          'video.mp4',
          'subs.ass',
          'output.mp4',
          timeout=1
      )
      
      assert result == False  # Falha por timeout
  
  def test_burn_subtitles_has_nostdin_flag(monkeypatch):
      """Valida que -nostdin está presente"""
      generator = ASSGenerator()
      
      called_cmd = []
      
      def mock_run(cmd, *args, **kwargs):
          called_cmd.append(cmd)
          # Simular sucesso
          mock_result = Mock()
          mock_result.returncode = 0
          return mock_result
      
      monkeypatch.setattr('subprocess.run', mock_run)
      
      generator.burn_subtitles('video.mp4', 'subs.ass', 'output.mp4')
      
      # Validar que -nostdin está no comando
      assert len(called_cmd) == 1
      assert '-nostdin' in called_cmd[0]
      assert '-hide_banner' in called_cmd[0]
      assert '-map' in called_cmd[0]
      assert '0:a?' in called_cmd[0]
  ```

**Critérios de Aceite / Definition of Done:**
- [ ] Testa timeout respeitado
- [ ] Valida -nostdin presente
- [ ] Valida -hide_banner presente
- [ ] Valida -map 0:a? presente

**Testes:**
- Unit: `tests/test_ass_generator.py::test_burn_subtitles_respects_timeout()`
- Unit: `tests/test_ass_generator.py::test_burn_subtitles_has_nostdin_flag()`

**Observabilidade:**
- N/A (testing)

**Riscos/Rollback:**
- Risco: Nenhum
- Rollback: N/A

**Dependências:** S-130

---

## Mapa de Dependências (Pack 11)

```
S-123 (estrutura) ← S-001
S-124 (neon_preset) ← S-123
S-125 (style_key MUST-FIX) ← S-124
S-126 (cores 8-digit MUST-FIX) ← S-124, S-125
S-127 (FontManager) ← S-001
S-128 (font detection) ← S-127, S-123
S-129 (generate_ass_file) ← S-125, S-126
S-130 (burn_subtitles MUST-FIX) ← S-129, S-006
S-131 (validar escaping) ← S-130
S-132 (testes geração) ← S-129
S-133 (validar cores) ← S-126
S-134 (validar não trava) ← S-130
```

**Próximo pack:** Sprint 12 - Sincronismo + Diagnóstico (diagnose_subtitle_sync.py, VAD first speech, auto-decision global_offset vs intra_segment, feature flags, FFmpeg audit, runbook, rollback final)
