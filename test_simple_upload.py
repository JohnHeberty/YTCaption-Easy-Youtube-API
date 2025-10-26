#!/usr/bin/env python3
"""
Script simplificado para testar o upload de arquivos
"""

import requests
import json

# Configuração
API_URL = "http://localhost:8001"

def test_upload_simple():
    """Testa o upload de um arquivo simples simulando o curl problemático"""
    print("🎵 TESTANDO UPLOAD WEBM com MIME video/webm")
    print("Simulando: curl -F 'file=@file.webm;type=video/webm'")
    print("=" * 60)
    
    try:
        with open("test_file_larger.webm", 'rb') as f:
            files = {
                'file': ('test_file_larger.webm', f, 'video/webm')
            }
            
            # Dados do formulário
            data = {
                'normalize': 'true',
                'remove_noise': 'false', 
                'vocal_isolation': 'false',
                'output_format': 'webm'
            }
            
            response = requests.post(f"{API_URL}/jobs", files=files, data=data)
            
            print(f"Status Code: {response.status_code}")
            print(f"Response Headers: {dict(response.headers)}")
            print(f"Response Text: {response.text}")
            
            if response.status_code == 200:
                print("✅ SUCCESS - Upload aceito!")
                result = response.json()
                print(f"Job ID: {result.get('job_id')}")
                return True
            else:
                print("❌ FAILED - Upload rejeitado!")
                try:
                    error_detail = response.json()
                    print(f"Error detail: {error_detail}")
                except:
                    pass
                return False
                
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        return False

if __name__ == "__main__":
    test_upload_simple()