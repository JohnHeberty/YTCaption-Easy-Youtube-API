"""Testes unitários para stages individuais"""
import pytest
from pathlib import Path


@pytest.mark.unit
class TestStagesModules:
    """Testes de importação de stages"""

    def test_stages_package_exists(self):
        """Package stages existe"""
        from app.domain import stages
        assert stages is not None

    def test_all_stages_can_be_imported(self):
        """Todas as stages podem ser importadas"""
        stages_list = [
            ('analyze_audio_stage', 'AnalyzeAudioStage'),
            ('load_approved_stage', 'LoadApprovedVideosStage'),
            ('select_shorts_stage', 'SelectShortsStage'),
            ('assemble_video_stage', 'AssembleVideoStage'),
            ('generate_subtitles_stage', 'GenerateSubtitlesStage'),
            ('final_composition_stage', 'FinalCompositionStage'),
            ('trim_video_stage', 'TrimVideoStage'),
            ('validate_av_sync_stage', 'ValidateAVSyncStage'),
        ]

        for module_name, class_name in stages_list:
            module = __import__(
                f'app.domain.stages.{module_name}',
                fromlist=[class_name]
            )
            assert hasattr(module, class_name), f"{class_name} não encontrado em {module_name}"


@pytest.mark.unit
class TestStagesInheritance:
    """Testes de herança das stages"""

    def test_analyze_audio_stage_inherits_job_stage(self):
        """AnalyzeAudioStage herda de JobStage"""
        from app.domain.stages.analyze_audio_stage import AnalyzeAudioStage
        from app.domain.job_stage import JobStage
        assert issubclass(AnalyzeAudioStage, JobStage)

    def test_load_approved_stage_inherits_job_stage(self):
        """LoadApprovedVideosStage herda de JobStage"""
        from app.domain.stages.load_approved_stage import LoadApprovedVideosStage
        from app.domain.job_stage import JobStage
        assert issubclass(LoadApprovedVideosStage, JobStage)

    def test_select_shorts_stage_inherits_job_stage(self):
        """SelectShortsStage herda de JobStage"""
        from app.domain.stages.select_shorts_stage import SelectShortsStage
        from app.domain.job_stage import JobStage
        assert issubclass(SelectShortsStage, JobStage)

    def test_assemble_video_stage_inherits_job_stage(self):
        """AssembleVideoStage herda de JobStage"""
        from app.domain.stages.assemble_video_stage import AssembleVideoStage
        from app.domain.job_stage import JobStage
        assert issubclass(AssembleVideoStage, JobStage)

    def test_generate_subtitles_stage_inherits_job_stage(self):
        """GenerateSubtitlesStage herda de JobStage"""
        from app.domain.stages.generate_subtitles_stage import GenerateSubtitlesStage
        from app.domain.job_stage import JobStage
        assert issubclass(GenerateSubtitlesStage, JobStage)

    def test_final_composition_stage_inherits_job_stage(self):
        """FinalCompositionStage herda de JobStage"""
        from app.domain.stages.final_composition_stage import FinalCompositionStage
        from app.domain.job_stage import JobStage
        assert issubclass(FinalCompositionStage, JobStage)

    def test_trim_video_stage_inherits_job_stage(self):
        """TrimVideoStage herda de JobStage"""
        from app.domain.stages.trim_video_stage import TrimVideoStage
        from app.domain.job_stage import JobStage
        assert issubclass(TrimVideoStage, JobStage)

    def test_validate_av_sync_stage_inherits_job_stage(self):
        """ValidateAVSyncStage herda de JobStage"""
        from app.domain.stages.validate_av_sync_stage import ValidateAVSyncStage
        from app.domain.job_stage import JobStage
        assert issubclass(ValidateAVSyncStage, JobStage)


