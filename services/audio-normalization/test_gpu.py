#!/usr/bin/env python3
"""
Script para testar suporte CUDA/GPU no container de audio-normalization
"""
import sys

print("=" * 60)
print("🔍 TESTE DE SUPORTE GPU/CUDA - Audio Normalization")
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

# Teste 2: OpenUnmix
print("\n2️⃣ Verificando OpenUnmix...")
try:
    import openunmix
    print(f"   ✅ OpenUnmix instalado")
    
except ImportError as e:
    print(f"   ⚠️ OpenUnmix não instalado: {e}")
    print(f"   └─ Isolamento vocal não estará disponível")

# Teste 3: Bibliotecas de áudio
print("\n3️⃣ Verificando bibliotecas de processamento de áudio...")
try:
    import librosa
    import noisereduce as nr
    import soundfile as sf
    from pydub import AudioSegment
    print(f"   ✅ librosa: {librosa.__version__}")
    print(f"   ✅ noisereduce instalado")
    print(f"   ✅ soundfile instalado")
    print(f"   ✅ pydub instalado")
except ImportError as e:
    print(f"   ❌ Erro ao importar bibliotecas de áudio: {e}")
    sys.exit(1)

# Teste 4: Variáveis de Ambiente
print("\n4️⃣ Verificando Variáveis de Ambiente...")
import os
env_vars = [
    'CUDA_VISIBLE_DEVICES',
    'NVIDIA_VISIBLE_DEVICES',
    'NVIDIA_DRIVER_CAPABILITIES',
    'FORCE_CUDA'
]

for var in env_vars:
    value = os.getenv(var, 'Not Set')
    print(f"   └─ {var}: {value}")

# Teste 5: Carregar modelo OpenUnmix (se disponível)
print("\n5️⃣ Testando carregamento de modelo OpenUnmix...")
try:
    import openunmix
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"   └─ Carregando modelo 'vocals' no {device}...")
    
    model = openunmix.umx.load_pretrained(
        target='vocals',
        device=device,
        pretrained=True
    )
    model.eval()
    
    print(f"   ✅ Modelo OpenUnmix carregado com sucesso no {device.upper()}!")
    
    if device == 'cuda':
        print(f"   └─ Memória GPU após carregar: {torch.cuda.memory_allocated(0) / 1024**2:.2f} MB")
    
except Exception as e:
    print(f"   ⚠️ Não foi possível carregar OpenUnmix: {e}")
    print(f"   └─ Isolamento vocal pode não funcionar")

print("\n" + "=" * 60)
print("✅ TESTES CONCLUÍDOS!")
print("=" * 60)
