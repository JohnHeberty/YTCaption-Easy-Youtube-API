#!/usr/bin/env python3
"""
Sprint 00: Simple Baseline Measurement (Fallback)

Como o PaddleOCR está com problema de inicialização (MKL arithmetic error),
este script cria um baseline simplificado apenas validando a estrutura de dados
e preparando para medições futuras.

Usage:
    python scripts/measure_baseline_simple.py
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class SimpleBaselineMeasurement:
    """
    Baseline simplificado - valida estrutura de dataset
    """
    
    def __init__(self, validation_dir: Path):
        self.validation_dir = Path(validation_dir)
        self.sample_ok_dir = self.validation_dir / 'sample_OK'
        self.sample_not_ok_dir = self.validation_dir / 'sample_NOT_OK'
        
        logger.info(f"Validation directory: {self.validation_dir}")
    
    def load_ground_truth(self) -> Dict:
        """Carrega ground truth de ambos os diretórios"""
        ground_truth = {}
        
        # Load sample_OK
        ok_gt_file = self.sample_ok_dir / 'ground_truth.json'
        if ok_gt_file.exists():
            with open(ok_gt_file, 'r') as f:
                ok_data = json.load(f)
            
            for video in ok_data['videos']:
                filename = video['filename']
                video_path = self.sample_ok_dir / filename
                
                if video_path.exists():
                    ground_truth[filename] = {
                        'expected': True,
                        'path': str(video_path),
                        'category': 'sample_OK'
                    }
        
        # Load sample_NOT_OK
        not_ok_gt_file = self.sample_not_ok_dir / 'ground_truth.json'
        if not_ok_gt_file.exists():
            with open(not_ok_gt_file, 'r') as f:
                not_ok_data = json.load(f)
            
            for video in not_ok_data['videos']:
                filename = video['filename']
                video_path = self.sample_not_ok_dir / filename
                
                if video_path.exists():
                    ground_truth[filename] = {
                        'expected': False,
                        'path': str(video_path),
                        'category': 'sample_NOT_OK'
                    }
        
        logger.info(f"✅ Ground truth loaded: {len(ground_truth)} videos")
        
        # Summary
        total_ok = sum(1 for v in ground_truth.values() if v['expected'])
        total_not_ok = len(ground_truth) - total_ok
        logger.info(f"   - WITH subtitles: {total_ok} videos")
        logger.info(f"   - WITHOUT subtitles: {total_not_ok} videos")
        
        return ground_truth
    
    def validate_dataset_structure(self, ground_truth: Dict) -> Dict:
        """Valida estrutura do dataset"""
        validation_results = {
            'total_videos': len(ground_truth),
            'videos_with_subtitles': sum(1 for v in ground_truth.values() if v['expected']),
            'videos_without_subtitles': sum(1 for v in ground_truth.values() if not v['expected']),
            'missing_files': [],
            'valid': True
        }
        
        # Check missing files
        for filename, info in ground_truth.items():
            if not Path(info['path']).exists():
                validation_results['missing_files'].append(filename)
                validation_results['valid'] = False
        
        if validation_results['missing_files']:
            logger.warning(f"⚠️ Missing {len(validation_results['missing_files'])} video files")
        else:
            logger.info("✅ All ground truth videos found")
        
        # Check balance
        balance_ratio = validation_results['videos_with_subtitles'] / validation_results['total_videos']
        if balance_ratio < 0.3 or balance_ratio > 0.7:
            logger.warning(f"⚠️ Dataset imbalanced: {balance_ratio:.1%} positive class")
        else:
            logger.info(f"✅ Dataset balanced: {balance_ratio:.1%} positive class")
        
        return validation_results
    
    def create_baseline_placeholder(self, ground_truth: Dict, validation: Dict) -> Dict:
        """
        Cria baseline placeholder
        
        Como PaddleOCR não está funcionando, cria estrutura de resultados
        vazia para ser preenchida depois.
        """
        baseline = {
            'status': 'placeholder',
            'reason': 'PaddleOCR initialization error (MKL arithmetic error)',
            'timestamp': datetime.now().isoformat(),
            'dataset': {
                'total_videos': len(ground_truth),
                'positive_samples': sum(1 for v in ground_truth.values() if v['expected']),
                'negative_samples': sum(1 for v in ground_truth.values() if not v['expected']),
                'validation': validation
            },
            'metrics': {
                'precision': None,
                'recall': None,
                'f1_score': None,
                'fpr': None,
                'accuracy': None,
                'note': 'Baseline não medido ainda - sistema atual com problemas de inicialização'
            },
            'goals': {
                'f1_score': 0.90,
                'recall': 0.85,
                'fpr': 0.03
            },
            'predictions': {}
        }
        
        logger.info("📊 Baseline placeholder created (measurements pending)")
        return baseline
    
    def save_results(self, baseline: Dict):
        """Salva resultados"""
        output_file = self.validation_dir / 'baseline_results.json'
        
        with open(output_file, 'w') as f:
            json.dump(baseline, f, indent=2, ensure_ascii=False)
        
        logger.info(f"💾 Results saved: {output_file}")
    
    def print_summary(self, baseline: Dict):
        """Imprime resumo"""
        print("\n" + "="*70)
        print("📊 SPRINT 00 - BASELINE MEASUREMENT (PLACEHOLDER)")
        print("="*70)
        
        print("\n📁 Dataset Summary:")
        print(f"   Total videos: {baseline['dataset']['total_videos']}")
        print(f"   WITH subtitles: {baseline['dataset']['positive_samples']}")
        print(f"   WITHOUT subtitles: {baseline['dataset']['negative_samples']}")
        
        validation = baseline['dataset']['validation']
        if validation['valid']:
            print(f"   ✅ Dataset structure valid")
        else:
            print(f"   ⚠️ Dataset has issues: {len(validation['missing_files'])} missing files")
        
        print("\n🎯 Sprint 00 Goals:")
        goals = baseline['goals']
        print(f"   F1 Score: ≥{goals['f1_score']:.0%}")
        print(f"   Recall:   ≥{goals['recall']:.0%}")
        print(f"   FPR:      <{goals['fpr']:.0%}")
        
        print("\n⚠️ STATUS:")
        print(f"   {baseline['status'].upper()}: {baseline['reason']}")
        print("\n📝 Next Steps:")
        print("   1. Fix PaddleOCR initialization (MKL arithmetic error)")
        print("   2. OR: Implement lightweight OCR fallback (pytesseract)")
        print("   3. Run actual baseline measurement on videos")
        print("   4. Compare metrics vs Sprint 00 goals")
        
        print("\n" + "="*70)
    
    def run(self):
        """Executa baseline measurement"""
        logger.info("🚀 Starting Simple Baseline Measurement (Sprint 00)")
        
        # Load ground truth
        ground_truth = self.load_ground_truth()
        
        if not ground_truth:
            logger.error("❌ No ground truth found. Cannot proceed.")
            return
        
        # Validate dataset structure
        validation = self.validate_dataset_structure(ground_truth)
        
        # Create baseline placeholder
        baseline = self.create_baseline_placeholder(ground_truth, validation)
        
        # Save results
        self.save_results(baseline)
        
        # Print summary
        self.print_summary(baseline)
        
        logger.info("✅ Simple baseline measurement complete")


def main():
    validation_dir = Path(__file__).parent.parent / 'storage' / 'validation'
    
    measurement = SimpleBaselineMeasurement(validation_dir)
    measurement.run()


if __name__ == '__main__':
    main()