@pytest.mark.unit
class TestStagesInterface:
    """Testes de interface das stages"""

    def test_analyze_audio_stage_has_execute(self):
        """AnalyzeAudioStage tem método execute"""
        from app.domain.stages.analyze_audio_stage import AnalyzeAudioStage
        assert hasattr(AnalyzeAudioStage, 'execute')
        assert callable(AnalyzeAudioStage.execute)

    def test_load_approved_stage_has_execute(self):
        """LoadApprovedVideosStage tem método execute"""
        from app.domain.stages.load_approved_stage import LoadApprovedVideosStage
        assert hasattr(LoadApprovedVideosStage, 'execute')
        assert callable(LoadApprovedVideosStage.execute)

    def test_select_shorts_stage_has_execute(self):
        """SelectShortsStage tem método execute"""
        from app.domain.stages.select_shorts_stage import SelectShortsStage
        assert hasattr(SelectShortsStage, 'execute')
        assert callable(SelectShortsStage.execute)

    def test_validate_av_sync_stage_has_execute(self):
        """ValidateAVSyncStage tem método execute"""
        from app.domain.stages.validate_av_sync_stage import ValidateAVSyncStage
        assert hasattr(ValidateAVSyncStage, 'execute')
        assert callable(ValidateAVSyncStage.execute)

    def test_all_stages_have_name_attribute(self):
        """Todas as stages devem ter nome"""
        import inspect
        from app.domain.stages.load_approved_stage import LoadApprovedVideosStage

        sig = inspect.signature(LoadApprovedVideosStage.__init__)
        assert len(sig.parameters) > 1


@pytest.mark.unit
class TestStagesNaming:
    """Testes de nomenclatura das stages"""

    def test_stage_names_follow_convention(self):
        """Nomes das stages seguem convenção"""
        stages = [
            'analyze_audio_stage',
            'load_approved_stage',
            'select_shorts_stage',
            'assemble_video_stage',
            'generate_subtitles_stage',
            'final_composition_stage',
            'trim_video_stage',
            'validate_av_sync_stage',
        ]

        for stage_name in stages:
            assert stage_name.endswith('_stage'), f"{stage_name} deve terminar com _stage"
            assert stage_name.islower(), f"{stage_name} deve estar em lowercase"
            assert '_' in stage_name, f"{stage_name} deve usar underscores"


@pytest.mark.unit
class TestStagesStructure:
    """Testes de estrutura das stages"""

    def test_analyze_audio_stage_structure(self):
        """AnalyzeAudioStage tem estrutura esperada"""
        from app.domain.stages.analyze_audio_stage import AnalyzeAudioStage
        assert hasattr(AnalyzeAudioStage, '__init__')
        assert hasattr(AnalyzeAudioStage, 'execute')

    def test_load_approved_stage_structure(self):
        """LoadApprovedVideosStage tem estrutura esperada"""
        from app.domain.stages.load_approved_stage import LoadApprovedVideosStage
        assert hasattr(LoadApprovedVideosStage, '__init__')
        assert hasattr(LoadApprovedVideosStage, 'execute')
        assert hasattr(LoadApprovedVideosStage, 'validate')

    def test_assemble_video_stage_structure(self):
        """AssembleVideoStage tem estrutura esperada"""
        from app.domain.stages.assemble_video_stage import AssembleVideoStage
        assert hasattr(AssembleVideoStage, '__init__')
        assert hasattr(AssembleVideoStage, 'execute')

    def test_generate_subtitles_stage_structure(self):
        """GenerateSubtitlesStage tem estrutura esperada"""
        from app.domain.stages.generate_subtitles_stage import GenerateSubtitlesStage
        assert hasattr(GenerateSubtitlesStage, '__init__')
        assert hasattr(GenerateSubtitlesStage, 'execute')

    def test_final_composition_stage_structure(self):
        """FinalCompositionStage tem estrutura esperada"""
        from app.domain.stages.final_composition_stage import FinalCompositionStage
        assert hasattr(FinalCompositionStage, '__init__')
        assert hasattr(FinalCompositionStage, 'execute')

    def test_validate_av_sync_stage_structure(self):
        """ValidateAVSyncStage tem estrutura esperada"""
        from app.domain.stages.validate_av_sync_stage import ValidateAVSyncStage
        assert hasattr(ValidateAVSyncStage, '__init__')
        assert hasattr(ValidateAVSyncStage, 'execute')
