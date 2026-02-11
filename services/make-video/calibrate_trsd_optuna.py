#!/usr/bin/env python3
"""
TRSD Calibration with Optuna - Hyperparameter Optimization

Otimiza TODOS os parâmetros do TRSD usando Optuna para encontrar
a melhor configuração que maximize a acurácia na detecção de legendas.

Parâmetros otimizados:
- OCR: min_confidence, max_words_per_region, min_region_area
- Temporal: min_consecutive_detections, stability_window, cooldown_frames
- Spatial: proximity_threshold, max_text_regions
- Classificador: area_weight, aspect_ratio_weight, position_weight, etc.
"""

import os
import sys
import json
import shutil
import gc
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import optuna
from optuna.samplers import TPESampler
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import TRSD components
sys.path.insert(0, str(Path(__file__).parent))
from app.ocr_detector import OCRDetector
import cv2

# Global detector instance (reutilizado em todos os trials para eficiência)
_global_detector = None

def get_detector():
    """Retorna instância global do detector (singleton pattern)"""
    global _global_detector
    if _global_detector is None:
        logger.info("🚀 Initializing EasyOCR detector (pt+en)...")
        _global_detector = OCRDetector()
        logger.info("✅ EasyOCR detector initialized successfully")
    return _global_detector


def get_video_codec(video_path: str) -> Optional[str]:
    """Retorna codec do vídeo usando ffprobe"""
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
             '-show_entries', 'stream=codec_name', '-of', 
             'default=noprint_wrappers=1:nokey=1', video_path],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip().lower()
    except Exception as e:
        logger.warning(f"Failed to get codec for {video_path}: {e}")
    return None


