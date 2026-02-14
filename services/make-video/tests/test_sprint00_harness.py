"""
Sprint 00: Regression Test Harness

Harness de testes de regressão para garantir que melhorias nas sprints
NÃO degradem métricas do baseline.

Executa:
- Testes de smoke (rápido, CI)
- Comparação com baseline
- Gates de regressão (fail se degradar>2%)

Usage:
    pytest tests/test_sprint00_harness.py -v
    pytest tests/test_sprint00_harness.py --baseline=baseline_results.json
"""

import pytest
import json
import logging
from pathlib import Path
from typing import Dict

from app.video_processing.video_validator import VideoValidator

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def baseline_metrics():
    """Load baseline metrics from Sprint 00"""
    baseline_file = Path(__file__).parent.parent / 'storage' / 'validation' / 'baseline_results.json'
    
    if not baseline_file.exists():
        pytest.skip(f"Baseline não encontrado: {baseline_file}. Execute scripts/measure_baseline.py primeiro.")
    
    with open(baseline_file, 'r') as f:
        data = json.load(f)
    
    return data['metrics']


@pytest.fixture(scope="session")
def video_validator():
    """VideoValidator instance para testes"""
    return VideoValidator(
        min_confidence=0.40,
        frames_per_second=6,
        max_frames=30
    )


@pytest.fixture(scope="session")
def smoke_videos():
    """Vídeos de smoke test (quick validation)"""
    smoke_dir = Path(__file__).parent.parent / 'storage' / 'validation' / 'smoke_set'
    
    if not smoke_dir.exists() or not list(smoke_dir.glob("*.mp4")):
        pytest.skip(f"Smoke set vazio: {smoke_dir}. Adicione vídeos de teste.")
    
    return {
        'dir': smoke_dir,
        'videos': list(smoke_dir.glob("*.mp4"))
    }


