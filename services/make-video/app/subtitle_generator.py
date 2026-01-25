"""
Subtitle Generator

Converte segmentos de transcrição para formato SRT.
"""

import logging
from typing import List, Dict
from pathlib import Path

logger = logging.getLogger(__name__)


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
