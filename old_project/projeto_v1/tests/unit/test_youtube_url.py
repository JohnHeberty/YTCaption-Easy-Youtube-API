"""
Exemplo de teste unitário para YouTubeURL value object.
"""
import pytest
from src.domain.value_objects import YouTubeURL


class TestYouTubeURL:
    """Testes para o value object YouTubeURL."""
    
    def test_create_valid_youtube_url(self):
        """Deve criar YouTubeURL válida."""
        url = YouTubeURL.create("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        
        assert url.video_id == "dQw4w9WgXcQ"
        assert url.url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    def test_create_valid_youtube_short_url(self):
        """Deve criar YouTubeURL válida com URL curta."""
        url = YouTubeURL.create("https://youtu.be/dQw4w9WgXcQ")
        
        assert url.video_id == "dQw4w9WgXcQ"
    
    def test_create_invalid_url_raises_error(self):
        """Deve lançar erro para URL inválida."""
        with pytest.raises(ValueError, match="Invalid YouTube URL"):
            YouTubeURL.create("https://invalid-url.com/video")
    
    def test_youtube_url_is_immutable(self):
        """YouTubeURL deve ser imutável."""
        url = YouTubeURL.create("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        
        with pytest.raises(Exception):  # dataclass frozen=True
            url.video_id = "new_id"
    
    def test_string_representation(self):
        """Deve retornar URL como string."""
        url = YouTubeURL.create("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        
        assert str(url) == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