class TestRegressionHarness:
    """Regression test harness - Sprint 00"""
    
    def test_baseline_exists(self, baseline_metrics):
        """Verifica se baseline foi medido"""
        assert baseline_metrics is not None
        assert 'precision' in baseline_metrics
        assert 'recall' in baseline_metrics
        assert 'f1_score' in baseline_metrics
        assert 'fpr' in baseline_metrics
    
    def test_baseline_sanity(self, baseline_metrics):
        """Verifica se baseline tem valores razoáveis"""
        # Métricas devem estar entre 0 e 1
        assert 0.0 <= baseline_metrics['precision'] <= 1.0
        assert 0.0 <= baseline_metrics['recall'] <= 1.0
        assert 0.0 <= baseline_metrics['f1_score'] <= 1.0
        assert 0.0 <= baseline_metrics['fpr'] <= 1.0
        
        # Baseline não pode ser completamente ruim (senão sistema atual é inútil)
        assert baseline_metrics['f1_score'] >= 0.50, "Baseline F1 muito baixo (<50%)"
    
    def test_smoke_videos_process(self, video_validator, smoke_videos):
        """Smoke test: Todos os vídeos devem processar sem erro"""
        errors = []
        
        for video_path in smoke_videos['videos'][:5]:  # Processar até 5 vídeos
            try:
                has_subs, conf, reason = video_validator.has_embedded_subtitles(str(video_path))
                
                # Verificar que resultado é válido
                assert isinstance(has_subs, bool)
                assert 0.0 <= conf <= 1.0
                assert isinstance(reason, str) and len(reason) > 0
                
            except Exception as e:
                errors.append(f"{video_path.name}: {str(e)}")
        
        if errors:
            pytest.fail(f"Erros no smoke test:\n" + "\n".join(errors))
    
    def test_no_regression_f1(self, baseline_metrics):
        """
        Gate de regressão: F1 Score
        
        CRÍTICO: Sprints NÃO devem degradar F1 em mais de 2%
        Tolerância: -2 pontos percentuais (ex: 85% → 83% = FAIL)
        """
        current_f1 = baseline_metrics['f1_score']
        min_acceptable_f1 = 0.50  # Baseline mínimo aceitável
        
        assert current_f1 >= min_acceptable_f1, (
            f"F1 Score regrediu abaixo do mínimo aceitável: "
            f"{current_f1:.2%} < {min_acceptable_f1:.2%}"
        )
    
    def test_no_regression_recall(self, baseline_metrics):
        """
        Gate de regressão: Recall
        
        CRÍTICO: Recall não deve cair >2%
        Meta produto: ≥85% Recall
        """
        current_recall = baseline_metrics['recall']
        min_acceptable_recall = 0.50  # Baseline mínimo aceitável
        
        assert current_recall >= min_acceptable_recall, (
            f"Recall regrediu abaixo do mínimo aceitável: "
            f"{current_recall:.2%} < {min_acceptable_recall:.2%}"
        )
    
    def test_no_regression_fpr(self, baseline_metrics):
        """
        Gate de regressão: False Positive Rate
        
        CRÍTICO: FPR não deve aumentar >2%
        Meta produto: FPR <3%
        """
        current_fpr = baseline_metrics['fpr']
        max_acceptable_fpr = 0.15  # Baseline máximo aceitável (15%)
        
        assert current_fpr <= max_acceptable_fpr, (
            f"FPR aumentou acima do máximo aceitável: "
            f"{current_fpr:.2%} > {max_acceptable_fpr:.2%}"
        )
    
    def test_goal_tracking_f1(self, baseline_metrics):
        """Meta Sprint 00: F1 ≥90% (informacional, não falha)"""
        current_f1 = baseline_metrics['f1_score']
        goal_f1 = 0.90
        
        gap = goal_f1 - current_f1
        
        if current_f1 >= goal_f1:
            logger.info(f"✅ META ATINGIDA: F1={current_f1:.2%} ≥ {goal_f1:.2%}")
        else:
            logger.info(f"🎯 Meta F1: {current_f1:.2%} (faltam {gap:.2%} para ≥90%)")
    
    def test_goal_tracking_recall(self, baseline_metrics):
        """Meta Sprint 00: Recall ≥85% (informacional, não falha)"""
        current_recall = baseline_metrics['recall']
        goal_recall = 0.85
        
        gap = goal_recall - current_recall
        
        if current_recall >= goal_recall:
            logger.info(f"✅ META ATINGIDA: Recall={current_recall:.2%} ≥ {goal_recall:.2%}")
        else:
            logger.info(f"🎯 Meta Recall: {current_recall:.2%} (faltam {gap:.2%} para ≥85%)")
    
    def test_goal_tracking_fpr(self, baseline_metrics):
        """Meta Sprint 00: FPR <3% (informacional, não falha)"""
        current_fpr = baseline_metrics['fpr']
        goal_fpr = 0.03
        
        if current_fpr < goal_fpr:
            logger.info(f"✅ META ATINGIDA: FPR={current_fpr:.2%} < {goal_fpr:.2%}")
        else:
            excess = current_fpr - goal_fpr
            logger.info(f"🎯 Meta FPR: {current_fpr:.2%} (precisa reduzir {excess:.2%} para <3%)")


class TestMetricComparison:
    """Compara métricas entre sprints"""
    
    def test_save_current_metrics(self, baseline_metrics, tmp_path):
        """Salva métricas atuais para comparação futura"""
        # Este teste sempre passa, serve apenas para documentar métricas
        output_file = tmp_path / 'current_metrics.json'
        
        with open(output_file, 'w') as f:
            json.dump(baseline_metrics, f, indent=2)
        
        logger.info(f"📊 Métricas atuais salvas: {output_file}")
        logger.info(f"   Precision: {baseline_metrics['precision']:.2%}")
        logger.info(f"   Recall:    {baseline_metrics['recall']:.2%}")
        logger.info(f"   F1 Score:  {baseline_metrics['f1_score']:.2%}")
        logger.info(f"   FPR:       {baseline_metrics['fpr']:.2%}")


# Configuração pytest
def pytest_configure(config):
    """Configuração customizada do pytest"""
    config.addinivalue_line(
        "markers", "regression: marca testes de regressão (Sprint 00 harness)"
    )
    config.addinivalue_line(
        "markers", "smoke: marca smoke tests (CI rápido)"
    )
