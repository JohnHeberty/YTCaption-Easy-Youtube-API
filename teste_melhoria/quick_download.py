"""
Download simplificado de vídeo de teste (sem FFmpeg).
"""
import subprocess
from pathlib import Path

# Criar diretório
Path("./temp").mkdir(exist_ok=True)

# URL de teste (vídeo curto)
url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
output = "temp/test_video.%(ext)s"

print("📥 Baixando vídeo de teste...")
print(f"🔗 URL: {url}")

# Baixar apenas o melhor áudio disponível (sem conversão)
cmd = [
    "yt-dlp",
    "-f", "bestaudio",
    "-o", output,
    url
]

try:
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    print("✅ Download concluído!")
    
    # Procurar arquivo baixado
    for file in Path("./temp").glob("test_video.*"):
        print(f"📁 Arquivo: {file}")
        print(f"📦 Tamanho: {file.stat().st_size / (1024*1024):.2f} MB")
        
        # Renomear para .mp3 se não for
        if file.suffix != ".mp3":
            new_path = file.with_suffix(".mp3")
            file.rename(new_path)
            print(f"✏️  Renomeado para: {new_path}")
            
except subprocess.CalledProcessError as e:
    print(f"❌ Erro: {e}")
    print(f"Stderr: {e.stderr}")
except FileNotFoundError:
    print("❌ yt-dlp não encontrado!")
    print("Instale: pip install yt-dlp")
