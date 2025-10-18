# Exemplos de Uso da API

## 📝 Exemplos Práticos

### 1. Transcrição Simples (cURL)

```bash
curl -X POST "http://localhost:8000/api/v1/transcribe" \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "language": "auto"
  }'
```

### 2. Transcrição com Python Requests

```python
import requests
import json

# Configuração
API_URL = "http://localhost:8000"

# Request
response = requests.post(
    f"{API_URL}/api/v1/transcribe",
    json={
        "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "language": "auto"
    }
)

# Processar resposta
if response.status_code == 200:
    data = response.json()
    print(f"✅ Transcrição concluída!")
    print(f"Idioma: {data['language']}")
    print(f"Segmentos: {data['total_segments']}")
    print(f"Texto completo:\n{data['full_text']}")
else:
    print(f"❌ Erro: {response.json()}")
```

### 3. Cliente Python Assíncrono

```python
import asyncio
import httpx

async def transcrever_video(youtube_url: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/transcribe",
            json={
                "youtube_url": youtube_url,
                "language": "auto"
            },
            timeout=600.0  # 10 minutos
        )
        return response.json()

# Uso
resultado = asyncio.run(transcrever_video(
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
))
print(resultado)
```

### 4. Múltiplas Transcrições em Paralelo

```python
import asyncio
import httpx

async def transcrever_multiplos(urls: list[str]):
    async with httpx.AsyncClient() as client:
        tasks = []
        for url in urls:
            task = client.post(
                "http://localhost:8000/api/v1/transcribe",
                json={"youtube_url": url, "language": "auto"},
                timeout=600.0
            )
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks)
        return [r.json() for r in responses]

# Transcrever múltiplos vídeos
urls = [
    "https://www.youtube.com/watch?v=video1",
    "https://www.youtube.com/watch?v=video2",
    "https://www.youtube.com/watch?v=video3"
]

resultados = asyncio.run(transcrever_multiplos(urls))
```

### 5. Salvando em Diferentes Formatos

```python
import requests
import json

def transcrever_e_salvar(youtube_url: str, formato: str = "srt"):
    # Transcrever
    response = requests.post(
        "http://localhost:8000/api/v1/transcribe",
        json={"youtube_url": youtube_url}
    )
    
    if response.status_code != 200:
        raise Exception(f"Erro: {response.json()}")
    
    data = response.json()
    
    # Salvar em diferentes formatos
    if formato == "json":
        with open("transcricao.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    elif formato == "txt":
        with open("transcricao.txt", "w", encoding="utf-8") as f:
            f.write(data["full_text"])
    
    elif formato == "srt":
        with open("transcricao.srt", "w", encoding="utf-8") as f:
            for i, seg in enumerate(data["segments"], 1):
                f.write(f"{i}\n")
                f.write(f"{format_time(seg['start'])} --> {format_time(seg['end'])}\n")
                f.write(f"{seg['text']}\n\n")
    
    print(f"✅ Transcrição salva em transcricao.{formato}")

def format_time(seconds: float) -> str:
    """Formata tempo para formato SRT."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

# Uso
transcrever_e_salvar(
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    formato="srt"
)
```

### 6. Health Check

```python
import requests

response = requests.get("http://localhost:8000/health")
health = response.json()

print(f"Status: {health['status']}")
print(f"Versão: {health['version']}")
print(f"Modelo Whisper: {health['whisper_model']}")
print(f"Uptime: {health['uptime_seconds']:.2f}s")
print(f"Storage: {health['storage_usage']}")
```

### 7. Tratamento de Erros

```python
import requests

def transcrever_com_retry(youtube_url: str, max_retries: int = 3):
    for tentativa in range(max_retries):
        try:
            response = requests.post(
                "http://localhost:8000/api/v1/transcribe",
                json={"youtube_url": youtube_url},
                timeout=600
            )
            
            if response.status_code == 200:
                return response.json()
            
            elif response.status_code == 400:
                print(f"❌ URL inválida: {youtube_url}")
                return None
            
            elif response.status_code == 404:
                print(f"❌ Vídeo não encontrado: {youtube_url}")
                return None
            
            else:
                print(f"⚠️ Erro {response.status_code}, tentativa {tentativa + 1}/{max_retries}")
                if tentativa < max_retries - 1:
                    time.sleep(5)
                    continue
                    
        except requests.exceptions.Timeout:
            print(f"⚠️ Timeout, tentativa {tentativa + 1}/{max_retries}")
            if tentativa < max_retries - 1:
                time.sleep(5)
                continue
        
        except Exception as e:
            print(f"❌ Erro inesperado: {str(e)}")
            return None
    
    print("❌ Falhou após todas as tentativas")
    return None
```

