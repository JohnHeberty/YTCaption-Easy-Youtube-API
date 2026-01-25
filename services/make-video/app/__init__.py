"""
Make-Video Service

Microserviço orquestrador para criação de vídeos dinâmicos
usando YouTube Shorts + Áudio customizado + Legendas.

Reutiliza 100% a infraestrutura existente:
- youtube-search: Busca de shorts
- video-downloader: Download de vídeos
- audio-transcriber: Geração de legendas

Responsabilidade exclusiva: Orquestração + Montagem (FFmpeg)
"""

__version__ = "1.0.0"
