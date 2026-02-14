"""
SubtitleDetectorV3 - SEM OTIMIZAÇÕES - FORÇA BRUTA
Processa TODOS os frames, imagem COMPLETA, sem ROI, sem sample
"""
import cv2
from paddleocr import PaddleOCR
from pathlib import Path
from typing import Tuple, Dict


class SubtitleDetectorV3:
    """
    Detector SEM otimizações - FORÇA BRUTA
    - Processa TODOS os frames
    - Frame COMPLETO (sem ROI)
    - Sem sampling
    - Sem heurísticas
    """
    
    def __init__(self):
        """Inicializa apenas PaddleOCR"""
        self.ocr = PaddleOCR(
            use_angle_cls=True,
            lang='en',
            show_log=False,
            use_gpu=True
        )
    
    def detect_full_brute_force(self, video_path: str, max_frames: int = None) -> Tuple[bool, float, str, Dict]:
        """
        Detecção FORÇA BRUTA - SEM otimizações
        
        Args:
            video_path: Caminho do vídeo
            max_frames: Limite máximo de frames (None = TODOS)
        
        Returns:
            (has_text, confidence, sample_text, metadata)
        """
        if not Path(video_path).exists():
            return False, 0.0, "", {'error': 'Video not found'}
        
        cap = cv2.VideoCapture(video_path)
        
        # Informações do vídeo
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0
        
        print(f"📹 Vídeo: {width}x{height}, {total_frames} frames, {duration:.1f}s, {fps:.1f}fps")
        
        # Limitar frames se necessário
        frames_to_process = total_frames if max_frames is None else min(total_frames, max_frames)
        
        print(f"🔍 Processando {frames_to_process} frames COMPLETOS...")
        
        frames_with_text = 0
        all_texts = []
        frame_count = 0
        
        # PROCESSAR TODOS OS FRAMES
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            
            # Limitar se max_frames especificado
            if max_frames is not None and frame_count > max_frames:
                break
            
            # OCR no FRAME COMPLETO (sem crop, sem ROI)
            try:
                result = self.ocr.ocr(frame, cls=True)
                
                if result and result[0]:
                    frames_with_text += 1
                    
                    # Coletar textos
                    for line in result[0]:
                        text = line[1][0]
                        conf = line[1][1]
                        if conf > 0.5:  # Mínimo de confiança
                            all_texts.append(text)
                    
                    if frame_count % 10 == 0:
                        print(f"  Frame {frame_count}/{frames_to_process}: ✅ TEXTO encontrado")
                elif frame_count % 10 == 0:
                    print(f"  Frame {frame_count}/{frames_to_process}: ❌ Sem texto")
                    
            except Exception as e:
                print(f"  Frame {frame_count}: Erro OCR - {e}")
                continue
        
        cap.release()
        
        # Calcular métricas
        detection_ratio = frames_with_text / frame_count if frame_count > 0 else 0
        has_text = frames_with_text > 0  # Basta 1 frame ter texto
        
        sample_text = " ".join(all_texts[:5]) if all_texts else ""
        
        metadata = {
            'resolution': (width, height),
            'duration': duration,
            'fps': fps,
            'total_frames': total_frames,
            'frames_processed': frame_count,
            'frames_with_text': frames_with_text,
            'detection_ratio': detection_ratio,
            'mode': 'BRUTE_FORCE_FULL_FRAME'
        }
        
        print(f"")
        print(f"📊 Resultado:")
        print(f"   Frames processados: {frame_count}")
        print(f"   Frames com texto: {frames_with_text} ({detection_ratio*100:.1f}%)")
        print(f"   Detecção: {'✅ TEM TEXTO' if has_text else '❌ SEM TEXTO'}")
        
        return has_text, detection_ratio, sample_text, metadata


if __name__ == "__main__":
    detector = SubtitleDetectorV3()
    
    # Teste rápido
    test_video = "storage/validation/sample_OK/5Bc-aOe4pC4.mp4"
    has_text, conf, text, meta = detector.detect_full_brute_force(test_video, max_frames=30)
    print(f"\nResultado: {has_text}, Confiança: {conf:.2%}")
