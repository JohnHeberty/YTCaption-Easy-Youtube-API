#!/usr/bin/env python3
"""
Teste simples para verificar se o endpoint funciona
"""
import requests
import json
import io
import wave
import struct

def create_test_audio():
    """Cria um pequeno arquivo WAV de teste na memória"""
    # Parâmetros do áudio
    sample_rate = 44100
    duration = 1  # 1 segundo
    frequency = 440  # Nota A4
    
    # Gera onda senoidal
    samples = []
    for i in range(int(sample_rate * duration)):
        time = i / sample_rate
        amplitude = 0.5 * (1 << 15 - 1)  # 50% do volume máximo
        sample = int(amplitude * (
            0.5 * (1 + 0.5 * (i / (sample_rate * duration)))  # Fade in
        ))
        samples.append(struct.pack('<h', sample))
    
    # Cria arquivo WAV na memória
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b''.join(samples))
    
    wav_buffer.seek(0)
    return wav_buffer

def test_basic_job():
    url = "http://localhost:8001/jobs"
    
    print("🧪 Testando endpoint básico...")
    try:
        # Cria arquivo de teste
        audio_data = create_test_audio()
        
        # Parâmetros do form
        files = {
            'file': ('test_audio.wav', audio_data.getvalue(), 'audio/wav')
        }
        data = {
            'apply_highpass_filter': 'false',
            'remove_noise': 'false',
            'isolate_vocals': 'false',
            'convert_to_mono': 'false',
            'set_sample_rate_16k': 'false'
        }
        
        response = requests.post(url, files=files, data=data, timeout=30)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200 or response.status_code == 201:
            job_data = response.json()
            job_id = job_data.get('id')
            print(f"✅ Job criado: {job_id}")
            
            # Verificar status
            status_url = f"http://localhost:8001/jobs/{job_id}"
            status_response = requests.get(status_url)
            print(f"Status response: {status_response.json()}")
        else:
            print(f"❌ Erro: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Exceção: {e}")

if __name__ == "__main__":
    test_basic_job()