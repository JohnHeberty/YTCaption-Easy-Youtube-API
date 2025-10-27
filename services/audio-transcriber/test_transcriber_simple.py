"""
Teste simples do serviço audio-transcriber
"""
import requests
import time
import json
from pathlib import Path

API_URL = "http://localhost:8002"
OUTPUT_DIR = Path("../../tests/output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def log_result(message, data=None):
    """Salva resultado no arquivo"""
    output_file = OUTPUT_DIR / "transcriber_test_results.txt"
    with open(output_file, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*80}\n")
        f.write(f"{message}\n")
        if data:
            f.write(f"{json.dumps(data, indent=2, default=str)}\n")
    print(message)
    if data:
        print(json.dumps(data, indent=2, default=str))

def test_health():
    """Testa endpoint de health"""
    log_result("🏥 TESTE: Health Check")
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        log_result(f"✅ Status: {response.status_code}", response.json())
        return response.status_code == 200
    except Exception as e:
        log_result(f"❌ Erro: {e}")
        return False

def create_test_audio():
    """Cria arquivo de áudio de teste"""
    log_result("🎵 Criando arquivo de teste...")
    import subprocess
    result = subprocess.run([
        "docker", "exec", "audio-transcriber-api",
        "python", "-c",
        "from pydub.generators import Sine; audio = Sine(440).to_audio_segment(duration=2000); audio.export('/app/uploads/test_transcriber.wav', format='wav')"
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        log_result("✅ Arquivo criado")
        return True
    else:
        log_result(f"❌ Erro ao criar arquivo: {result.stderr}")
        return False

def test_transcription():
    """Testa transcrição de áudio"""
    log_result("🎙️ TESTE: Transcrição de Áudio")
    
    # Lê o arquivo de teste
    audio_file = Path("./uploads/test_transcriber.wav")
    if not audio_file.exists():
        log_result(f"❌ Arquivo não encontrado: {audio_file}")
        return False
    
    try:
        # Envia para transcrição
        with open(audio_file, "rb") as f:
            files = {"file": ("test.wav", f, "audio/wav")}
            data = {
                "language": "pt",
                "task": "transcribe"
            }
            
            log_result("📤 Enviando arquivo para transcrição...")
            response = requests.post(
                f"{API_URL}/jobs",
                files=files,
                data=data,
                timeout=10
            )
            
            if response.status_code != 200:
                log_result(f"❌ Erro ao criar job: {response.status_code}", response.json())
                return False
            
            job_data = response.json()
            job_id = job_data.get("id")
            log_result(f"✅ Job criado: {job_id}", job_data)
            
            # Aguarda conclusão (máximo 2 minutos)
            max_attempts = 60
            for attempt in range(max_attempts):
                time.sleep(2)
                status_response = requests.get(f"{API_URL}/jobs/{job_id}", timeout=5)
                
                if status_response.status_code != 200:
                    log_result(f"❌ Erro ao consultar status")
                    return False
                
                status_data = status_response.json()
                status = status_data.get("status")
                progress = status_data.get("progress", 0)
                
                print(f"   [{attempt+1}] Status: {status}, Progress: {progress}%")
                
                if status == "completed":
                    log_result(f"✅ Transcrição completada em {(attempt+1)*2}s", status_data)
                    return True
                elif status == "failed":
                    log_result(f"❌ Transcrição falhou", status_data)
                    return False
            
            log_result(f"⏰ Timeout: transcrição não completou em {max_attempts*2}s")
            return False
            
    except Exception as e:
        log_result(f"❌ Erro: {e}")
        return False

def test_resilience():
    """Testa resiliência da API"""
    log_result("🛡️ TESTE: Resiliência da API")
    
    success_count = 0
    total_tests = 10
    
    for i in range(total_tests):
        try:
            response = requests.get(f"{API_URL}/health", timeout=5)
            if response.status_code == 200:
                success_count += 1
                print(f"   [{i+1}/{total_tests}] ✅ API respondendo")
            else:
                print(f"   [{i+1}/{total_tests}] ❌ Status: {response.status_code}")
        except Exception as e:
            print(f"   [{i+1}/{total_tests}] ❌ Erro: {e}")
        
        time.sleep(0.5)
    
    log_result(f"Resiliência: {success_count}/{total_tests} requisições bem-sucedidas")
    return success_count == total_tests

def main():
    """Executa todos os testes"""
    # Limpa arquivo de resultados
    output_file = OUTPUT_DIR / "transcriber_test_results.txt"
    if output_file.exists():
        output_file.unlink()
    
    log_result("🚀 INICIANDO TESTES DO AUDIO-TRANSCRIBER")
    log_result(f"📅 {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {
        "Health Check": test_health(),
        "Criar Áudio": create_test_audio(),
        "Transcrição": test_transcription(),
        "Resiliência": test_resilience()
    }
    
    log_result("\n📊 RESUMO DOS TESTES")
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSOU" if result else "❌ FALHOU"
        log_result(f"{test_name}: {status}")
    
    log_result(f"\nTotal: {passed}/{total} testes passaram")
    log_result(f"Taxa de sucesso: {(passed/total)*100:.1f}%")
    
    if passed == total:
        log_result("🎉 TODOS OS TESTES PASSARAM!")
    else:
        log_result("⚠️ ALGUNS TESTES FALHARAM")
    
    print(f"\n📄 Resultados salvos em: {output_file}")

if __name__ == "__main__":
    main()
