"""
Validador de User-Agents para garantir qualidade e eficácia
"""

import re
import logging
from typing import List, Tuple, Dict
from pathlib import Path

logger = logging.getLogger(__name__)


class UserAgentValidator:
    """
    Validador completo de User-Agents que verifica:
    - Formato e estrutura
    - Tamanho apropriado
    - Caracteres válidos
    - Blacklist de UAs problemáticos
    - Padrões de browsers legítimos
    """
    
    def __init__(self):
        # Padrões de UAs legítimos
        self.valid_patterns = [
            r'Mozilla/\d+\.\d+',  # Deve começar com Mozilla/X.X
            r'AppleWebKit/[\d.]+',  # Contém AppleWebKit
            r'Chrome/[\d.]+',  # Chrome version
            r'Safari/[\d.]+',  # Safari version
            r'Firefox/[\d.]+',  # Firefox version
            r'Edge/[\d.]+',  # Edge version
        ]
        
        # Blacklist de UAs problemáticos (bots, crawlers, etc.)
        self.blacklist_patterns = [
            r'bot',
            r'crawler',
            r'spider',
            r'scraper',
            r'fetcher',
            r'Googlebot',
            r'bingbot',
            r'facebookexternalhit',
            r'twitterbot',
            r'linkedinbot',
            r'whatsapp',
            r'telegrambot',
            r'slurp',  # Yahoo
            r'duckduckbot',
            r'baiduspider',
            r'yandexbot',
            r'archive.org_bot',
            r'ia_archiver',
            r'wayback',
            r'SemrushBot',
            r'AhrefsBot',
            r'MJ12bot',
            r'DotBot',
            r'proximic',
            r'nerdybot',
            r'WordPress.com mShots',
            r'Feedfetcher-Google',
            r'Mediapartners-Google',
            r'APIs-Google',
            # Ferramentas de teste
            r'curl/',
            r'wget/',
            r'python-requests',
            r'libwww-perl',
            r'HttpClient',
            # UAs suspeitos ou malformados
            r'The given key was not present in the dictionary',  # Erro conhecido
            r'compatible;?\s*$',  # Apenas "compatible"
            r'^\s*$',  # Vazio
        ]
        
        # Browsers legítimos que devem estar presentes
        self.legitimate_browsers = [
            'Chrome', 'Firefox', 'Safari', 'Edge', 'Opera', 
            'Internet Explorer', 'MSIE', 'Trident'
        ]
        
        # Tamanhos válidos
        self.min_length = 20
        self.max_length = 500
    
    def validate_user_agent(self, ua: str) -> Tuple[bool, List[str]]:
        """
        Valida um User-Agent individual
        
        Args:
            ua: User-Agent string para validar
            
        Returns:
            Tupla (is_valid, list_of_issues)
        """
        issues = []
        
        # 1. Verifica se não é None ou vazio
        if not ua or not ua.strip():
            issues.append("User-Agent está vazio")
            return False, issues
        
        ua = ua.strip()
        
        # 2. Verifica tamanho
        if len(ua) < self.min_length:
            issues.append(f"Muito curto ({len(ua)} chars, mín: {self.min_length})")
        
        if len(ua) > self.max_length:
            issues.append(f"Muito longo ({len(ua)} chars, máx: {self.max_length})")
        
        # 3. Verifica caracteres válidos (ASCII printable)
        if not all(32 <= ord(c) <= 126 for c in ua):
            issues.append("Contém caracteres inválidos")
        
        # 4. Verifica blacklist (case-insensitive)
        for pattern in self.blacklist_patterns:
            if re.search(pattern, ua, re.IGNORECASE):
                issues.append(f"Contém padrão na blacklist: {pattern}")
                break
        
        # 5. Verifica se contém pelo menos um browser legítimo
        has_legitimate_browser = False
        for browser in self.legitimate_browsers:
            if browser.lower() in ua.lower():
                has_legitimate_browser = True
                break
        
        if not has_legitimate_browser:
            issues.append("Não contém browser reconhecido")
        
        # 6. Verifica estrutura básica (deve começar com Mozilla)
        if not ua.startswith('Mozilla/'):
            issues.append("Não segue formato padrão (Mozilla/X.X)")
        
        # 7. Verifica se não é malformado
        if '()' in ua or ua.count('(') != ua.count(')'):
            issues.append("Estrutura de parênteses malformada")
        
        # Se não há issues críticas, é válido
        critical_issues = [issue for issue in issues if any(word in issue.lower() 
                         for word in ['blacklist', 'vazio', 'inválidos', 'malformada'])]
        
        is_valid = len(critical_issues) == 0
        
        return is_valid, issues
    
    def validate_file(self, file_path: str) -> Dict:
        """
        Valida um arquivo completo de User-Agents
        
        Args:
            file_path: Caminho para arquivo de UAs
            
        Returns:
            Dicionário com estatísticas de validação
        """
        results = {
            'total_lines': 0,
            'valid_uas': 0,
            'invalid_uas': 0,
            'empty_lines': 0,
            'duplicates': 0,
            'valid_ua_list': [],
            'invalid_details': [],
            'duplicate_uas': [],
            'file_path': file_path
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            seen_uas = set()
            
            for line_num, line in enumerate(lines, 1):
                results['total_lines'] += 1
                
                # Remove quebras de linha
                ua = line.strip()
                
                # Linha vazia
                if not ua:
                    results['empty_lines'] += 1
                    continue
                
                # Verifica duplicata
                if ua in seen_uas:
                    results['duplicates'] += 1
                    results['duplicate_uas'].append({
                        'line': line_num,
                        'ua': ua[:50] + '...' if len(ua) > 50 else ua
                    })
                    continue
                
                seen_uas.add(ua)
                
                # Valida UA
                is_valid, issues = self.validate_user_agent(ua)
                
                if is_valid:
                    results['valid_uas'] += 1
                    results['valid_ua_list'].append(ua)
                else:
                    results['invalid_uas'] += 1
                    results['invalid_details'].append({
                        'line': line_num,
                        'ua': ua[:50] + '...' if len(ua) > 50 else ua,
                        'issues': issues
                    })
            
            logger.info(f"Validação completa: {results['valid_uas']}/{results['total_lines']} UAs válidos")
            
        except Exception as e:
            logger.error(f"Erro ao validar arquivo: {e}")
            results['error'] = str(e)
        
        return results
    
    def create_clean_file(self, original_file: str, clean_file: str) -> Dict:
        """
        Cria arquivo limpo apenas com UAs válidos
        
        Args:
            original_file: Arquivo original
            clean_file: Arquivo limpo de saída
            
        Returns:
            Estatísticas da limpeza
        """
        results = self.validate_file(original_file)
        
        if 'error' in results:
            return results
        
        # Escreve arquivo limpo
        try:
            with open(clean_file, 'w', encoding='utf-8') as f:
                for ua in results['valid_ua_list']:
                    f.write(ua + '\n')
            
            logger.info(f"Arquivo limpo criado: {clean_file}")
            logger.info(f"UAs válidos salvos: {len(results['valid_ua_list'])}")
            
            results['clean_file'] = clean_file
            results['clean_file_created'] = True
            
        except Exception as e:
            logger.error(f"Erro ao criar arquivo limpo: {e}")
            results['clean_file_error'] = str(e)
        
        return results
    
    def get_quality_score(self, ua: str) -> float:
        """
        Calcula score de qualidade do UA (0.0 a 1.0)
        
        Args:
            ua: User-Agent string
            
        Returns:
            Score de qualidade
        """
        score = 0.0
        
        # Pontuações por critérios
        if ua.startswith('Mozilla/'):
            score += 0.2
        
        if 'AppleWebKit' in ua:
            score += 0.2
        
        if any(browser in ua for browser in ['Chrome', 'Firefox', 'Safari']):
            score += 0.2
        
        if 'Windows NT' in ua or 'Mac OS X' in ua or 'Linux' in ua:
            score += 0.2
        
        if 50 <= len(ua) <= 200:  # Tamanho ideal
            score += 0.2
        
        return min(score, 1.0)


def main():
    """Script principal para validar arquivo de User-Agents"""
    
    # Configura logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    validator = UserAgentValidator()
    
    # Arquivos
    original_file = "user-agents.txt"
    clean_file = "user-agents-clean.txt"
    
    print("🔍 Validador de User-Agents")
    print("=" * 50)
    
    # Verifica se arquivo existe
    if not Path(original_file).exists():
        print(f"❌ Arquivo não encontrado: {original_file}")
        return
    
    print(f"📁 Validando arquivo: {original_file}")
    print("⏳ Processando...")
    
    # Valida arquivo
    results = validator.validate_file(original_file)
    
    if 'error' in results:
        print(f"❌ Erro: {results['error']}")
        return
    
    # Mostra estatísticas
    print(f"\n📊 Estatísticas de Validação:")
    print(f"   Total de linhas: {results['total_lines']:,}")
    print(f"   Linhas vazias: {results['empty_lines']:,}")
    print(f"   UAs duplicados: {results['duplicates']:,}")
    print(f"   UAs válidos: {results['valid_uas']:,}")
    print(f"   UAs inválidos: {results['invalid_uas']:,}")
    
    # Calcula percentuais
    total_content = results['total_lines'] - results['empty_lines']
    if total_content > 0:
        valid_percent = (results['valid_uas'] / total_content) * 100
        print(f"   Taxa de validade: {valid_percent:.1f}%")
    
    # Mostra alguns exemplos de UAs inválidos
    if results['invalid_details']:
        print(f"\n⚠️ Exemplos de UAs inválidos (primeiros 5):")
        for detail in results['invalid_details'][:5]:
            print(f"   Linha {detail['line']}: {detail['ua']}")
            print(f"     Problemas: {', '.join(detail['issues'])}")
    
    # Cria arquivo limpo
    print(f"\n🧹 Criando arquivo limpo...")
    clean_results = validator.create_clean_file(original_file, clean_file)
    
    if clean_results.get('clean_file_created'):
        print(f"✅ Arquivo limpo criado: {clean_file}")
        print(f"📈 UAs válidos salvos: {len(clean_results['valid_ua_list']):,}")
        
        # Calcula qualidade média
        if clean_results['valid_ua_list']:
            scores = [validator.get_quality_score(ua) for ua in clean_results['valid_ua_list'][:100]]
            avg_quality = sum(scores) / len(scores)
            print(f"🎯 Qualidade média: {avg_quality:.2f}/1.0")
    
    print(f"\n🎉 Validação concluída!")


if __name__ == "__main__":
    main()