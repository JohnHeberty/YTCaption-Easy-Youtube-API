#!/usr/bin/env python3
"""
Script de teste com POLLING para Audio Transcriber Service
Testa o fluxo COMPLETO de job: upload -> transcrição -> conclusão

USO:
    python test_transcriber_polling.py <caminho_para_arquivo_audio>

EXEMPLO:
    python test_transcriber_polling.py audio.mp3
    python test_transcriber_polling.py sample.wav
    
NOTA: Aceita arquivos de áudio em diversos formatos
"""

import requests
import time
import sys
import os
from pathlib import Path
from datetime import datetime


# Configuração do serviço
BASE_URL = "http://localhost:8001"
POLLING_INTERVAL = 3  # segundos entre cada consulta
MAX_WAIT_TIME = 600  # timeout de 10 minutos (transcrição pode demorar)


def print_header(title: str):
    """Imprime cabeçalho formatado"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def print_status(message: str, status: str = "INFO"):
    """Imprime mensagem de status formatada"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    symbols = {
        "INFO": "ℹ️",
        "SUCCESS": "✅",
        "ERROR": "❌",
        "WAIT": "⏳",
        "PROCESSING": "🔄"
    }
    symbol = symbols.get(status, "•")
    print(f"[{timestamp}] {symbol} {message}")


def test_health_check():
    """Verifica se o serviço está online"""
    print_header("VERIFICANDO SERVIÇO")
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print_status(f"Serviço ONLINE: {data.get('service', 'N/A')}", "SUCCESS")
            print_status(f"Versão: {data.get('version', 'N/A')}", "INFO")
            return True
        else:
            print_status(f"Serviço retornou status {response.status_code}", "ERROR")
            return False
    except requests.exceptions.RequestException as e:
        print_status(f"Não foi possível conectar ao serviço: {e}", "ERROR")
        return False


def create_transcription_job(audio_file_path: str):
    """
    Cria um job de transcrição de áudio
    
    Args:
        audio_file_path: Caminho para o arquivo de áudio
    
    Returns:
        tuple: (job_id, response_data) ou (None, None) em caso de erro
    """
    print_header("CRIANDO JOB DE TRANSCRIÇÃO")
    
    # Verifica se arquivo existe
    if not os.path.exists(audio_file_path):
        print_status(f"Arquivo não encontrado: {audio_file_path}", "ERROR")
        return None, None
    
    file_path = Path(audio_file_path)
    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    
    print_status(f"Arquivo: {file_path.name}", "INFO")
    print_status(f"Tamanho: {file_size_mb:.2f} MB", "INFO")
    print_status(f"Formato: {file_path.suffix}", "INFO")
    
    try:
        # Abre o arquivo e envia
        with open(audio_file_path, 'rb') as f:
            files = {'file': (file_path.name, f, 'audio/*')}
            
            response = requests.post(
                f"{BASE_URL}/jobs",
                files=files,
                timeout=30
            )
        
        if response.status_code == 200:
            data = response.json()
            job_id = data.get('id')
            print_status(f"Job criado com sucesso!", "SUCCESS")
            print_status(f"Job ID: {job_id}", "INFO")
            print_status(f"Status inicial: {data.get('status')}", "INFO")
            return job_id, data
        else:
            print_status(f"Erro ao criar job: Status {response.status_code}", "ERROR")
            try:
                error_data = response.json()
                print_status(f"Detalhes: {error_data}", "ERROR")
            except:
                print_status(f"Resposta: {response.text[:200]}", "ERROR")
            return None, None
            
    except Exception as e:
        print_status(f"Erro ao enviar request: {e}", "ERROR")
        return None, None


