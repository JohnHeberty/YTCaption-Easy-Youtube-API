#!/usr/bin/env python3
"""
Teste das opções que anteriormente falhavam
"""
import requests
import json
import io
import wave
import struct
import time

def create_test_audio():
    """Cria um pequeno arquivo WAV de teste na memória"""
    # Parâmetros do áudio
    sample_rate = 44100
    duration = 1  # 1 segundo
    frequency = 440  # Nota A4
    
    # Gera onda senoidal
    samples = []
    for i in range(int(sample_rate * duration)):
        time_val = i / sample_rate
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

def test_problematic_options():
    """Testa as 3 opções que anteriormente causavam falhas"""
    url = "http://localhost:8001/jobs"
    
    tests = [
        ("apply_highpass_filter", {'apply_highpass_filter': 'true'}),
        ("remove_noise", {'remove_noise': 'true'}),
        ("isolate_vocals", {'isolate_vocals': 'true'})
    ]
    
    for test_name, params in tests:
        print(f"\n🧪 Testando: {test_name}")
        print("=" * 50)
        
        try:
            # Cria arquivo de teste
            audio_data = create_test_audio()
            
            # Parâmetros do form
            files = {
                'file': ('test_audio.wav', audio_data.getvalue(), 'audio/wav')
            }
            
            # Base data
            data = {
                'apply_highpass_filter': 'false',
                'remove_noise': 'false',
                'isolate_vocals': 'false',
                'convert_to_mono': 'false',
                'set_sample_rate_16k': 'false'
            }
            # Aplica o parâmetro específico do teste
            data.update(params)
            
            # Submete job
            response = requests.post(url, files=files, data=data, timeout=30)
            print(f"📤 Submit: {response.status_code}")
            
            if response.status_code != 200:
                print(f"❌ Falha ao criar job: {response.text}")
                continue
                
            job_data = response.json()
            job_id = job_data.get('id')
            print(f"✅ Job criado: {job_id}")
            
            # Polling do status
            status_url = f"http://localhost:8001/jobs/{job_id}"
            max_polls = 10
            poll_count = 0
            
            while poll_count < max_polls:
                poll_count += 1
                status_response = requests.get(status_url)
                
                if status_response.status_code != 200:
                    print(f"❌ Erro ao consultar status: {status_response.status_code}")
                    break
                    
                status_data = status_response.json()
                status = status_data.get('status', 'unknown')
                progress = status_data.get('progress', 0)
                error = status_data.get('error_message')
                
                print(f"📊 Poll {poll_count}: {status} ({progress}%)")
                
                if status == 'completed':
                    print(f"✅ {test_name}: SUCESSO!")
                    print(f"   Output: {status_data.get('output_file', 'N/A')}")
                    break
                elif status == 'failed':
                    print(f"❌ {test_name}: FALHOU")
                    print(f"   Erro: {error}")
                    break
                elif status in ['processing', 'queued']:
                    time.sleep(2)  # Aguarda 2 segundos
                else:
                    print(f"⚠️ Status desconhecido: {status}")
                    break
            else:
                print(f"⏰ {test_name}: TIMEOUT após {max_polls} polls")
                
        except Exception as e:
            print(f"❌ Exceção em {test_name}: {e}")

if __name__ == "__main__":
    test_problematic_options()