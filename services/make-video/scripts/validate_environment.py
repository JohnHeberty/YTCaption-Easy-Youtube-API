#!/usr/bin/env python3
"""
Script de validação de ambiente

Valida que todas as dependências estão instaladas e configuradas
"""

import sys
import subprocess
import os
from typing import List, Tuple


def check_command(command: str) -> bool:
    """Verifica se comando está disponível"""
    try:
        subprocess.run(
            ['which', command],
            capture_output=True,
            check=True
        )
        return True
    except subprocess.CalledProcessError:
        return False


def check_python_package(package: str) -> bool:
    """Verifica se pacote Python está instalado"""
    try:
        __import__(package)
        return True
    except ImportError:
        return False


def check_directory(path: str) -> bool:
    """Verifica se diretório existe"""
    return os.path.isdir(path)


def validate_environment() -> List[Tuple[str, bool, str]]:
    """
    Valida ambiente completo
    
    Returns:
        Lista de (check_name, passed, message)
    """
    results = []
    
    # Sistema
    results.append((
        'FFmpeg',
        check_command('ffmpeg'),
        'Required for video/audio processing'
    ))
    
    results.append((
        'ffprobe',
        check_command('ffprobe'),
        'Required for video validation'
    ))
    
    results.append((
        'tesseract',
        check_command('tesseract'),
        'Required for OCR detection'
    ))
    
    # Python packages
    packages = [
        ('torch', 'PyTorch for VAD'),
        ('cv2', 'OpenCV for video processing'),
        ('pytesseract', 'Tesseract wrapper'),
        ('redis', 'Redis client'),
        ('prometheus_client', 'Prometheus metrics'),
        ('pysrt', 'SRT subtitle parser'),
    ]
    
    for package, description in packages:
        results.append((
            f'Python: {package}',
            check_python_package(package),
            description
        ))
    
    # Diretórios
    directories = [
        'storage',
        'storage/video_cache',
        'storage/audio_cache',
        'storage/shorts_cache',
        'models',
        'logs',
    ]
    
    for directory in directories:
        results.append((
            f'Directory: {directory}',
            check_directory(directory),
            'Required storage directory'
        ))
    
    return results


def main():
    """Executa validação e exibe resultados"""
    print("🔍 Validating environment...\n")
    
    results = validate_environment()
    
    passed = 0
    failed = 0
    
    for check_name, success, message in results:
        status = '✅' if success else '❌'
        print(f"{status} {check_name:30s} - {message}")
        
        if success:
            passed += 1
        else:
            failed += 1
    
    print(f"\n📊 Results: {passed} passed, {failed} failed")
    
    if failed > 0:
        print("\n⚠️  Some checks failed. Please install missing dependencies.")
        sys.exit(1)
    else:
        print("\n✅ All checks passed! Environment is ready.")
        sys.exit(0)


if __name__ == '__main__':
    main()
