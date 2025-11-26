"""
Sprint 3.1: Teste do F5TTSModelLoader
Valida carregamento do modelo pt-BR
"""

from app.f5tts_loader import F5TTSModelLoader

print("="*70)
print("🧪 SPRINT 3.1: Teste do F5TTSModelLoader")
print("="*70)

# 1. Instanciar loader
print("\n1️⃣ Instanciando loader...")
loader = F5TTSModelLoader()

print(f"   ✅ Loader criado")
print(f"   📂 Modelo: {loader.model_path}")
print(f"   🔧 Device: {loader.device}")

# 2. Carregar modelo
print("\n2️⃣ Carregando modelo F5-TTS pt-BR...")
model = loader.load_model()

# 3. Validar informações
print("\n3️⃣ Informações do modelo:")
info = loader.get_model_info()
for key, value in info.items():
    if key == 'config':
        print(f"   {key}:")
        for k, v in value.items():
            print(f"      {k}: {v}")
    else:
        print(f"   {key}: {value}")

print("\n✅ SPRINT 3.1 CONCLUÍDO COM SUCESSO!")
print("="*70)
