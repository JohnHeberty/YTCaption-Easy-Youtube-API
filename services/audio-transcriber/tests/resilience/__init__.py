"""
Testes de Resiliência - Audio Transcriber Service

Esta suite valida cenários de falha e recuperação em produção.

Testes incluem:
- Circuit breaker behavior
- Timeout handling
- Corrupted file handling  
- Retry logic
- Memory management
- Resource cleanup

⚠️  IMPORTANTE: Estes testes NÃO usam mocks - validam comportamento real!
"""