### 8. Integração com Flask

```python
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)
WHISPER_API_URL = "http://localhost:8000"

@app.route('/transcrever', methods=['POST'])
def transcrever():
    data = request.json
    youtube_url = data.get('url')
    
    if not youtube_url:
        return jsonify({"error": "URL é obrigatória"}), 400
    
    try:
        response = requests.post(
            f"{WHISPER_API_URL}/api/v1/transcribe",
            json={"youtube_url": youtube_url},
            timeout=600
        )
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify(response.json()), response.status_code
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(port=5000)
```

### 9. Integração com FastAPI

```python
from fastapi import FastAPI, HTTPException
import httpx

app = FastAPI()
WHISPER_API_URL = "http://localhost:8000"

@app.post("/transcrever")
async def transcrever(youtube_url: str):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{WHISPER_API_URL}/api/v1/transcribe",
                json={"youtube_url": youtube_url},
                timeout=600.0
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=response.json()
                )
                
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=504,
                detail="Timeout ao processar vídeo"
            )
```

### 10. Script CLI

```python
#!/usr/bin/env python3
"""
Script CLI para transcrever vídeos do YouTube.
Uso: python transcribe_cli.py <youtube_url>
"""
import sys
import requests
import json

def main():
    if len(sys.argv) < 2:
        print("Uso: python transcribe_cli.py <youtube_url>")
        sys.exit(1)
    
    youtube_url = sys.argv[1]
    
    print(f"🎬 Transcrevendo: {youtube_url}")
    print("⏳ Aguarde, isso pode levar alguns minutos...")
    
    try:
        response = requests.post(
            "http://localhost:8000/api/v1/transcribe",
            json={"youtube_url": youtube_url},
            timeout=600
        )
        
        if response.status_code == 200:
            data = response.json()
            
            print("\n✅ Transcrição concluída!")
            print(f"📝 Idioma: {data['language']}")
            print(f"⏱️ Duração: {data['duration']:.2f}s")
            print(f"📊 Segmentos: {data['total_segments']}")
            print(f"⚡ Tempo de processamento: {data['processing_time']:.2f}s")
            print("\n📄 Transcrição:\n")
            print(data['full_text'])
            
            # Salvar em arquivo
            filename = f"transcricao_{data['video_id']}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print(f"\n💾 Salvo em: {filename}")
            
        else:
            print(f"❌ Erro: {response.json()}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⚠️ Operação cancelada pelo usuário")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

### Como Executar o Script CLI

```bash
# Tornar executável (Linux/Mac)
chmod +x transcribe_cli.py

# Executar
python transcribe_cli.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

---

## 🔧 Dicas e Truques

### Monitorar Progresso

```python
import time
import requests

def transcrever_com_progresso(youtube_url: str):
    print("🎬 Iniciando transcrição...")
    
    start_time = time.time()
    
    # Fazer requisição em thread separada para mostrar progresso
    import threading
    
    result = {}
    def fazer_requisicao():
        response = requests.post(
            "http://localhost:8000/api/v1/transcribe",
            json={"youtube_url": youtube_url},
            timeout=600
        )
        result['response'] = response
    
    thread = threading.Thread(target=fazer_requisicao)
    thread.start()
    
    # Mostrar progresso enquanto aguarda
    dots = 0
    while thread.is_alive():
        elapsed = time.time() - start_time
        print(f"\r⏳ Processando{'.' * (dots % 4)}{' ' * (3 - dots % 4)} ({elapsed:.0f}s)", end='')
        dots += 1
        time.sleep(0.5)
    
    thread.join()
    
    print("\n✅ Concluído!")
    return result['response'].json()
```

### Cache de Resultados

```python
import hashlib
import json
import os

def transcrever_com_cache(youtube_url: str, cache_dir: str = "./cache"):
    # Criar hash da URL
    url_hash = hashlib.md5(youtube_url.encode()).hexdigest()
    cache_file = f"{cache_dir}/{url_hash}.json"
    
    # Verificar cache
    if os.path.exists(cache_file):
        print("📦 Carregando do cache...")
        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    # Transcrever
    print("🎬 Transcrevendo...")
    response = requests.post(
        "http://localhost:8000/api/v1/transcribe",
        json={"youtube_url": youtube_url}
    )
    
    data = response.json()
    
    # Salvar em cache
    os.makedirs(cache_dir, exist_ok=True)
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return data
```

---

Estes exemplos cobrem os casos de uso mais comuns! 🚀