def poll_job_status(job_id: str):
    """
    Faz polling do status do job até completar ou falhar
    
    Args:
        job_id: ID do job a ser monitorado
    
    Returns:
        dict: Dados finais do job ou None em caso de erro
    """
    print_header("MONITORANDO TRANSCRIÇÃO (POLLING)")
    print_status(f"Consultando status a cada {POLLING_INTERVAL}s", "INFO")
    print_status(f"Timeout máximo: {MAX_WAIT_TIME}s ({MAX_WAIT_TIME//60} minutos)", "INFO")
    
    start_time = time.time()
    last_status = None
    last_progress = None
    
    while True:
        elapsed_time = time.time() - start_time
        
        # Verifica timeout
        if elapsed_time > MAX_WAIT_TIME:
            print_status(f"TIMEOUT! Job não completou em {MAX_WAIT_TIME}s", "ERROR")
            return None
        
        try:
            # Consulta status do job
            response = requests.get(f"{BASE_URL}/jobs/{job_id}", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                current_status = data.get('status')
                current_progress = data.get('progress', 0)
                
                # Mostra atualização apenas se status ou progresso mudaram
                if current_status != last_status or current_progress != last_progress:
                    status_symbol = "PROCESSING" if current_status in ['queued', 'processing'] else "INFO"
                    print_status(
                        f"Status: {current_status.upper()} | Progresso: {current_progress:.1f}% | Tempo: {elapsed_time:.1f}s",
                        status_symbol
                    )
                    last_status = current_status
                    last_progress = current_progress
                
                # Verifica se completou
                if current_status == 'completed':
                    print_status(f"TRANSCRIÇÃO COMPLETADA! Tempo total: {elapsed_time:.1f}s", "SUCCESS")
                    return data
                
                # Verifica se falhou
                elif current_status == 'failed':
                    error_msg = data.get('error_message', 'Erro desconhecido')
                    print_status(f"JOB FALHOU: {error_msg}", "ERROR")
                    return data
                
                # Continua aguardando
                time.sleep(POLLING_INTERVAL)
                
            elif response.status_code == 404:
                print_status(f"Job não encontrado", "ERROR")
                return None
            
            else:
                print_status(f"Erro ao consultar status: {response.status_code}", "ERROR")
                time.sleep(POLLING_INTERVAL)
        
        except requests.exceptions.RequestException as e:
            print_status(f"Erro de conexão: {e}", "ERROR")
            time.sleep(POLLING_INTERVAL)


def get_transcription_text(job_id: str):
    """
    Obtém o texto da transcrição
    
    Args:
        job_id: ID do job
    
    Returns:
        str: Texto transcrito ou None em caso de erro
    """
    try:
        response = requests.get(f"{BASE_URL}/jobs/{job_id}/text", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('text', '')
        else:
            print_status(f"Erro ao obter texto: Status {response.status_code}", "ERROR")
            return None
            
    except Exception as e:
        print_status(f"Erro ao obter texto: {e}", "ERROR")
        return None


def download_srt_file(job_id: str, output_path: str = None):
    """
    Faz download do arquivo SRT
    
    Args:
        job_id: ID do job
        output_path: Caminho para salvar o arquivo (opcional)
    
    Returns:
        bool: True se download foi bem sucedido
    """
    print_header("FAZENDO DOWNLOAD DO ARQUIVO SRT")
    
    if output_path is None:
        output_path = f"transcription_{job_id}.srt"
    
    try:
        response = requests.get(f"{BASE_URL}/jobs/{job_id}/download", timeout=30)
        
        if response.status_code == 200:
            with open(output_path, 'wb') as f:
                f.write(response.content)
            
            file_size_kb = len(response.content) / 1024
            print_status(f"Arquivo SRT salvo: {output_path}", "SUCCESS")
            print_status(f"Tamanho: {file_size_kb:.2f} KB", "INFO")
            return True
        else:
            print_status(f"Erro ao fazer download: Status {response.status_code}", "ERROR")
            return False
            
    except Exception as e:
        print_status(f"Erro no download: {e}", "ERROR")
        return False


def print_final_summary(job_data: dict, transcription_text: str = None):
    """Imprime resumo final do job"""
    print_header("RESUMO FINAL DA TRANSCRIÇÃO")
    
    print(f"""
    Job ID:              {job_data.get('id')}
    Status:              {job_data.get('status').upper()}
    Arquivo de entrada:  {Path(job_data.get('input_file', 'N/A')).name}
    Arquivo de saída:    {Path(job_data.get('output_file', 'N/A')).name}
    Tamanho entrada:     {job_data.get('file_size_input', 0) / 1024:.2f} KB
    Tamanho saída:       {job_data.get('file_size_output', 0) / 1024:.2f} KB
    Progresso:           {job_data.get('progress', 0):.1f}%
    Criado em:           {job_data.get('created_at', 'N/A')}
    Completado em:       {job_data.get('completed_at', 'N/A')}
    """)
    
    if transcription_text:
        print("\n" + "─" * 70)
        print("TEXTO TRANSCRITO (Primeiras 500 caracteres):")
        print("─" * 70)
        preview = transcription_text[:500]
        if len(transcription_text) > 500:
            preview += "..."
        print(preview)
        print("─" * 70)
        print(f"Total de caracteres: {len(transcription_text)}")


def main():
    """Função principal"""
    print_header("TESTE DE JOB COM POLLING - AUDIO TRANSCRIBER")
    
    # Verifica argumentos
    if len(sys.argv) < 2:
        print("\n❌ ERRO: Arquivo de áudio não especificado")
        print("\nUSO:")
        print("    python test_transcriber_polling.py <arquivo_audio>")
        print("\nEXEMPLOS:")
        print("    python test_transcriber_polling.py audio.mp3")
        print("    python test_transcriber_polling.py sample.wav")
        sys.exit(1)
    
    audio_file = sys.argv[1]
    
    # 1. Verifica se serviço está online
    if not test_health_check():
        print("\n❌ Serviço não está disponível. Inicie o serviço e tente novamente.")
        sys.exit(1)
    
    # 2. Cria job
    job_id, job_data = create_transcription_job(audio_file)
    if not job_id:
        print("\n❌ Não foi possível criar o job.")
        sys.exit(1)
    
    # 3. Faz polling até completar
    final_data = poll_job_status(job_id)
    if not final_data:
        print("\n❌ Erro durante monitoramento do job.")
        sys.exit(1)
    
    # 4. Se completou, obtém texto e faz download
    transcription_text = None
    if final_data.get('status') == 'completed':
        print_header("OBTENDO RESULTADO")
        
        # Obtém texto
        transcription_text = get_transcription_text(job_id)
        if transcription_text:
            print_status(f"Texto obtido: {len(transcription_text)} caracteres", "SUCCESS")
        
        # Faz download do SRT
        output_file = f"transcription_{Path(audio_file).stem}.srt"
        download_srt_file(job_id, output_file)
    
    # 5. Exibe resumo
    print_final_summary(final_data, transcription_text)
    
    # Status final
    if final_data.get('status') == 'completed':
        print("\n✅ TESTE CONCLUÍDO COM SUCESSO!")
        print(f"\n📁 Arquivo SRT salvo como: transcription_{Path(audio_file).stem}.srt")
        sys.exit(0)
    else:
        print("\n❌ TESTE FALHOU!")
        sys.exit(1)


if __name__ == "__main__":
    main()
