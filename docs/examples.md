# 💡 Exemplos Práticos# Exemplos de Uso da API



## 🎯 Casos de Uso## 📝 Exemplos Práticos



### 1. Transcrição Rápida (com legendas)### 1. Transcrição Simples (cURL)

**Usa legendas existentes - resultado em 1-2 segundos**

```bash

```bashcurl -X POST "http://localhost:8000/api/v1/transcribe" \

curl -X POST "http://localhost:8000/api/v1/transcribe" \  -H "Content-Type: application/json" \

  -H "Content-Type: application/json" \  -d '{

  -d '{    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",

    "youtube_url": "https://youtube.com/watch?v=exemplo",    "language": "auto"

    "use_youtube_transcript": true,  }'

    "language": "en"```

  }'

```### 2. Transcrição com Python Requests



### 2. Transcrição Precisa (sem legendas)```python

**Usa Whisper - mais lento mas 100% preciso**import requests

import json

```bash

curl -X POST "http://localhost:8000/api/v1/transcribe" \# Configuração

  -H "Content-Type: application/json" \API_URL = "http://localhost:8000"

  -d '{

    "youtube_url": "https://youtube.com/watch?v=exemplo",# Request

    "language": "auto"response = requests.post(

  }'    f"{API_URL}/api/v1/transcribe",

```    json={

        "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",

### 3. Verificar Antes de Transcrever        "language": "auto"

**Obtém info do vídeo (duração, idioma, legendas disponíveis)**    }

)

```bash

curl -X POST "http://localhost:8000/api/v1/video/info" \# Processar resposta

  -H "Content-Type: application/json" \if response.status_code == 200:

  -d '{"youtube_url": "https://youtube.com/watch?v=exemplo"}'    data = response.json()

```    print(f"✅ Transcrição concluída!")

    print(f"Idioma: {data['language']}")

**Resposta mostra:**    print(f"Segmentos: {data['total_segments']}")

- Duração (ex: 3600s = 1h)    print(f"Texto completo:\n{data['full_text']}")

- Idioma detectado (ex: pt, confiança 0.8)else:

- Legendas (5 manuais, 313 auto)    print(f"❌ Erro: {response.json()}")

- Tempo estimado Whisper (ex: base = 30min)```



### 4. Vídeo Longo (1h+)### 3. Cliente Python Assíncrono

**Recomendado: Use YouTube Transcript**

```python

```bashimport asyncio

curl -X POST "http://localhost:8000/api/v1/transcribe" \import httpx

  -H "Content-Type: application/json" \

  -d '{async def transcrever_video(youtube_url: str):

    "youtube_url": "https://youtube.com/watch?v=longo",    async with httpx.AsyncClient() as client:

    "use_youtube_transcript": true,        response = await client.post(

    "prefer_manual_subtitles": true            "http://localhost:8000/api/v1/transcribe",

  }'            json={

```                "youtube_url": youtube_url,

**Tempo**: 2-5 segundos                "language": "auto"

            },

---            timeout=600.0  # 10 minutos

        )

## 🐍 Python        return response.json()



### Cliente Básico# Uso

