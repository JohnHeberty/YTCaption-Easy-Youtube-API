"""
Sprint 00: Baseline Measurement Script

Mede a precisão/recall do sistema ATUAL (v0 - antes de qualquer sprint)
Este é o baseline contra o qual todas as melhorias serão comparadas.

Requisitos:
- Dataset rotulado em storage/validation/
- Ground truth em .json files
- VideoValidator atual (v0)

Output: baseline_results.json com métricas
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.video_processing.video_validator import VideoValidator
from app.core.config import Settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class BaselineMeasurement:
    """Mede métricas baseline do sistema atual"""
    
    def __init__(self, validation_dir: Path):
        self.validation_dir = validation_dir
        self.validator = VideoValidator(
            min_confidence=0.40,  # Threshold atual
            frames_per_second=6,
            max_frames=30
        )
        self.results = {
            'version': 'v0_baseline',
            'timestamp': datetime.now().isoformat(),
            'metrics': {},
            'predictions': [],
            'errors': []
        }
    
    def load_ground_truth(self, gt_file: Path) -> Dict:
        """Carrega ground truth de arquivo JSON"""
        if not gt_file.exists():
            logger.warning(f"Ground truth não encontrado: {gt_file}")
            return {}
        
        with open(gt_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def evaluate_video(self, video_path: Path, expected_label: bool) -> Dict:
        """Avalia um vídeo e compara com ground truth"""
        try:
            has_subs, confidence, reason = self.validator.has_embedded_subtitles(str(video_path))
            
            prediction = {
                'video': video_path.name,
                'expected': expected_label,
                'predicted': has_subs,
                'confidence': confidence,
                'reason': reason,
                'correct': (has_subs == expected_label)
            }
            
            return prediction
        
        except Exception as e:
            logger.error(f"Erro ao avaliar {video_path.name}: {e}")
            self.results['errors'].append({
                'video': video_path.name,
                'error': str(e)
            })
            return None
    
    def run_evaluation(self, sample_ok_dir: Path, sample_not_ok_dir: Path):
        """Executa avaliação completa em sample_OK e sample_NOT_OK"""
        
        logger.info("=" * 60)
        logger.info("SPRINT 00: BASELINE MEASUREMENT")
        logger.info("=" * 60)
        
        predictions = []
        
        # Avaliar sample_OK (vídeos COM legenda embutida)
        logger.info(f"\n📹 Avaliando sample_OK (expected: TRUE)...")
        if sample_ok_dir.exists():
            ok_files = list(sample_ok_dir.glob("*.mp4"))
            logger.info(f"Encontrados {len(ok_files)} vídeos em sample_OK")
            
            for video_path in ok_files:
                logger.info(f"  Processando: {video_path.name}")
                pred = self.evaluate_video(video_path, expected_label=True)
                if pred:
                    predictions.append(pred)
        else:
            logger.warning(f"⚠️ Diretório não encontrado: {sample_ok_dir}")
        
        # Avaliar sample_NOT_OK (vídeos SEM legenda embutida)
        logger.info(f"\n📹 Avaliando sample_NOT_OK (expected: FALSE)...")
        if sample_not_ok_dir.exists():
            not_ok_files = list(sample_not_ok_dir.glob("*.mp4"))
            logger.info(f"Encontrados {len(not_ok_files)} vídeos em sample_NOT_OK")
            
            for video_path in not_ok_files:
                logger.info(f"  Processando: {video_path.name}")
                pred = self.evaluate_video(video_path, expected_label=False)
                if pred:
                    predictions.append(pred)
        else:
            logger.warning(f"⚠️ Diretório não encontrado: {sample_not_ok_dir}")
        
        self.results['predictions'] = predictions
        
        # Calcular métricas
        self.calculate_metrics()
        
        # Salvar resultados
        self.save_results()
        
        # Mostrar resumo
        self.print_summary()
    
    def calculate_metrics(self):
        """Calcula Precision, Recall, F1, FPR"""
        predictions = self.results['predictions']
        
        if not predictions:
            logger.warning("⚠️ Nenhuma predição para calcular métricas")
            return
        
        # Confusion matrix
        tp = sum(1 for p in predictions if p['expected'] and p['predicted'])
        tn = sum(1 for p in predictions if not p['expected'] and not p['predicted'])
        fp = sum(1 for p in predictions if not p['expected'] and p['predicted'])
        fn = sum(1 for p in predictions if p['expected'] and not p['predicted'])
        
        # Métricas
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        accuracy = (tp + tn) / len(predictions) if predictions else 0.0
        
        self.results['metrics'] = {
            'confusion_matrix': {
                'tp': tp,
                'tn': tn,
                'fp': fp,
                'fn': fn
            },
            'precision': round(precision, 4),
            'recall': round(recall, 4),
            'f1_score': round(f1_score, 4),
            'fpr': round(fpr, 4),
            'accuracy': round(accuracy, 4),
            'total_videos': len(predictions),
            'correct_predictions': tp + tn,
            'incorrect_predictions': fp + fn
        }
    
    def save_results(self):
        """Salva resultados em JSON"""
        output_file = self.validation_dir / 'baseline_results.json'
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"\n💾 Resultados salvos em: {output_file}")
    
    def print_summary(self):
        """Imprime resumo das métricas"""
        metrics = self.results['metrics']
        
        logger.info("\n" + "=" * 60)
        logger.info("📊 BASELINE METRICS (v0 - Sistema Atual)")
        logger.info("=" * 60)
        
        if not metrics:
            logger.warning("⚠️ Nenhuma métrica calculada")
            return
        
        logger.info(f"\n🎯 Confusion Matrix:")
        logger.info(f"  TP (True Positives):  {metrics['confusion_matrix']['tp']}")
        logger.info(f"  TN (True Negatives):  {metrics['confusion_matrix']['tn']}")
        logger.info(f"  FP (False Positives): {metrics['confusion_matrix']['fp']}")
        logger.info(f"  FN (False Negatives): {metrics['confusion_matrix']['fn']}")
        
        logger.info(f"\n📈 Métricas:")
        logger.info(f"  Precision:  {metrics['precision']:.2%}")
        logger.info(f"  Recall:     {metrics['recall']:.2%}")
        logger.info(f"  F1 Score:   {metrics['f1_score']:.2%}")
        logger.info(f"  FPR:        {metrics['fpr']:.2%}")
        logger.info(f"  Accuracy:   {metrics['accuracy']:.2%}")
        
        logger.info(f"\n📊 Total:")
        logger.info(f"  Videos avaliados: {metrics['total_videos']}")
        logger.info(f"  Corretos:         {metrics['correct_predictions']}")
        logger.info(f"  Incorretos:       {metrics['incorrect_predictions']}")
        
        # Meta Sprint 00
        logger.info(f"\n🎯 Meta Sprint 00: ≥90% F1, ≥85% Recall, FPR<3%")
        
        f1_ok = "✅" if metrics['f1_score'] >= 0.90 else "❌"
        recall_ok = "✅" if metrics['recall'] >= 0.85 else "❌"
        fpr_ok = "✅" if metrics['fpr'] < 0.03 else "❌"
        
        logger.info(f"  F1 ≥90%:      {f1_ok} ({metrics['f1_score']:.2%})")
        logger.info(f"  Recall ≥85%:  {recall_ok} ({metrics['recall']:.2%})")
        logger.info(f"  FPR <3%:      {fpr_ok} ({metrics['fpr']:.2%})")
        
        logger.info("=" * 60)


def main():
    """Executa baseline measurement"""
    # Diretórios
    validation_dir = Path(__file__).parent.parent / 'storage' / 'validation'
    sample_ok_dir = validation_dir / 'sample_OK'
    sample_not_ok_dir = validation_dir / 'sample_NOT_OK'
    
    # Verificar se diretórios existem
    if not sample_ok_dir.exists() or not sample_not_ok_dir.exists():
        logger.error("❌ Diretórios sample_OK ou sample_NOT_OK não encontrados!")
        logger.error(f"   Esperado: {sample_ok_dir}")
        logger.error(f"   Esperado: {sample_not_ok_dir}")
        logger.error("\n📝 Adicione vídeos de teste nos diretórios antes de continuar.")
        return
    
    # Contar vídeos
    ok_count = len(list(sample_ok_dir.glob("*.mp4")))
    not_ok_count = len(list(sample_not_ok_dir.glob("*.mp4")))
    
    if ok_count == 0 and not_ok_count == 0:
        logger.error("❌ Nenhum vídeo encontrado em sample_OK ou sample_NOT_OK!")
        logger.error("\n📝 Adicione pelo menos 5-10 vídeos de cada tipo antes de continuar.")
        return
    
    logger.info(f"✅ Encontrados: {ok_count} vídeos em sample_OK, {not_ok_count} em sample_NOT_OK")
    
    # Executar baseline measurement
    baseline = BaselineMeasurement(validation_dir)
    baseline.run_evaluation(sample_ok_dir, sample_not_ok_dir)


if __name__ == '__main__':
    main()
