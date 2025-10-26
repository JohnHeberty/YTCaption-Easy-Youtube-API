#!/usr/bin/env python3
"""
🧪 SCRIPT DE TESTE DE RESILIÊNCIA COMPLETO
==========================================

Testa TODOS os 5 parâmetros booleanos de processamento de áudio:
1. apply_highpass_filter=True
2. remove_noise=True  
3. isolate_vocals=True
4. convert_to_mono=True
5. set_sample_rate_16k=True

OBJETIVO: Provar que o sistema é RESILIENTE e que:
- Tasks que falham não derrubam a API
- Endpoint /jobs/{job_id} sempre responde
- Erros são capturados e reportados corretamente
- Jobs bem-sucedidos completam normalmente
"""

import requests
import time
import json
import sys
from pathlib import Path
import traceback


class ResilienceValidator:
    def __init__(self, base_url="http://localhost:8001"):
        self.base_url = base_url
        self.results = []
        
    def print_banner(self, text):
        """Imprime banner formatado"""
        print(f"\n{'='*80}")
        print(f"  {text}")
        print(f"{'='*80}")
    
    def print_status(self, emoji, status, details=""):
        """Imprime status formatado"""
        print(f"{emoji} {status:40} | {details}")
    
    def create_test_file(self):
        """Cria arquivo de teste para upload"""
        # Cria arquivo simulando .webm com tamanho razoável
        test_content = b"RIFF" + b"a" * 2000 + b"WEBMVP80" + b"x" * 5000
        test_file = Path("test_resilience.webm")
        
        with open(test_file, 'wb') as f:
            f.write(test_content)
            
        return test_file
    
    def submit_job(self, test_name, params):
        """Submete um job de teste"""
        self.print_status("🚀", f"Submetendo job: {test_name}")
        
        try:
            test_file = self.create_test_file()
            
            with open(test_file, 'rb') as f:
                files = {'file': ('test_resilience.webm', f, 'audio/webm')}
                
                # Parâmetros base + parâmetros de teste
                data = {
                    'normalize': 'true',
                    'output_format': 'webm',
                    **params
                }
                
                response = requests.post(f"{self.base_url}/jobs", files=files, data=data, timeout=30)
                
                if response.status_code == 200:
                    job_data = response.json()
                    job_id = job_data.get('id')
                    self.print_status("✅", f"Job criado: {job_id}", f"Status: {response.status_code}")
                    return job_id, True, None
                else:
                    error_msg = response.text[:100]
                    self.print_status("❌", f"Falha ao criar job", f"Status: {response.status_code}, Error: {error_msg}")
                    return None, False, f"HTTP {response.status_code}: {error_msg}"
                    
        except Exception as e:
            error_msg = str(e)[:100]
            self.print_status("💥", f"Exceção ao submeter job", error_msg)
            return None, False, f"Exception: {error_msg}"
        finally:
            # Limpa arquivo de teste
            try:
                test_file.unlink(missing_ok=True)
            except:
                pass
    
    def poll_job_status(self, job_id, test_name):
        """Faz polling do status do job até completar ou falhar"""
        self.print_status("🔍", f"Polling job {job_id}")
        
        max_polls = 60  # 5 minutos máximo (5s * 60)
        poll_count = 0
        final_status = None
        error_message = None
        api_survived = True
        
        while poll_count < max_polls:
            try:
                # TESTE CRÍTICO: Este endpoint NUNCA deve quebrar
                response = requests.get(f"{self.base_url}/jobs/{job_id}", timeout=10)
                
                if response.status_code == 200:
                    job_data = response.json()
                    status = job_data.get('status', 'unknown')
                    progress = job_data.get('progress', 0)
                    error_msg = job_data.get('error_message')
                    
                    self.print_status("📊", f"Poll {poll_count+1:2d}/60", f"Status: {status}, Progress: {progress}%")
                    
                    # Status finais
                    if status in ['completed', 'failed', 'error', 'expired']:
                        final_status = status
                        error_message = error_msg
                        break
                        
                elif response.status_code == 404:
                    self.print_status("🚫", f"Job não encontrado", "Status: 404")
                    final_status = 'not_found'
                    break
                    
                elif response.status_code == 500:
                    # FALHA CRÍTICA: API quebrou
                    self.print_status("🔥", f"API QUEBROU!", f"Status: 500 - {response.text[:50]}")
                    api_survived = False
                    final_status = 'api_crashed'
                    error_message = f"API returned 500: {response.text[:100]}"
                    break
                    
                else:
                    self.print_status("⚠️", f"Status inesperado", f"HTTP {response.status_code}")
                    
            except requests.exceptions.Timeout:
                self.print_status("⏰", f"Timeout na consulta", "Request timeout")
                
            except requests.exceptions.ConnectionError:
                self.print_status("🔌", f"Conexão perdida", "Connection error")
                api_survived = False
                final_status = 'connection_lost'
                break
                
            except Exception as e:
                self.print_status("💥", f"Exceção no polling", str(e)[:50])
                
            poll_count += 1
            time.sleep(5)  # Aguarda 5 segundos
        
        if poll_count >= max_polls:
            self.print_status("⏰", f"Timeout no polling", "Job não finalizou em 5 minutos")
            final_status = 'timeout'
        
        return final_status, error_message, api_survived
    
    def run_test(self, test_name, params):
        """Executa um teste completo"""
        self.print_banner(f"TESTE: {test_name}")
        
        result = {
            'test_name': test_name,
            'params': params,
            'job_submitted': False,
            'job_id': None,
            'final_status': None,
            'error_message': None,
            'api_survived': True,
            'success': False
        }
        
        # 1. Submete job
        job_id, submitted, submit_error = self.submit_job(test_name, params)
        result['job_submitted'] = submitted
        result['job_id'] = job_id
        
        if not submitted:
            result['error_message'] = submit_error
            self.print_status("❌", f"RESULTADO: FALHA NA SUBMISSÃO", submit_error or "")
            self.results.append(result)
            return result
        
        # 2. Polling do status
        final_status, error_message, api_survived = self.poll_job_status(job_id, test_name)
        result['final_status'] = final_status
        result['error_message'] = error_message
        result['api_survived'] = api_survived
        
        # 3. Avaliação do resultado
        if not api_survived:
            self.print_status("🔥", f"RESULTADO: API QUEBROU!", "FALHA CRÍTICA DE RESILIÊNCIA")
            result['success'] = False
        elif final_status == 'completed':
            self.print_status("🎉", f"RESULTADO: SUCESSO TOTAL", "Job processado com sucesso")
            result['success'] = True
        elif final_status in ['failed', 'error']:
            self.print_status("✅", f"RESULTADO: FALHA CONTROLADA", "Erro capturado corretamente")
            result['success'] = True  # Falha controlada é sucesso de resiliência!
        else:
            self.print_status("⚠️", f"RESULTADO: INCONCLUSIVO", f"Status final: {final_status}")
            result['success'] = False
        
        self.results.append(result)
        return result
    
    def run_all_tests(self):
        """Executa todos os testes de resiliência"""
        self.print_banner("🧪 INICIANDO TESTES DE RESILIÊNCIA")
        print("Objetivo: Provar que tasks falhadas não derrubam a API")
        print("Sucesso = API sempre responde, mesmo com jobs que falham")
        
        # Define os 5 testes críticos
        tests = [
            ("High-pass Filter", {"apply_highpass_filter": "true"}),
            ("Noise Removal", {"remove_noise": "true"}),
            ("Vocal Isolation", {"isolate_vocals": "true"}),
            ("Convert to Mono", {"convert_to_mono": "true"}),
            ("Sample Rate 16k", {"set_sample_rate_16k": "true"}),
        ]
        
        # Executa cada teste
        for test_name, params in tests:
            try:
                self.run_test(test_name, params)
                time.sleep(2)  # Pausa entre testes
            except KeyboardInterrupt:
                print("\n🛑 Testes interrompidos pelo usuário")
                break
            except Exception as e:
                print(f"\n💥 Erro crítico no teste {test_name}: {e}")
                traceback.print_exc()
        
        # Relatório final
        self.print_final_report()
    
    def print_final_report(self):
        """Imprime relatório final dos testes"""
        self.print_banner("📊 RELATÓRIO FINAL DE RESILIÊNCIA")
        
        total_tests = len(self.results)
        successful_tests = sum(1 for r in self.results if r['success'])
        api_crashes = sum(1 for r in self.results if not r['api_survived'])
        
        print(f"Total de testes: {total_tests}")
        print(f"Sucessos: {successful_tests}")
        print(f"Falhas: {total_tests - successful_tests}")
        print(f"Crashes da API: {api_crashes}")
        
        print("\nDetalhamento por teste:")
        print("-" * 80)
        
        for result in self.results:
            status_emoji = "✅" if result['success'] else "❌"
            api_emoji = "🔥" if not result['api_survived'] else "✅"
            
            print(f"{status_emoji} {result['test_name']:20} | API: {api_emoji} | Status: {result['final_status']:15} | Job: {result['job_id'] or 'N/A'}")
            
            if result['error_message']:
                print(f"   Erro: {result['error_message'][:60]}...")
        
        # Veredicto final
        print("\n" + "="*80)
        
        if api_crashes == 0:
            if successful_tests == total_tests:
                print("🎉 PERFEITO! API é 100% resiliente - nenhum crash detectado")
                success_rate = 100
            else:
                print("✅ BOA! API resiliente - nenhum crash, alguns testes inconclusivos")
                success_rate = (successful_tests / total_tests) * 100
        else:
            print("🔥 FALHA CRÍTICA! API quebrou durante testes - resiliência inadequada")
            success_rate = 0
        
        print(f"Taxa de sucesso: {success_rate:.1f}%")
        
        if success_rate >= 80:
            print("✅ Sistema aprovado nos testes de resiliência")
        else:
            print("❌ Sistema reprovado - necessita correções")
        
        return success_rate >= 80


def main():
    """Função principal"""
    print("🧪 VALIDADOR DE RESILIÊNCIA - AUDIO NORMALIZATION")
    print("=" * 60)
    print("Este script testa se o sistema é resiliente a falhas de processamento")
    print("Objetivo: API nunca deve quebrar, mesmo com tasks que falham")
    
    # Verifica se serviço está online
    validator = ResilienceValidator()
    
    try:
        response = requests.get(f"{validator.base_url}/health", timeout=5)
        if response.status_code != 200:
            print(f"❌ Serviço não está saudável: {response.status_code}")
            return False
    except:
        print("❌ Serviço não está online. Inicie o audio-normalization primeiro!")
        return False
    
    print("✅ Serviço online - iniciando testes")
    
    # Executa testes
    validator.run_all_tests()
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)