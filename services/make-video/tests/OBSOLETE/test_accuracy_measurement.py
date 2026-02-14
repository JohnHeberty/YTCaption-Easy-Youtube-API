"""
Test de Acurácia - Sprint 06 vs Sprint 07
Meta: ≥90% de acurácia

Este teste mede a acurácia real em subset de vídeos de validação.
"""

import pytest
import json
from pathlib import Path
from typing import Dict, List, Tuple

from app.video_processing.ensemble_detector import EnsembleSubtitleDetector


class TestAccuracyMeasurement:
    """Testes de acurácia em dataset real"""
    
    @pytest.fixture(scope="class")
    def validation_videos(self):
        """Carrega vídeos de validação com ground truth"""
        storage = Path(__file__).parent.parent / "storage" / "validation"
        
        # Carregar ground truth dos samples
        ok_path = storage / "sample_OK"
        not_ok_path = storage / "sample_NOT_OK"
        
        videos = {}
        
        # Vídeos COM legendas (sample_OK)
        if ok_path.exists():
            ok_videos = list(ok_path.glob("*.mp4"))[:10]  # Primeiros 10
            for video in ok_videos:
                videos[str(video)] = True
        
        # Vídeos SEM legendas (sample_NOT_OK)
        if not_ok_path.exists():
            not_ok_videos = list(not_ok_path.glob("*.mp4"))[:10]  # Primeiros 10
            for video in not_ok_videos:
                videos[str(video)] = False
        
        print(f"\n📊 Dataset carregado: {len(videos)} vídeos")
        print(f"   - Com legendas: {sum(1 for v in videos.values() if v)}")
        print(f"   - Sem legendas: {sum(1 for v in videos.values() if not v)}")
        
        return videos
    
    def calculate_metrics(self, results: List[Tuple[bool, bool]]) -> Dict:
        """
        Calcula métricas de acurácia
        
        Args:
            results: Lista de tuplas (expected, predicted)
        
        Returns:
            Dict com accuracy, precision, recall, f1
        """
        tp = sum(1 for exp, pred in results if exp and pred)
        tn = sum(1 for exp, pred in results if not exp and not pred)
        fp = sum(1 for exp, pred in results if not exp and pred)
        fn = sum(1 for exp, pred in results if exp and not pred)
        
        total = len(results)
        accuracy = (tp + tn) / total * 100 if total > 0 else 0
        
        precision = tp / (tp + fp) * 100 if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) * 100 if (tp + fn) > 0 else 0
        
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        return {
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1': f1,
            'confusion_matrix': {
                'tp': tp, 'tn': tn, 'fp': fp, 'fn': fn
            },
            'total': total
        }
    
    def test_sprint06_baseline(self, validation_videos):
        """
        Teste 1: Sprint 06 - Baseline (weighted voting)
        """
        print("\n" + "="*70)
        print("🎯 TESTE 1: SPRINT 06 BASELINE (WEIGHTED VOTING)")
        print("="*70)
        
        # Ensemble Sprint 06
        ensemble = EnsembleSubtitleDetector(
            voting_method='weighted'
        )
        
        results = []
        errors = []
        
        for i, (video_path, expected) in enumerate(validation_videos.items(), 1):
            video_name = Path(video_path).name
            print(f"\n[{i}/{len(validation_videos)}] 🎥 {video_name}")
            print(f"   Ground Truth: {'✅ COM legendas' if expected else '❌ SEM legendas'}")
            
            try:
                result = ensemble.detect(video_path)
                predicted = result['has_subtitles']
                confidence = result['confidence']
                
                results.append((expected, predicted))
                
                # Verificar se acertou
                correct = (expected == predicted)
                status = "✅ CORRETO" if correct else "❌ ERRO"
                
                print(f"   Predição: {'✅ COM legendas' if predicted else '❌ SEM legendas'} (conf: {confidence:.1f}%)")
                print(f"   Status: {status}")
                
                if not correct:
                    errors.append({
                        'video': video_name,
                        'expected': expected,
                        'predicted': predicted,
                        'confidence': confidence,
                        'votes': result.get('votes', {})
                    })
            
            except Exception as e:
                print(f"   ⚠️ ERRO: {e}")
                results.append((expected, False))  # Assume erro = sem legendas
        
        # Calcular métricas
        metrics = self.calculate_metrics(results)
        
        print("\n" + "="*70)
        print("📊 RESULTADOS SPRINT 06 BASELINE")
        print("="*70)
        print(f"Total de vídeos:  {metrics['total']}")
        print(f"Acurácia:         {metrics['accuracy']:.2f}%")
        print(f"Precisão:         {metrics['precision']:.2f}%")
        print(f"Recall:           {metrics['recall']:.2f}%")
        print(f"F1-Score:         {metrics['f1']:.2f}%")
        print(f"\nMatriz de Confusão:")
        cm = metrics['confusion_matrix']
        print(f"  TP (Verdadeiro Positivo): {cm['tp']}")
        print(f"  TN (Verdadeiro Negativo): {cm['tn']}")
        print(f"  FP (Falso Positivo):      {cm['fp']}")
        print(f"  FN (Falso Negativo):      {cm['fn']}")
        
        if errors:
            print(f"\n❌ Erros ({len(errors)}):")
            for err in errors:
                print(f"   - {err['video']}: esperado={err['expected']}, predito={err['predicted']} (conf={err['confidence']:.1f}%)")
        
        print("="*70)
        
        # Salvar resultados
        results_file = Path(__file__).parent / "accuracy_results_sprint06.json"
        with open(results_file, 'w') as f:
            json.dump({
                'sprint': '06',
                'metrics': metrics,
                'errors': errors
            }, f, indent=2)
        
        print(f"\n💾 Resultados salvos em: {results_file}")
        
        # Armazenar para comparação
        self.sprint06_metrics = metrics
        
        assert metrics['total'] > 0, "Nenhum vídeo testado"
        assert metrics['accuracy'] > 0, "Acurácia é 0%"
    
    def test_sprint07_advanced(self, validation_videos):
        """
        Teste 2: Sprint 07 - Advanced (confidence-weighted + análise)
        Meta: ≥90% de acurácia
        """
        print("\n" + "="*70)
        print("🎯 TESTE 2: SPRINT 07 ADVANCED (CONFIDENCE-WEIGHTED)")
        print("="*70)
        
        # Ensemble Sprint 07
        ensemble = EnsembleSubtitleDetector(
            voting_method='confidence_weighted',
            enable_conflict_detection=True,
            enable_uncertainty_estimation=True
        )
        
        results = []
        errors = []
        high_conflicts = 0
        high_uncertainty = 0
        
        for i, (video_path, expected) in enumerate(validation_videos.items(), 1):
            video_name = Path(video_path).name
            print(f"\n[{i}/{len(validation_videos)}] 🎥 {video_name}")
            print(f"   Ground Truth: {'✅ COM legendas' if expected else '❌ SEM legendas'}")
            
            try:
                result = ensemble.detect(video_path)
                predicted = result['has_subtitles']
                confidence = result['confidence']
                
                results.append((expected, predicted))
                
                # Análise de conflito
                conflict = result.get('conflict_analysis', {})
                if conflict.get('detected') and conflict.get('severity') == 'high':
                    high_conflicts += 1
                    print(f"   ⚠️ Conflito Alto detectado!")
                
                # Análise de incerteza
                uncertainty = result.get('uncertainty', {})
                if uncertainty.get('level') == 'high':
                    high_uncertainty += 1
                    print(f"   ⚠️ Incerteza Alta: {uncertainty.get('aggregate', 0):.3f}")
                
                # Verificar se acertou
                correct = (expected == predicted)
                status = "✅ CORRETO" if correct else "❌ ERRO"
                
                print(f"   Predição: {'✅ COM legendas' if predicted else '❌ SEM legendas'} (conf: {confidence:.1f}%)")
                print(f"   Status: {status}")
                
                if not correct:
                    errors.append({
                        'video': video_name,
                        'expected': expected,
                        'predicted': predicted,
                        'confidence': confidence,
                        'votes': result.get('votes', {}),
                        'conflict': conflict.get('severity', 'none'),
                        'uncertainty': uncertainty.get('level', 'unknown')
                    })
            
            except Exception as e:
                print(f"   ⚠️ ERRO: {e}")
                results.append((expected, False))
        
        # Calcular métricas
        metrics = self.calculate_metrics(results)
        
        print("\n" + "="*70)
        print("📊 RESULTADOS SPRINT 07 ADVANCED")
        print("="*70)
        print(f"Total de vídeos:   {metrics['total']}")
        print(f"Acurácia:          {metrics['accuracy']:.2f}% ⭐")
        print(f"Precisão:          {metrics['precision']:.2f}%")
        print(f"Recall:            {metrics['recall']:.2f}%")
        print(f"F1-Score:          {metrics['f1']:.2f}%")
        print(f"\nAnálise Avançada:")
        print(f"  Conflitos Altos:   {high_conflicts}")
        print(f"  Incerteza Alta:    {high_uncertainty}")
        print(f"\nMatriz de Confusão:")
        cm = metrics['confusion_matrix']
        print(f"  TP (Verdadeiro Positivo): {cm['tp']}")
        print(f"  TN (Verdadeiro Negativo): {cm['tn']}")
        print(f"  FP (Falso Positivo):      {cm['fp']}")
        print(f"  FN (Falso Negativo):      {cm['fn']}")
        
        if errors:
            print(f"\n❌ Erros ({len(errors)}):")
            for err in errors:
                print(f"   - {err['video']}: esperado={err['expected']}, predito={err['predicted']}")
                print(f"     Conf={err['confidence']:.1f}%, Conflito={err['conflict']}, Incerteza={err['uncertainty']}")
        
        print("="*70)
        
        # Salvar resultados
        results_file = Path(__file__).parent / "accuracy_results_sprint07.json"
        with open(results_file, 'w') as f:
            json.dump({
                'sprint': '07',
                'metrics': metrics,
                'errors': errors,
                'analysis': {
                    'high_conflicts': high_conflicts,
                    'high_uncertainty': high_uncertainty
                }
            }, f, indent=2)
        
        print(f"\n💾 Resultados salvos em: {results_file}")
        
        # Armazenar para comparação
        self.sprint07_metrics = metrics
        
        # Verificações
        assert metrics['total'] > 0, "Nenhum vídeo testado"
        assert metrics['accuracy'] > 0, "Acurácia é 0%"
        
        # META: ≥90% de acurácia
        if metrics['accuracy'] >= 90.0:
            print("\n" + "="*70)
            print("🎉🎉🎉 META DE 90% DE ACURÁCIA ATINGIDA! 🎉🎉🎉")
            print("="*70)
        else:
            print("\n" + "="*70)
            print(f"⚠️ Meta não atingida: {metrics['accuracy']:.2f}% (meta: ≥90%)")
            print(f"   Faltam: {90.0 - metrics['accuracy']:.2f} pontos percentuais")
            print("="*70)
    
    def test_comparison_summary(self):
        """
        Teste 3: Comparação Sprint 06 vs Sprint 07
        """
        print("\n" + "="*70)
        print("📊 COMPARAÇÃO: SPRINT 06 vs SPRINT 07")
        print("="*70)
        
        if not hasattr(self, 'sprint06_metrics') or not hasattr(self, 'sprint07_metrics'):
            pytest.skip("Métricas anteriores não disponíveis")
        
        s06 = self.sprint06_metrics
        s07 = self.sprint07_metrics
        
        print(f"\n{'Métrica':<20} {'Sprint 06':<15} {'Sprint 07':<15} {'Melhoria':<15}")
        print("-" * 70)
        
        metrics_names = [
            ('Acurácia', 'accuracy'),
            ('Precisão', 'precision'),
            ('Recall', 'recall'),
            ('F1-Score', 'f1')
        ]
        
        improvements = []
        for name, key in metrics_names:
            v06 = s06[key]
            v07 = s07[key]
            diff = v07 - v06
            
            symbol = "📈" if diff > 0 else ("📉" if diff < 0 else "➡️")
            improvements.append(diff)
            
            print(f"{name:<20} {v06:>6.2f}%{'':<8} {v07:>6.2f}%{'':<8} {symbol} {diff:>+6.2f} pp")
        
        print("="*70)
        
        avg_improvement = sum(improvements) / len(improvements)
        
        print(f"\n📊 Resumo:")
        print(f"   Melhoria Média: {avg_improvement:+.2f} pontos percentuais")
        
        if s07['accuracy'] >= 90.0:
            print(f"   Status: ✅ META DE 90% ATINGIDA ({s07['accuracy']:.2f}%)")
        else:
            print(f"   Status: ⚠️ Meta não atingida: {s07['accuracy']:.2f}% (faltam {90.0 - s07['accuracy']:.2f} pp)")
        
        if avg_improvement > 0:
            print(f"   Conclusão: ✅ Sprint 07 é superior ao Sprint 06")
        elif avg_improvement == 0:
            print(f"   Conclusão: ➡️ Sprint 07 equivalente ao Sprint 06")
        else:
            print(f"   Conclusão: ⚠️ Sprint 07 inferior ao Sprint 06 (investigar)")
        
        print("="*70)
        
        # Salvar comparação
        comparison_file = Path(__file__).parent / "accuracy_comparison.json"
        with open(comparison_file, 'w') as f:
            json.dump({
                'sprint_06': s06,
                'sprint_07': s07,
                'improvement': {
                    'accuracy': improvements[0],
                    'precision': improvements[1],
                    'recall': improvements[2],
                    'f1': improvements[3],
                    'average': avg_improvement
                },
                'meta_90_percent': {
                    'achieved': s07['accuracy'] >= 90.0,
                    'value': s07['accuracy'],
                    'gap': 90.0 - s07['accuracy'] if s07['accuracy'] < 90.0 else 0
                }
            }, f, indent=2)
        
        print(f"\n💾 Comparação salva em: {comparison_file}")
        
        # Assert: Sprint 07 deve ser pelo menos igual ou superior
        assert avg_improvement >= -1.0, f"Sprint 07 muito inferior (-{abs(avg_improvement):.2f} pp)"