resultado = asyncio.run(transcrever_video(

```python    "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

import requests))

print(resultado)

class YTCaptionClient:```

    def __init__(self, base_url="http://localhost:8000"):

        self.base_url = base_url### 4. Múltiplas Transcrições em Paralelo

    

    def get_info(self, url):```python

        return requests.post(import asyncio

            f"{self.base_url}/api/v1/video/info",import httpx

            json={"youtube_url": url}

        ).json()async def transcrever_multiplos(urls: list[str]):

        async with httpx.AsyncClient() as client:

    def transcribe(self, url, use_youtube=True):        tasks = []

        return requests.post(        for url in urls:

            f"{self.base_url}/api/v1/transcribe",            task = client.post(

            json={                "http://localhost:8000/api/v1/transcribe",

                "youtube_url": url,                json={"youtube_url": url, "language": "auto"},

                "use_youtube_transcript": use_youtube                timeout=600.0

            }            )

        ).json()            tasks.append(task)

        

# Uso        responses = await asyncio.gather(*tasks)

client = YTCaptionClient()        return [r.json() for r in responses]



# Info# Transcrever múltiplos vídeos

info = client.get_info("https://youtube.com/watch?v=exemplo")urls = [

print(f"Duração: {info['duration_seconds']}s")    "https://www.youtube.com/watch?v=video1",

    "https://www.youtube.com/watch?v=video2",

# Transcrever    "https://www.youtube.com/watch?v=video3"

result = client.transcribe("https://youtube.com/watch?v=exemplo")]

print(f"Texto: {result['full_text'][:200]}...")

```resultados = asyncio.run(transcrever_multiplos(urls))

```

### Processamento em Lote

### 5. Salvando em Diferentes Formatos

```python

from concurrent.futures import ThreadPoolExecutor```python

import requests

def process_batch(urls, max_workers=3):import json

    client = YTCaptionClient()

    results = []def transcrever_e_salvar(youtube_url: str, formato: str = "srt"):

        # Transcrever

    with ThreadPoolExecutor(max_workers) as executor:    response = requests.post(

        futures = {executor.submit(client.transcribe, url): url for url in urls}        "http://localhost:8000/api/v1/transcribe",

                json={"youtube_url": youtube_url}

        for future in futures:    )

            url = futures[future]    

            try:    if response.status_code != 200:

                result = future.result()        raise Exception(f"Erro: {response.json()}")

                results.append({'url': url, 'success': True, 'data': result})    

            except Exception as e:    data = response.json()

                results.append({'url': url, 'success': False, 'error': str(e)})    

        # Salvar em diferentes formatos

    return results    if formato == "json":

```        with open("transcricao.json", "w", encoding="utf-8") as f:

            json.dump(data, f, ensure_ascii=False, indent=2)

### Exportar para SRT    

    elif formato == "txt":

```python        with open("transcricao.txt", "w", encoding="utf-8") as f:

def export_srt(segments, output="subtitle.srt"):            f.write(data["full_text"])

    with open(output, 'w', encoding='utf-8') as f:    

        for i, seg in enumerate(segments, 1):    elif formato == "srt":

            start = format_time(seg['start'])        with open("transcricao.srt", "w", encoding="utf-8") as f:

            end = format_time(seg['end'])            for i, seg in enumerate(data["segments"], 1):

            f.write(f"{i}\n{start} --> {end}\n{seg['text']}\n\n")                f.write(f"{i}\n")

                f.write(f"{format_time(seg['start'])} --> {format_time(seg['end'])}\n")

def format_time(seconds):                f.write(f"{seg['text']}\n\n")

    h = int(seconds // 3600)    

    m = int((seconds % 3600) // 60)    print(f"✅ Transcrição salva em transcricao.{formato}")

    s = int(seconds % 60)

    ms = int((seconds % 1) * 1000)def format_time(seconds: float) -> str:

    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"    """Formata tempo para formato SRT."""

    hours = int(seconds // 3600)

# Uso    minutes = int((seconds % 3600) // 60)

result = client.transcribe(url)    secs = int(seconds % 60)

export_srt(result['segments'])    millis = int((seconds % 1) * 1000)

```    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"



---# Uso

transcrever_e_salvar(

## 🌐 JavaScript    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",

    formato="srt"

### Cliente Fetch)

```

```javascript

class YTCaptionClient {### 6. Health Check

  constructor(baseUrl = 'http://localhost:8000') {

    this.baseUrl = baseUrl;```python

  }import requests



  async transcribe(url, useYoutube = true) {response = requests.get("http://localhost:8000/health")

    const response = await fetch(`${this.baseUrl}/api/v1/transcribe`, {health = response.json()

      method: 'POST',

      headers: { 'Content-Type': 'application/json' },print(f"Status: {health['status']}")

      body: JSON.stringify({print(f"Versão: {health['version']}")

        youtube_url: url,print(f"Modelo Whisper: {health['whisper_model']}")

        use_youtube_transcript: useYoutubeprint(f"Uptime: {health['uptime_seconds']:.2f}s")

      })print(f"Storage: {health['storage_usage']}")

    });```

    return response.json();

  }### 7. Tratamento de Erros

}

```python

// Usoimport requests

const client = new YTCaptionClient();

const result = await client.transcribe('https://youtube.com/watch?v=exemplo');def transcrever_com_retry(youtube_url: str, max_retries: int = 3):

console.log(result.full_text);    for tentativa in range(max_retries):

```        try:

            response = requests.post(

---                "http://localhost:8000/api/v1/transcribe",

                json={"youtube_url": youtube_url},

## 🔄 Integração                timeout=600

            )

### GitHub Actions            

            if response.status_code == 200:

```yaml                return response.json()

name: Transcrever Vídeos            

            elif response.status_code == 400:

on:                print(f"❌ URL inválida: {youtube_url}")

  workflow_dispatch:                return None

    inputs:            

      youtube_url:            elif response.status_code == 404:

        required: true                print(f"❌ Vídeo não encontrado: {youtube_url}")

                return None

jobs:            

  transcribe:            else:

    runs-on: ubuntu-latest                print(f"⚠️ Erro {response.status_code}, tentativa {tentativa + 1}/{max_retries}")

    steps:                if tentativa < max_retries - 1:

      - name: Transcrever                    time.sleep(5)

        run: |                    continue

          curl -X POST "https://api.ytcaption.com/api/v1/transcribe" \                    

            -H "Content-Type: application/json" \        except requests.exceptions.Timeout:

            -d "{\"youtube_url\": \"${{ github.event.inputs.youtube_url }}\"}" \            print(f"⚠️ Timeout, tentativa {tentativa + 1}/{max_retries}")

            > transcription.json            if tentativa < max_retries - 1:

                      time.sleep(5)

      - name: Upload                continue

        uses: actions/upload-artifact@v3        

        with:        except Exception as e:

          name: transcription            print(f"❌ Erro inesperado: {str(e)}")

          path: transcription.json            return None

```    

    print("❌ Falhou após todas as tentativas")

### Webhook Receiver    return None

```

```python

from fastapi import FastAPI, BackgroundTasks### 8. Integração com Flask

import requests

```python

app = FastAPI()from flask import Flask, request, jsonify

import requests

@app.post("/webhook/youtube")

async def process(video_url: str, background_tasks: BackgroundTasks):app = Flask(__name__)

    background_tasks.add_task(process_and_notify, video_url)WHISPER_API_URL = "http://localhost:8000"

    return {"status": "processing"}

@app.route('/transcrever', methods=['POST'])

async def process_and_notify(url):def transcrever():

    result = requests.post(    data = request.json

        "http://ytcaption:8000/api/v1/transcribe",    youtube_url = data.get('url')

        json={"youtube_url": url}    

    ).json()    if not youtube_url:

            return jsonify({"error": "URL é obrigatória"}), 400

    # Notificar callback    

    requests.post("https://callback.example.com/done", json=result)    try:

```        response = requests.post(

            f"{WHISPER_API_URL}/api/v1/transcribe",

---            json={"youtube_url": youtube_url},

            timeout=600

## 💡 Dicas        )

        

### Retry Automático        if response.status_code == 200:

            return jsonify(response.json())

```python        else:

import time            return jsonify(response.json()), response.status_code

            

def transcribe_with_retry(url, max_retries=3):    except Exception as e:

    for attempt in range(max_retries):        return jsonify({"error": str(e)}), 500

        try:

            # Tentar YouTube Transcriptif __name__ == '__main__':

            return client.transcribe(url, use_youtube=True)    app.run(port=5000)

        except Exception as e:```

            if attempt == max_retries - 1:

                # Última tentativa: Whisper### 9. Integração com FastAPI

                return client.transcribe(url, use_youtube=False)

            time.sleep(2 ** attempt)```python

```from fastapi import FastAPI, HTTPException

import httpx

### Cache de Resultados

app = FastAPI()

```pythonWHISPER_API_URL = "http://localhost:8000"

import hashlib, json, os

@app.post("/transcrever")

def transcribe_cached(url, cache_dir="./cache"):async def transcrever(youtube_url: str):

    url_hash = hashlib.md5(url.encode()).hexdigest()    async with httpx.AsyncClient() as client:

    cache_file = f"{cache_dir}/{url_hash}.json"        try:

                response = await client.post(

    if os.path.exists(cache_file):                f"{WHISPER_API_URL}/api/v1/transcribe",

        with open(cache_file) as f:                json={"youtube_url": youtube_url},

            return json.load(f)                timeout=600.0

                )

    result = client.transcribe(url)            

                if response.status_code == 200:

    os.makedirs(cache_dir, exist_ok=True)                return response.json()

    with open(cache_file, 'w') as f:            else:

        json.dump(result, f)                raise HTTPException(

                        status_code=response.status_code,

    return result                    detail=response.json()

```                )

                

---        except httpx.TimeoutException:

            raise HTTPException(

**💡 Sempre use `/video/info` primeiro para escolher o melhor método!**                status_code=504,

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
