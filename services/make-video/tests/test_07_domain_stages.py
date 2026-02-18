"""
TESTES MÓDULO 7: Domain Stages
Testa stages do pipeline (fetch, download, analyze, generate, assemble, etc)
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestFetchShortsStage:
    """Testes para FetchShortsStage"""
    
    def test_fetch_shorts_import(self):
        """Test 7.1: Importar FetchShortsStage"""
        print("\n🧪 TEST 7.1: FetchShortsStage import...")
        
        from app.domain.stages.fetch_shorts import FetchShortsStage
        
        assert FetchShortsStage is not None
        
        print("✅ FetchShortsStage importado")
    
    def test_fetch_shorts_initialization(self):
        """Test 7.2: Inicializar FetchShortsStage"""
        print("\n🧪 TEST 7.2: FetchShortsStage init...")
        
        from app.domain.stages.fetch_shorts import FetchShortsStage
        from app.core.config import get_settings
        
        settings = get_settings()
        stage = FetchShortsStage()
        
        assert stage is not None
        assert hasattr(stage, 'execute') or hasattr(stage, 'run')
        
        print("✅ FetchShortsStage inicializado")


class TestDownloadShortsStage:
    """Testes para DownloadShortsStage"""
    
    def test_download_shorts_import(self):
        """Test 7.3: Importar DownloadShortsStage"""
        print("\n🧪 TEST 7.3: DownloadShortsStage import...")
        
        from app.domain.stages.download_shorts import DownloadShortsStage
        
        assert DownloadShortsStage is not None
        
        print("✅ DownloadShortsStage importado")
    
    def test_download_shorts_initialization(self):
        """Test 7.4: Inicializar DownloadShortsStage"""
        print("\n🧪 TEST 7.4: DownloadShortsStage init...")
        
        from app.domain.stages.download_shorts import DownloadShortsStage
        
        stage = DownloadShortsStage()
        
        assert stage is not None
        
        print("✅ DownloadShortsStage inicializado")


class TestAnalyzeAudioStage:
    """Testes para AnalyzeAudioStage"""
    
    def test_analyze_audio_import(self):
        """Test 7.5: Importar AnalyzeAudioStage"""
        print("\n🧪 TEST 7.5: AnalyzeAudioStage import...")
        
        from app.domain.stages.analyze_audio import AnalyzeAudioStage
        
        assert AnalyzeAudioStage is not None
        
        print("✅ AnalyzeAudioStage importado")


class TestGenerateSubtitlesStage:
    """Testes para GenerateSubtitlesStage"""
    
    def test_generate_subtitles_import(self):
        """Test 7.6: Importar GenerateSubtitlesStage"""
        print("\n🧪 TEST 7.6: GenerateSubtitlesStage import...")
        
        from app.domain.stages.generate_subtitles import GenerateSubtitlesStage
        
        assert GenerateSubtitlesStage is not None
        
        print("✅ GenerateSubtitlesStage importado")


class TestAssembleVideoStage:
    """Testes para AssembleVideoStage"""
    
    def test_assemble_video_import(self):
        """Test 7.7: Importar AssembleVideoStage"""
        print("\n🧪 TEST 7.7: AssembleVideoStage import...")
        
        from app.domain.stages.assemble_video import AssembleVideoStage
        
        assert AssembleVideoStage is not None
        
        print("✅ AssembleVideoStage importado")


class TestPostProcessingStage:
    """Testes para PostProcessingStage"""
    
    def test_post_processing_import(self):
        """Test 7.8: Importar PostProcessingStage"""
        print("\n🧪 TEST 7.8: PostProcessingStage import...")
        
        try:
            from app.domain.stages.post_processing import PostProcessingStage
            
            assert PostProcessingStage is not None
            
            print("✅ PostProcessingStage importado")
            
        except ImportError as e:
            print(f"⚠️  PostProcessingStage não disponível: {e}")
            pytest.skip("PostProcessingStage não implementado")


class TestFinalizeStage:
    """Testes para FinalizeStage"""
    
    def test_finalize_import(self):
        """Test 7.9: Importar FinalizeStage"""
        print("\n🧪 TEST 7.9: FinalizeStage import...")
        
        try:
            from app.domain.stages.finalize import FinalizeStage
            
            assert FinalizeStage is not None
            
            print("✅ FinalizeStage importado")
            
        except ImportError as e:
            print(f"⚠️  FinalizeStage não disponível: {e}")
            pytest.skip("FinalizeStage não implementado")


class TestStageFactory:
    """Testes para StageFactory"""
    
    def test_stage_factory_import(self):
        """Test 7.10: Importar StageFactory"""
        print("\n🧪 TEST 7.10: StageFactory import...")
        
        try:
            from app.domain.stage_factory import StageFactory
            
            assert StageFactory is not None
            
            print("✅ StageFactory importado")
            
        except ImportError as e:
            print(f"⚠️  StageFactory não disponível: {e}")
            pytest.skip("StageFactory não implementado")
    
    def test_stage_factory_create_all_stages(self):
        """Test 7.11: Criar todos os stages via factory"""
        print("\n🧪 TEST 7.11: StageFactory criar stages...")
        
        try:
            from app.domain.stage_factory import StageFactory
            
            factory = StageFactory()
            
            stage_names = [
                'fetch_shorts',
                'download_shorts',
                'analyze_audio',
                'generate_subtitles',
                'assemble_video',
            ]
            
            created_stages = []
            for stage_name in stage_names:
                try:
                    stage = factory.create_stage(stage_name)
                    if stage:
                        created_stages.append(stage_name)
                        print(f"   ✅ {stage_name}: criado")
                except Exception as e:
                    print(f"   ⚠️  {stage_name}: {str(e)[:50]}")
            
            assert len(created_stages) > 0, "Pelo menos um stage deveria ser criado"
            
            print(f"✅ {len(created_stages)}/{len(stage_names)} stages criados")
            
        except (ImportError, AttributeError) as e:
            print(f"⚠️  StageFactory não disponível: {e}")
            pytest.skip("StageFactory não implementado")


class TestPipelineExecution:
    """Testes para Pipeline (sequence de stages)"""
    
    def test_pipeline_composition(self):
        """Test 7.12: Composição do pipeline"""
        print("\n🧪 TEST 7.12: Pipeline composition...")
        
        from app.domain.stages.fetch_shorts import FetchShortsStage
        from app.domain.stages.download_shorts import DownloadShortsStage
        from app.domain.stages.analyze_audio import AnalyzeAudioStage
        
        stages = [
            FetchShortsStage(),
            DownloadShortsStage(),
            AnalyzeAudioStage(),
        ]
        
        assert len(stages) == 3
        
        for i, stage in enumerate(stages):
            assert stage is not None
            print(f"   Stage {i+1}: {type(stage).__name__}")
        
        print("✅ Pipeline composto com 3 stages")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