def convert_to_h264(input_path: str, output_path: str) -> bool:
    """Converte vídeo para H.264 usando ffmpeg"""
    try:
        logger.info(f"   🔄 Converting {Path(input_path).name} to H.264...")
        
        result = subprocess.run(
            ['ffmpeg', '-i', input_path, '-c:v', 'libx264', '-crf', '23',
             '-c:a', 'copy', '-y', output_path],
            capture_output=True,
            text=True,
            timeout=300  # 5 min max por vídeo
        )
        
        if result.returncode == 0 and Path(output_path).exists():
            logger.info(f"   ✅ Converted successfully")
            return True
        else:
            logger.error(f"   ❌ Conversion failed: {result.stderr[:200]}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"   ⏱️ Conversion timeout (>5min)")
        return False
    except Exception as e:
        logger.error(f"   ❌ Conversion error: {e}")
        return False


def ensure_h264_videos(video_paths: List[Path], temp_dir: Path) -> List[Path]:
    """
    Garante que todos os vídeos sejam H.264, convertendo se necessário
    
    Args:
        video_paths: Lista de caminhos dos vídeos
        temp_dir: Diretório temporário para vídeos convertidos
    
    Returns:
        Lista de caminhos (originais ou convertidos)
    """
    temp_dir.mkdir(parents=True, exist_ok=True)
    processed_videos = []
    converted_count = 0
    
    logger.info(f"\n📹 Verificando codecs de {len(video_paths)} vídeos...")
    
    for video_path in video_paths:
        codec = get_video_codec(str(video_path))
        
        if codec == 'h264':
            logger.info(f"   ✅ {video_path.name} - já é H.264")
            processed_videos.append(video_path)
        elif codec == 'av1' or codec is None:
            # Converter para H.264
            output_name = f"{video_path.stem}_h264.mp4"
            output_path = temp_dir / output_name
            
            if convert_to_h264(str(video_path), str(output_path)):
                processed_videos.append(output_path)
                converted_count += 1
            else:
                # Se conversão falhar, tentar usar original mesmo assim
                logger.warning(f"   ⚠️ Using original {video_path.name} (may be slow!)")
                processed_videos.append(video_path)
        else:
            # Outros codecs (assumir que são rápidos)
            logger.info(f"   ✅ {video_path.name} - codec {codec}")
            processed_videos.append(video_path)
    
    logger.info(f"\n📊 Resumo: {len(processed_videos)} vídeos prontos ({converted_count} convertidos)")
    return processed_videos


def detect_subtitles_wrapper(video_path: str, config: dict) -> Tuple[bool, float, dict]:
    """
    Wrapper function to detect subtitles in a video using OCRDetector
    OTIMIZADO: Limita frames processados e libera memória explicitamente
    
    Args:
        video_path: Path to video file
        config: TRSD configuration (not used yet, for future expansion)
    
    Returns:
        (has_subtitles, confidence, debug_info)
    """
    detector = get_detector()  # Reutilizar detector global
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        return False, 0.0, {"error": "Failed to open video"}
    
    # Sample frames (LIMITE: máximo 10 frames por vídeo para economizar memória)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    duration = total_frames / fps if fps > 0 else 0
    
    # Sample every 2 seconds, MAX 10 frames
    sample_interval = max(1, int(fps * 2))
    max_samples = min(10, total_frames // sample_interval)  # Limite de 10 frames
    
    positive_frames = 0
    total_samples = 0
    max_confidence = 0.0
    
    frame_indices = list(range(0, total_frames, sample_interval))[:max_samples]
    
    for frame_idx in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        
        if not ret:
            break
        
        # Use min_confidence from config if available
        min_conf = config.get("ocr_params", {}).get("min_confidence", 60.0) * 100  # Convert to 0-100 scale
        result = detector.detect_subtitle_in_frame(frame, min_confidence=min_conf)
        
        total_samples += 1
        if result.has_subtitle:
            positive_frames += 1
            max_confidence = max(max_confidence, result.confidence)
        
        # Liberar memória do frame explicitamente
        del frame
    
    cap.release()
    
    # Garbage collection forçado após processamento
    gc.collect()
    
    # Consider video has subtitles if >30% of frames have text
    has_subtitles = (positive_frames / total_samples) > 0.3 if total_samples > 0 else False
    avg_confidence = max_confidence
    
    debug_info = {
        "positive_frames": positive_frames,
        "total_samples": total_samples,
        "max_confidence": max_confidence,
        "duration": duration
    }
    
    return has_subtitles, avg_confidence, debug_info


class TRSDOptimizer:
    """Otimizador de hiperparâmetros TRSD usando Optuna"""
    
    def __init__(self, ok_dir: str, not_ok_dir: str, convert_to_h264: bool = True):
        self.ok_dir = Path(ok_dir)
        self.not_ok_dir = Path(not_ok_dir)
        
        # Validar diretórios
        if not self.ok_dir.exists() or not self.not_ok_dir.exists():
            raise ValueError("Directories OK and NOT_OK must exist")
        
        # Carregar datasets
        ok_videos_raw = list(self.ok_dir.glob("*.mp4"))
        not_ok_videos_raw = list(self.not_ok_dir.glob("*.mp4"))
        
        logger.info(f"📊 Dataset carregado:")
        logger.info(f"   ├─ OK (no subtitles): {len(ok_videos_raw)} videos")
        logger.info(f"   └─ NOT_OK (has subtitles): {len(not_ok_videos_raw)} videos")
        
        if len(ok_videos_raw) == 0 or len(not_ok_videos_raw) == 0:
            raise ValueError("Both OK and NOT_OK directories must contain videos")
        
        # OPÇÃO A: Converter vídeos AV1 para H.264
        if convert_to_h264:
            logger.info("\n🔧 Executando OPÇÃO A: Conversão AV1 → H.264")
            temp_dir = Path(__file__).parent / "storage" / "calibration" / "h264_converted"
            
            self.ok_videos = ensure_h264_videos(ok_videos_raw, temp_dir / "OK")
            self.not_ok_videos = ensure_h264_videos(not_ok_videos_raw, temp_dir / "NOT_OK")
        else:
            self.ok_videos = ok_videos_raw
            self.not_ok_videos = not_ok_videos_raw
        
        # Arquivo para salvar resultados incrementais
        self.results_file = Path(__file__).parent / "storage" / "calibration" / "optuna_incremental_results.json"
        self.results_file.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"\n✅ Dataset final pronto para otimização")
    
    def objective(self, trial: optuna.Trial) -> float:
        """
        Função objetivo para Optuna
        OTIMIZADO: Menos parâmetros para reduzir espaço de busca
        
        Retorna accuracy (0-1) para ser MAXIMIZADA
        """
        
        # =========================================================================
        # DEFINIR HIPERPARÂMETROS ESSENCIAIS (SIMPLIFICADO)
        # =========================================================================
        
        # 1. OCR Parameters (principal parâmetro para EasyOCR)
        ocr_params = {
            "min_confidence": trial.suggest_float("min_confidence", 0.4, 0.8, step=0.05),
        }
        
        # Combinar parâmetros
        config = {
            **ocr_params,
        }
        
        # =========================================================================
        # AVALIAR COM DATASET (PROCESSAMENTO EM LOTES)
        # =========================================================================
        
        true_positives = 0
        false_positives = 0
        true_negatives = 0
        false_negatives = 0
        
        # LOTE 1: Testar vídeos OK (não devem ter legendas detectadas)
        for i, video_path in enumerate(self.ok_videos):
            try:
                has_subtitles, confidence, _ = detect_subtitles_wrapper(
                    str(video_path),
                    config=config
                )
                
                if not has_subtitles:
                    true_negatives += 1  # Correto: não detectou (não tem legendas)
                else:
                    false_positives += 1  # Erro: detectou (mas não tem legendas)
                    
            except Exception as e:
                logger.warning(f"Error processing {video_path.name}: {e}")
                false_positives += 1  # Considerar como erro
            
            # Garbage collection a cada 3 vídeos
            if (i + 1) % 3 == 0:
                gc.collect()
        
        # Garbage collection após lote OK
        gc.collect()
        
        # LOTE 2: Testar vídeos NOT_OK (devem ter legendas detectadas)
        for i, video_path in enumerate(self.not_ok_videos):
            try:
                has_subtitles, confidence, _ = detect_subtitles_wrapper(
                    str(video_path),
                    config=config
                )
                
                if has_subtitles:
                    true_positives += 1  # Correto: detectou (tem legendas)
                else:
                    false_negatives += 1  # Erro: não detectou (mas tem legendas)
                    
            except Exception as e:
                logger.warning(f"Error processing {video_path.name}: {e}")
                false_negatives += 1  # Considerar como erro
            
            # Garbage collection a cada 3 vídeos
            if (i + 1) % 3 == 0:
                gc.collect()
        
        # Garbage collection final
        gc.collect()
        
        # Calcular métricas
        total = true_positives + true_negatives + false_positives + false_negatives
        accuracy = (true_positives + true_negatives) / total if total > 0 else 0
        
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        # Log para este trial
        logger.info(
            f"Trial {trial.number}: "
            f"Accuracy={accuracy:.3f}, F1={f1_score:.3f}, "
            f"Precision={precision:.3f}, Recall={recall:.3f}"
        )
        
        # SALVAR RESULTADO INCREMENTAL (atualiza a cada iteração)
        self._save_incremental_result(trial.number, config, {
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "f1_score": f1_score,
            "true_positives": true_positives,
            "false_positives": false_positives,
            "true_negatives": true_negatives,
            "false_negatives": false_negatives
        })
        
        # Retornar accuracy para maximizar
        return accuracy
    
    def _save_incremental_result(self, trial_number: int, config: dict, metrics: dict):
        """
        Salva resultado de um trial incrementalmente
        Mantém histórico de todos os trials executados
        """
        try:
            # Carregar resultados existentes
            if self.results_file.exists():
                with open(self.results_file, "r") as f:
                    data = json.load(f)
            else:
                data = {
                    "trials": [],
                    "best_trial": None,
                    "dataset_size": {
                        "ok_videos": len(self.ok_videos),
                        "not_ok_videos": len(self.not_ok_videos)
                    }
                }
            
            # Adicionar novo trial
            trial_data = {
                "trial_number": trial_number,
                "params": config,
                "metrics": metrics,
                "timestamp": datetime.now().isoformat()
            }
            data["trials"].append(trial_data)
            
            # Atualizar best trial
            if data["best_trial"] is None or metrics["accuracy"] > data["best_trial"]["metrics"]["accuracy"]:
                data["best_trial"] = trial_data
            
            # Salvar arquivo atualizado
            with open(self.results_file, "w") as f:
                json.dump(data, f, indent=2)
            
        except Exception as e:
            logger.warning(f"Failed to save incremental result: {e}")
    
    def optimize(self, n_trials: int = 100, timeout: int = 3600) -> Dict:
        """
        Executar otimização
        
        Args:
            n_trials: Número de trials
            timeout: Timeout em segundos (1h padrão)
        
        Returns:
            Best parameters e resultados
        """
        
        logger.info(f"🚀 Starting Optuna optimization:")
        logger.info(f"   ├─ Trials: {n_trials}")
        logger.info(f"   └─ Timeout: {timeout}s ({timeout//60}min)")
        
        # Criar estudo Optuna
        study = optuna.create_study(
            direction="maximize",  # Maximizar accuracy
            sampler=TPESampler(seed=42),
            study_name="trsd_optimization"
        )
        
        # Executar otimização
        study.optimize(
            self.objective,
            n_trials=n_trials,
            timeout=timeout,
            show_progress_bar=True
        )
        
        # Resultados
        best_params = study.best_params
        best_value = study.best_value
        
        logger.info(f"\n🎯 OPTIMIZATION COMPLETE!")
        logger.info(f"   ├─ Best Accuracy: {best_value:.4f}")
        logger.info(f"   ├─ Trials completed: {len(study.trials)}")
        logger.info(f"   └─ Best trial: #{study.best_trial.number}")
        
        return {
            "best_params": best_params,
            "best_accuracy": best_value,
            "n_trials": len(study.trials),
            "study": study
        }


def main():
    """Main function"""
    
    # Diretórios (corrigidos para estrutura real)
    BASE_DIR = Path(__file__).parent / "storage"
    OK_DIR = BASE_DIR / "OK"
    NOT_OK_DIR = BASE_DIR / "NOT_OK"
    CALIBRATION_DIR = BASE_DIR / "calibration"  # Onde salvar resultados
    
    logger.info("="*80)
    logger.info("TRSD HYPERPARAMETER OPTIMIZATION WITH OPTUNA")
    logger.info("="*80)
    
    # Criar diretório de calibração
    CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)
    
    # Verificar diretórios
    if not OK_DIR.exists() or not NOT_OK_DIR.exists():
        logger.error(f"❌ Directories not found:")
        logger.error(f"   ├─ OK: {OK_DIR}")
        logger.error(f"   └─ NOT_OK: {NOT_OK_DIR}")
        logger.error("\nPlease create these directories and add test videos.")
        return 1
    
    # Criar otimizador (COM conversão automática AV1→H.264)
    optimizer = TRSDOptimizer(
        ok_dir=str(OK_DIR),
        not_ok_dir=str(NOT_OK_DIR),
        convert_to_h264=True  # OPÇÃO A ativada
    )
    
    # =========================================================================
    # TESTE DE VALIDAÇÃO: 5 trials primeiro
    # =========================================================================
    logger.info("\n" + "="*80)
    logger.info("🧪 TESTE DE VALIDAÇÃO (5 trials)")
    logger.info("="*80)
    
    validation_results = optimizer.optimize(
        n_trials=5,
        timeout=300  # 5 min max
    )
    
    validation_accuracy = validation_results["best_accuracy"]
    
    logger.info(f"\n📊 Validação completa: Accuracy = {validation_accuracy:.1%}")
    
    # Verificar se validação funcionou (accuracy > 0)
    if validation_accuracy == 0.0:
        logger.error("\n❌ VALIDAÇÃO FALHOU!")
        logger.error("   Todos os 5 trials resultaram em accuracy 0%")
        logger.error("   Possíveis causas:")
        logger.error("   - Vídeos não foram processados corretamente")
        logger.error("   - Problemas de codec ainda presentes")
        logger.error("   - Dataset muito desbalanceado")
        logger.error("\n🛑 Abortando calibração completa")
        return 1
    
    logger.info("\n✅ VALIDAÇÃO PASSOU! Prosseguindo com calibração completa...")
    
    # =========================================================================
    # CALIBRAÇÃO COMPLETA: 100 trials
    # =========================================================================
    logger.info("\n" + "="*80)
    logger.info("🚀 CALIBRAÇÃO COMPLETA (100 trials)")
    logger.info("="*80)
    
    n_trials = int(os.getenv("OPTUNA_TRIALS", "100"))  # Default 100 trials
    timeout = int(os.getenv("OPTUNA_TIMEOUT", "3600"))  # 1h default
    
    results = optimizer.optimize(
        n_trials=n_trials,
        timeout=timeout
    )
    
    # Salvar resultados no diretório de calibração
    output_file = CALIBRATION_DIR / "trsd_optuna_best_params.json"
    with open(output_file, "w") as f:
        json.dump({
            "best_params": results["best_params"],
            "best_accuracy": results["best_accuracy"],
            "n_trials": results["n_trials"],
            "optimization_date": datetime.now().isoformat(),
            "dataset_size": {
                "ok_videos": len(optimizer.ok_videos),
                "not_ok_videos": len(optimizer.not_ok_videos)
            }
        }, f, indent=2)
    
    logger.info(f"\n💾 Results saved to: {output_file}")
    
    # Também salvar em storage/ para backward compatibility
    legacy_file = BASE_DIR / "calibration_optuna_results.json"
    shutil.copy(output_file, legacy_file)
    logger.info(f"💾 Legacy copy saved to: {legacy_file}")
    
    # Imprimir best params
    logger.info("\n" + "="*80)
    logger.info("BEST PARAMETERS (copy to config):")
    logger.info("="*80)
    for key, value in sorted(results["best_params"].items()):
        logger.info(f"{key:30s} = {value}")
    
    # Criar report markdown
    report_file = CALIBRATION_DIR / "trsd_optuna_report.md"
    with open(report_file, "w") as f:
        f.write("# TRSD Optuna Optimization Report\n\n")
        f.write(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Best Accuracy**: {results['best_accuracy']:.4f}\n\n")
        f.write(f"**Trials**: {results['n_trials']}\n\n")
        f.write("## Best Parameters\n\n")
        f.write("```python\n")
        f.write("TRSD_CONFIG = {\n")
        for key, value in sorted(results["best_params"].items()):
            if isinstance(value, float):
                f.write(f'    "{key}": {value:.4f},\n')
            else:
                f.write(f'    "{key}": {value},\n')
        f.write("}\n")
        f.write("```\n\n")
        f.write("## Dataset\n\n")
        f.write(f"- OK (no subtitles): {len(optimizer.ok_videos)} videos\n")
        f.write(f"- NOT_OK (has subtitles): {len(optimizer.not_ok_videos)} videos\n")
    
    logger.info(f"📄 Report saved to: {report_file}")
    logger.info(f"\n📁 All calibration files saved to: {CALIBRATION_DIR}")
    logger.info("\n✅ OPTIMIZATION COMPLETE!")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
