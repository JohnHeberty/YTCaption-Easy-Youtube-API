#!/usr/bin/env python3
"""
Validação rápida da Sprint 1: Interface Base + Factory Pattern
Valida a implementação sem precisar de pytest
"""
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

def test_interface_exists():
    """Verifica se interface TTSEngine existe"""
    print("🔍 Testando: Interface TTSEngine existe...")
    try:
        from app.engines.base import TTSEngine
        print("  ✅ Interface TTSEngine importada com sucesso")
        return True
    except Exception as e:
        print(f"  ❌ Erro ao importar TTSEngine: {e}")
        return False


def test_interface_is_abstract():
    """Verifica se TTSEngine é abstrata"""
    print("🔍 Testando: TTSEngine é abstrata...")
    try:
        from app.engines.base import TTSEngine
        
        # Tentar instanciar diretamente (deve falhar)
        try:
            engine = TTSEngine()
            print(f"  ❌ TTSEngine não é abstrata (pôde ser instanciada)")
            return False
        except TypeError:
            print(f"  ✅ TTSEngine é abstrata (não pode ser instanciada)")
            return True
    except Exception as e:
        print(f"  ❌ Erro: {e}")
        return False


def test_interface_has_required_methods():
    """Verifica se interface tem métodos obrigatórios"""
    print("🔍 Testando: Interface tem métodos obrigatórios...")
    try:
        from app.engines.base import TTSEngine
        import inspect
        
        required_methods = [
            'generate_dubbing',
            'clone_voice',
            'get_supported_languages',
            'engine_name',
            'sample_rate'
        ]
        
        abstract_methods = [method for method in dir(TTSEngine) 
                          if not method.startswith('_')]
        
        all_found = True
        for method in required_methods:
            if method in abstract_methods or hasattr(TTSEngine, method):
                print(f"  ✅ Método '{method}' encontrado")
            else:
                print(f"  ❌ Método '{method}' NÃO encontrado")
                all_found = False
        
        return all_found
    except Exception as e:
        print(f"  ❌ Erro: {e}")
        return False


def test_factory_exists():
    """Verifica se factory existe"""
    print("🔍 Testando: Factory existe...")
    try:
        from app.engines.factory import create_engine, create_engine_with_fallback, clear_engine_cache
        print("  ✅ Funções de factory importadas com sucesso")
        return True
    except Exception as e:
        print(f"  ❌ Erro ao importar factory: {e}")
        return False


def test_factory_has_cache():
    """Verifica se factory tem cache"""
    print("🔍 Testando: Factory tem cache...")
    try:
        from app.engines.factory import _ENGINE_CACHE
        print(f"  ✅ Cache existe (_ENGINE_CACHE)")
        print(f"  ℹ️  Cache atual: {dict(_ENGINE_CACHE)}")
        return True
    except Exception as e:
        print(f"  ❌ Erro: {e}")
        return False


def test_package_exports():
    """Verifica se package exports corretos"""
    print("🔍 Testando: Package exports...")
    try:
        from app import engines
        
        exports = ['TTSEngine', 'create_engine', 'create_engine_with_fallback', 'clear_engine_cache']
        
        all_found = True
        for export in exports:
            if hasattr(engines, export):
                print(f"  ✅ Export '{export}' disponível")
            else:
                print(f"  ❌ Export '{export}' NÃO disponível")
                all_found = False
        
        return all_found
    except Exception as e:
        print(f"  ❌ Erro: {e}")
        return False


def main():
    """Executa todos os testes"""
    print("=" * 60)
    print("🧪 SPRINT 1 - VALIDAÇÃO DE INTERFACE + FACTORY")
    print("=" * 60)
    print()
    
    tests = [
        test_interface_exists,
        test_interface_is_abstract,
        test_interface_has_required_methods,
        test_factory_exists,
        test_factory_has_cache,
        test_package_exports,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  💥 Exceção não tratada: {e}")
            failed += 1
        print()
    
    print("=" * 60)
    print("📊 RESULTADO")
    print("=" * 60)
    print(f"✅ Testes aprovados: {passed}/{len(tests)}")
    print(f"❌ Testes falhados: {failed}/{len(tests)}")
    print()
    
    if failed == 0:
        print("🎉 SPRINT 1 - INTERFACE + FACTORY: GREEN PHASE COMPLETO!")
        return 0
    else:
        print("⚠️  Alguns testes falharam. Revisar implementação.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
