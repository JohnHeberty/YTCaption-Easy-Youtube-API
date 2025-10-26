#!/usr/bin/env python3
"""
Script para testar via curl real o comando que estava falhando
"""

import subprocess
import json

def test_curl_real():
    """Testa o comando curl exato que estava falhando"""
    print("🎵 TESTE FINAL - CURL REAL")
    print("Comando que estava falhando:")
    print("curl -F 'file=@test_file_larger.webm;type=video/webm' http://localhost:8001/jobs")
    print("=" * 80)
    
    try:
        # Executar o comando curl real
        cmd = [
            'curl', '-X', 'POST',
            '-F', 'file=@test_file_larger.webm;type=video/webm',
            '-F', 'normalize=true',
            '-F', 'remove_noise=false',
            '-F', 'vocal_isolation=false', 
            '-F', 'output_format=webm',
            'http://localhost:8001/jobs'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        print(f"Return Code: {result.returncode}")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        
        if result.returncode == 0:
            print("✅ CURL COMMAND SUCCESS!")
            try:
                response_data = json.loads(result.stdout)
                print(f"Job ID: {response_data.get('id')}")
                print(f"Status: {response_data.get('status')}")
                print(f"Filename: {response_data.get('filename')}")
            except:
                print("Response is not JSON")
        else:
            print("❌ CURL COMMAND FAILED!")
            
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")

if __name__ == "__main__":
    test_curl_real()