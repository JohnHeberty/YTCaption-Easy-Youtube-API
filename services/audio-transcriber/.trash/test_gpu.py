#!/usr/bin/env python3
"""
Script para testar suporte CUDA/GPU no container
"""
import sys

print("=" * 60)
print("🔍 TESTE DE SUPORTE GPU/CUDA")
print("=" * 60)

# Teste 1: PyTorch
print("\n1️⃣ Verificando PyTorch...")
try:
    import torch
    print(f"   ✅ PyTorch instalado: {torch.__version__}")
    print(f"   └─ CUDA Built Version: {torch.version.cuda}")
    
    cuda_available = torch.cuda.is_available()
    print(f"   └─ CUDA Disponível: {cuda_available}")
    
    if cuda_available:
        print(f"   └─ GPU Count: {torch.cuda.device_count()}")
        for i in range(torch.cuda.device_count()):
            print(f"   └─ GPU {i}: {torch.cuda.get_device_name(i)}")
            print(f"      └─ Compute Capability: {torch.cuda.get_device_capability(i)}")
        
        # Teste de tensor
        print("\n   🔥 Testando operação na GPU...")
        x = torch.randn(1000, 1000).to('cuda')
        y = x @ x.T
        print(f"   ✅ Operação na GPU bem-sucedida!")
        print(f"   └─ Memória Alocada: {torch.cuda.memory_allocated(0) / 1024**2:.2f} MB")
        print(f"   └─ Memória Total: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
    else:
        print("   ⚠️ CUDA não disponível")
        
except ImportError as e:
    print(f"   ❌ PyTorch não instalado: {e}")
    sys.exit(1)

# Teste 2: Whisper
print("\n2️⃣ Verificando Whisper...")
try:
    import whisper
    print(f"   ✅ Whisper instalado")
    
    # Lista modelos disponíveis
    print(f"   └─ Modelos disponíveis: {whisper.available_models()}")
    
except ImportError as e:
    print(f"   ❌ Whisper não instalado: {e}")
    sys.exit(1)

# Teste 3: Variáveis de Ambiente
print("\n3️⃣ Verificando Variáveis de Ambiente...")
import os
env_vars = [
    'CUDA_VISIBLE_DEVICES',
    'NVIDIA_VISIBLE_DEVICES',
    'NVIDIA_DRIVER_CAPABILITIES',
    'FORCE_CUDA',
    'WHISPER_DEVICE'
]

for var in env_vars:
    value = os.getenv(var, 'Not Set')
    print(f"   └─ {var}: {value}")

# Teste 4: Carregar modelo pequeno
print("\n4️⃣ Testando carregamento de modelo...")
try:
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"   └─ Carregando modelo 'tiny' no {device}...")
    model = whisper.load_model('tiny', device=device)
    print(f"   ✅ Modelo carregado com sucesso no {device.upper()}!")
    
    # Informações do modelo
    print(f"   └─ Device do modelo: {next(model.parameters()).device}")
    
    if device == 'cuda':
        print(f"   └─ Memória GPU após carregar: {torch.cuda.memory_allocated(0) / 1024**2:.2f} MB")
    
except Exception as e:
    print(f"   ❌ Erro ao carregar modelo: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ TODOS OS TESTES PASSARAM!")
print("=" * 60)
