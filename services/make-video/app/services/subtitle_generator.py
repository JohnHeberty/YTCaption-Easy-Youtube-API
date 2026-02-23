"""
Subtitle Generator

Converte segmentos de transcrição para formato SRT.
"""

import logging
import re
from typing import List, Dict
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# DATACLASSES PARA MELHOR TIPAGEM
# ═══════════════════════════════════════════════════════════════

@dataclass
class WordCue:
    """Cue de palavra individual com timestamps precisos"""
    start: float
    end: float
    text: str


class SubtitleGenerator:
    """Gerador de legendas em formato SRT"""
    
    def __init__(self):
        pass
    
    def segments_to_srt(self, segments: List[Dict], output_path: str) -> str:
        """Converte segmentos de transcrição para formato SRT
        
        Args:
            segments: Lista de segmentos de transcrição do audio-transcriber
            output_path: Caminho do arquivo SRT de saída
        
        Returns:
            Caminho do arquivo SRT gerado
        """
        logger.info(f"📝 Generating SRT file with {len(segments)} segments")
        
        # Criar diretório se não existir
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            for i, segment in enumerate(segments, start=1):
                start_time = self._format_timestamp(segment["start"])
                end_time = self._format_timestamp(segment["end"])
                text = segment["text"].strip()
                
                # Formato SRT:
                # 1
                # 00:00:00,000 --> 00:00:03,500
                # Texto da legenda
                #
                f.write(f"{i}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{text}\n")
                f.write("\n")
        
        logger.info(f"✅ SRT file generated: {output_path}")
        return output_path
    
    def _format_timestamp(self, seconds: float) -> str:
        """Converte segundos para formato SRT (HH:MM:SS,mmm)
        
        Args:
            seconds: Tempo em segundos
        
        Returns:
            String formatada (ex: "00:00:05,500")
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    def optimize_segments(self, segments: List[Dict], 
                         max_chars_per_line: int = 42, 
                         max_duration: float = 7.0) -> List[Dict]:
        """Otimiza segmentos para melhor legibilidade
        
        Args:
            segments: Segmentos originais
            max_chars_per_line: Máximo de caracteres por linha
            max_duration: Duração máxima de um segmento (segundos)
        
        Returns:
            Segmentos otimizados
        """
        logger.info(f"🔧 Optimizing {len(segments)} segments")
        
        optimized = []
        
        for segment in segments:
            text = segment["text"]
            duration = segment["end"] - segment["start"]
            
            # Se texto muito longo, quebrar em múltiplas linhas
            if len(text) > max_chars_per_line:
                words = text.split()
                lines = []
                current_line = []
                
                for word in words:
                    current_line.append(word)
                    if len(" ".join(current_line)) > max_chars_per_line:
                        if len(current_line) > 1:
                            current_line.pop()
                            lines.append(" ".join(current_line))
                            current_line = [word]
                        else:
                            # Palavra sozinha é muito longa, incluir assim mesmo
                            lines.append(word)
                            current_line = []
                
                if current_line:
                    lines.append(" ".join(current_line))
                
                # Validar que temos linhas antes de dividir duração
                if not lines:
                    # Fallback: manter segmento original
                    optimized.append(segment)
                    continue
                
                # Dividir duração entre linhas
                line_duration = duration / len(lines)
                for i, line in enumerate(lines):
                    optimized.append({
                        "start": segment["start"] + (i * line_duration),
                        "end": segment["start"] + ((i + 1) * line_duration),
                        "text": line
                    })
            
            # Se duração muito longa, limitar
            elif duration > max_duration:
                optimized.append({
                    "start": segment["start"],
                    "end": segment["start"] + max_duration,
                    "text": text
                })
            
            else:
                optimized.append(segment)
        
        logger.info(f"✅ Segments optimized: {len(segments)} -> {len(optimized)}")
        return optimized
    
    def generate_word_by_word_srt(self, segments: List[Dict], output_path: str,
                                    words_per_caption: int = 2) -> str:
        """Gera SRT com legendas palavra por palavra (estilo TikTok/Shorts)
        
        Args:
            segments: Segmentos de transcrição
            output_path: Caminho do arquivo SRT
            words_per_caption: Quantas palavras por legenda (1-3 recomendado)
        
        Returns:
            Caminho do arquivo SRT gerado
        """
        import re
        
        logger.info(f"📝 Generating word-by-word SRT ({words_per_caption} words/caption)")
        
        # Criar diretório
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        word_timings = []
        
        # Extrair palavras com timestamps
        for segment in segments:
            start_time = segment.get("start", 0.0)
            end_time = segment.get("end", 0.0)
            text = segment.get("text", "").strip()
            
            if not text:
                continue
            
            # Dividir em palavras (mantém pontuação)
            words = re.findall(r'\S+', text)
            
            if not words:
                continue
            
            # Calcular tempo por palavra
            segment_duration = end_time - start_time
            time_per_word = segment_duration / len(words)
            
            # Atribuir timestamps para cada palavra
            for i, word in enumerate(words):
                word_start = start_time + (i * time_per_word)
                word_end = word_start + time_per_word
                
                word_timings.append({
                    "word": word,
                    "start": word_start,
                    "end": word_end
                })
        
        # Gerar SRT agrupando palavras
        with open(output_path, "w", encoding="utf-8") as f:
            subtitle_index = 1
            i = 0
            
            while i < len(word_timings):
                # Pegar grupo de palavras
                word_group = word_timings[i:i+words_per_caption]
                
                if not word_group:
                    break
                
                # Tempo do grupo
                start_time = word_group[0]["start"]
                end_time = word_group[-1]["end"]
                
                # Texto do grupo
                text = " ".join([w["word"] for w in word_group])
                
                # Escrever entrada SRT
                f.write(f"{subtitle_index}\n")
                f.write(f"{self._format_timestamp(start_time)} --> {self._format_timestamp(end_time)}\n")
                f.write(f"{text}\n")
                f.write("\n")
                
                subtitle_index += 1
                i += words_per_caption
        
        logger.info(f"✅ Word-by-word SRT generated: {output_path} ({subtitle_index-1} captions)")
        return output_path


# ═══════════════════════════════════════════════════════════════
# NOVAS FUNÇÕES OTIMIZADAS (MELHORIAS DE SINCRONIZAÇÃO)
# ═══════════════════════════════════════════════════════════════

def format_srt_timestamp(seconds: float) -> str:
    """
    Converte segundos para formato SRT (HH:MM:SS,mmm)
    
    Args:
        seconds: Tempo em segundos (pode ser negativo, será truncado para 0)
    
    Returns:
        String formatada (ex: "00:00:05,500")
    """
    if seconds < 0:
        seconds = 0.0
    
    ms = int(round(seconds * 1000))
    hh = ms // 3_600_000
    ms %= 3_600_000
    mm = ms // 60_000
    ms %= 60_000
    ss = ms // 1_000
    ms %= 1_000
    
    return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"


def write_srt_from_word_cues(
    word_cues: List[Dict],
    srt_path: str,
    words_per_caption: int = 2
) -> str:
    """
    Gera arquivo SRT direto dos word cues (SEM redistribuir timestamps).
    
    Esta função PRESERVA os timestamps refinados pelo VAD, ao contrário de 
    generate_word_by_word_srt() que redistribui tempos uniformemente.
    
    Args:
        word_cues: Lista de dicts {'start': float, 'end': float, 'text': str}
                   Cues já devem estar finalizados (após gating VAD)
        srt_path: Caminho do arquivo SRT de saída
        words_per_caption: Quantas palavras agrupar por legenda
    
    Returns:
        Caminho do arquivo SRT gerado
        
    Exemplo:
        word_cues = [
            {'start': 0.5, 'end': 1.4, 'text': 'Olá,'},
            {'start': 1.4, 'end': 2.1, 'text': 'como'},
            {'start': 2.1, 'end': 2.8, 'text': 'vai?'}
        ]
        write_srt_from_word_cues(word_cues, 'out.srt', words_per_caption=2)
        
        Resultado SRT:
        1
        00:00:00,500 --> 00:00:02,100
        Olá, como
        
        2
        00:00:02,100 --> 00:00:02,800
        vai?
    """
    logger.info(
        f"📝 Writing SRT directly from {len(word_cues)} word cues "
        f"({words_per_caption} words/caption) - preserving VAD timestamps"
    )
    
    # Criar diretório se não existir
    Path(srt_path).parent.mkdir(parents=True, exist_ok=True)
    
    lines = []
    caption_index = 1
    
    # Processar em grupos de N palavras
    for i in range(0, len(word_cues), words_per_caption):
        chunk = word_cues[i:i + words_per_caption]
        
        if not chunk:
            continue
        
        # Timestamp do grupo: início da primeira palavra → fim da última
        caption_start = chunk[0]['start']
        caption_end = chunk[-1]['end']
        
        # Texto do grupo: juntar palavras com espaço
        caption_text = " ".join(c['text'] for c in chunk).strip()
        
        if not caption_text:
            continue  # Pular legendas vazias
        
        # Escrever entrada SRT
        lines.append(str(caption_index))
        lines.append(f"{format_srt_timestamp(caption_start)} --> {format_srt_timestamp(caption_end)}")
        lines.append(caption_text)
        lines.append("")  # Linha em branco entre legendas
        
        caption_index += 1
    
    # Escrever arquivo
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    logger.info(
        f"✅ SRT written with {caption_index - 1} captions, "
        f"timestamps preserved from VAD gating"
    )
    
    return srt_path


def segments_to_weighted_word_cues(segments: List[Dict]) -> List[Dict]:
    """
    Converte segments em word cues com timestamps PONDERADOS por comprimento.
    
    Esta função corrige o problema de "tempo uniforme por palavra", que causa
    drift perceptível. Palavras curtas ("a", "o") recebem menos tempo, palavras
    longas ("responsabilidade") recebem mais tempo.
    
    Método: Ponderar por número de caracteres (sem pontuação nas bordas).
    
    Args:
        segments: Lista de segmentos do Whisper
                  [{'start': 0.5, 'end': 3.2, 'text': 'Olá, como vai?'}]
    
    Returns:
        Lista de word cues com timestamps ponderados
        [{'start': 0.5, 'end': 1.4, 'text': 'Olá,'},
         {'start': 1.4, 'end': 2.3, 'text': 'como'},
         {'start': 2.3, 'end': 3.2, 'text': 'vai?'}]
    """
    logger.info(f"📝 Converting {len(segments)} segments to weighted word cues")
    
    all_word_cues = []
    
    for segment in segments:
        start = float(segment.get("start", 0.0))
        end = float(segment.get("end", 0.0))
        text = (segment.get("text") or "").strip()
        
        if not text or end <= start:
            continue  # Pular segmentos vazios ou inválidos
        
        # Extrair palavras (mantém pontuação anexada)
        words = re.findall(r'\S+', text)
        
        if not words:
            continue
        
        duration = end - start
        
        # ────────────────────────────────────────────────────────────
        # PONDERAR POR COMPRIMENTO DE PALAVRA
        # ────────────────────────────────────────────────────────────
        # Calcular "peso" de cada palavra (número de letras, sem pontuação)
        def word_weight(word: str) -> int:
            # Remove pontuação nas bordas: "Olá," → "Olá"
            core = re.sub(r"^\W+|\W+$", "", word)
            return max(1, len(core))  # Mínimo 1
        
        weights = [word_weight(w) for w in words]
        total_weight = sum(weights)
        
        # Distribuir tempo proporcionalmente ao peso
        current_time = start
        
        for word, weight in zip(words, weights):
            word_duration = duration * (weight / total_weight)
            word_end = current_time + word_duration
            
            all_word_cues.append({
                'start': current_time,
                'end': word_end,
                'text': word
            })
            
            current_time = word_end
        
        # Garantir que última palavra fecha exatamente no end do segmento
        # (evita drift acumulado por arredondamento)
        if all_word_cues:
            all_word_cues[-1]['end'] = end
    
    logger.info(
        f"✅ Generated {len(all_word_cues)} weighted word cues from "
        f"{len(segments)} segments (weighted by word length)"
    )
    
    return all_word_cues
