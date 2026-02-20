"""
Script de Monitoramento de Logs - Test-Prod

Monitora logs de jobs em tempo real para validar correções
"""

import sys
import time
import argparse
from pathlib import Path
from datetime import datetime
import json


def monitor_job_logs(log_dir: Path, job_id: str, follow: bool = False):
    """
    Monitora logs de um job específico
    
    Args:
        log_dir: Diretório de logs
        job_id: ID do job a monitorar
        follow: Se True, continua monitorando (tail -f)
    """
    
    job_log = log_dir / f"job_{job_id}.log"
    
    if not job_log.exists():
        print(f"❌ Log não encontrado: {job_log}")
        print(f"\n📁 Logs disponíveis em {log_dir}:")
        for log_file in sorted(log_dir.glob("job_*.log"))[-10:]:
            print(f"   - {log_file.name}")
        return
    
    print("="*80)
    print(f"📊 Monitorando Job: {job_id}")
    print("="*80)
    print(f"📁 Log: {job_log}")
    print(f"📏 Tamanho: {job_log.stat().st_size} bytes")
    print(f"🕐 Modificado: {datetime.fromtimestamp(job_log.stat().st_mtime)}")
    print("="*80)
    
    # Keywords críticas para destacar
    keywords = {
        "error": "🔴",
        "critical": "🔴",
        "exception": "🔴",
        "warning": "🟡",
        "failed": "🔴",
        "success": "🟢",
        "completed": "🟢",
        "subtitle": "📝",
        "srt": "📝",
        "vad": "🎙️",
        "transcr": "🎤",
        "burn": "🔥",
        "empty": "⚠️"
    }
    
    def highlight_line(line: str) -> str:
        """Adiciona emoji se linha contém keyword"""
        line_lower = line.lower()
        for keyword, emoji in keywords.items():
            if keyword in line_lower:
                return f"{emoji} {line}"
        return line
    
    # Ler log
    try:
        with open(job_log, 'r') as f:
            if follow:
                # Modo follow (tail -f)
                f.seek(0, 2)  # Ir para fim do arquivo
                print("\n⏳ Aguardando novas linhas (Ctrl+C para sair)...\n")
                
                while True:
                    line = f.readline()
                    if line:
                        print(highlight_line(line.rstrip()))
                    else:
                        time.sleep(0.1)
            else:
                # Ler arquivo completo
                lines = f.readlines()
                
                print(f"\n📋 {len(lines)} linhas no log:\n")
                
                for line in lines:
                    print(highlight_line(line.rstrip()))
    
    except KeyboardInterrupt:
        print("\n\n⏹️  Monitoramento interrompido")
    except Exception as e:
        print(f"\n❌ Erro lendo log: {e}")


def search_logs_for_errors(log_dir: Path, recent_hours: int = 24):
    """
    Busca erros em logs recentes
    
    Args:
        log_dir: Diretório de logs
        recent_hours: Buscar logs das últimas X horas
    """
    
    print("="*80)
    print(f"🔍 Buscando erros em logs (últimas {recent_hours}h)")
    print("="*80)
    
    cutoff_time = time.time() - (recent_hours * 3600)
    
    errors_found = []
    
    for log_file in log_dir.glob("job_*.log"):
        if log_file.stat().st_mtime < cutoff_time:
            continue
        
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                
                for i, line in enumerate(lines, 1):
                    line_lower = line.lower()
                    if any(kw in line_lower for kw in ['error', 'exception', 'failed', 'critical']):
                        errors_found.append({
                            'file': log_file.name,
                            'line_num': i,
                            'content': line.rstrip(),
                            'timestamp': datetime.fromtimestamp(log_file.stat().st_mtime)
                        })
        except:
            continue
    
    if not errors_found:
        print(f"\n✅ Nenhum erro encontrado nos últimos {recent_hours}h")
        return
    
    print(f"\n❌ {len(errors_found)} erros encontrados:\n")
    
    for error in errors_found[-20:]:  # Mostrar últimos 20
        print(f"📁 {error['file']} (linha {error['line_num']})")
        print(f"🕐 {error['timestamp']}")
        print(f"   {error['content']}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Monitor job logs")
    parser.add_argument('--job-id', type=str, help="Job ID to monitor")
    parser.add_argument('--follow', '-f', action='store_true', help="Follow log (tail -f)")
    parser.add_argument('--search-errors', action='store_true', help="Search for errors in recent logs")
    parser.add_argument('--recent-hours', type=int, default=24, help="Hours to look back (default: 24)")
    parser.add_argument('--log-dir', type=str, default="/app/data/logs/app", help="Log directory")
    
    args = parser.parse_args()
    
    log_dir = Path(args.log_dir)
    
    if not log_dir.exists():
        print(f"❌ Diretório de logs não encontrado: {log_dir}")
        return 1
    
    if args.search_errors:
        search_logs_for_errors(log_dir, args.recent_hours)
    elif args.job_id:
        monitor_job_logs(log_dir, args.job_id, args.follow)
    else:
        print("❌ Especifique --job-id ou --search-errors")
        parser.print_help()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
