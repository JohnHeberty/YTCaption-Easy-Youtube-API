"""
Teste FINAL de compatibilidade do modelo pt-BR com F5-TTS
Sprint 1.2 - Configurações EXATAS identificadas
"""

import sys
sys.path.insert(0, '/tmp/F5-TTS/src')

import torch
from safetensors import safe_open

# Importar CFM e DiT do repositório oficial
from f5_tts.model.cfm import CFM
from f5_tts.model.backbones.dit import DiT

print("=" * 80)
print("TESTE FINAL - Modelo pt-BR com Configurações Exatas")
print("=" * 80)

# Configurações EXATAS do modelo pt-BR (identificadas por análise)
model_config = {
    'dim': 1024,
    'depth': 22,
    'heads': 16,
    'dim_head': 64,
    'ff_mult': 2,              # *** CRITICAL: 2 ao invés de 4 padrão ***
    'mel_dim': 100,            # *** CRITICAL: 100 ao invés de 712 ***
    'text_num_embeds': 2545,   # *** CRITICAL: 2545 (TextEmbedding adds +1) ***
    'text_dim': 512,           # *** CRITICAL: 512 ao invés de 100 ***
    'conv_layers': 4,          # *** CRITICAL: 4 ConvNeXtV2 blocks ***
}

print(f"\n1. Configurações EXATAS do modelo pt-BR:")
for key, value in model_config.items():
    print(f"   {key:20s} = {value}")

# Cálculos de verificação
input_dim = model_config['mel_dim'] * 2 + model_config['text_dim']
ff_hidden = model_config['dim'] * model_config['ff_mult']
print(f"\n   Cálculos de verificação:")
print(f"   input_dim = mel_dim*2 + text_dim = {model_config['mel_dim']}*2 + {model_config['text_dim']} = {input_dim}")
print(f"   ff_hidden = dim * ff_mult = {model_config['dim']} * {model_config['ff_mult']} = {ff_hidden}")

try:
    print("\n2. Instanciando modelo DiT com configurações exatas...")
    dit_model = DiT(**model_config)
    print("   ✅ DiT instanciado com sucesso!")
    
    print("\n3. Instanciando CFM wrapper...")
    model = CFM(transformer=dit_model)
    print("   ✅ CFM wrapper instanciado com sucesso!")
    
    # Verificar estrutura
    total_params = sum(p.numel() for p in model.parameters())
    print(f"\n4. Estrutura do modelo:")
    print(f"   Total de parâmetros: {total_params:,}")
    print(f"   Transformer blocks: {len(model.transformer.transformer_blocks)}")
    print(f"   Input projection shape: {model.transformer.input_embed.proj.weight.shape}")
    print(f"   Text embedding shape: {model.transformer.text_embed.text_embed.weight.shape}")
    print(f"   FF hidden dim (block 0): {model.transformer.transformer_blocks[0].ff.ff[0][0].weight.shape}")
    print(f"   Output projection shape: {model.transformer.proj_out.weight.shape}")
    
    # Carregar checkpoint pt-BR
    model_path = "/app/models/f5tts/pt-br/model_last.safetensors"
    
    print(f"\n5. Carregando checkpoint pt-BR...")
    print(f"   Arquivo: {model_path}")
    
    with safe_open(model_path, framework="pt", device="cpu") as f:
        state_dict = {key: f.get_tensor(key) for key in f.keys()}
    
    print(f"   ✅ Checkpoint carregado: {len(state_dict)} tensors")
    
    # Tentar carregar pesos no modelo
    print(f"\n6. Carregando pesos no modelo...")
    result = model.load_state_dict(state_dict, strict=False)
    
    print(f"   Missing keys: {len(result.missing_keys)}")
    if result.missing_keys:
        print(f"   ⚠️  Primeiras missing: {result.missing_keys[:5]}")
    
    print(f"   Unexpected keys: {len(result.unexpected_keys)}")
    if result.unexpected_keys:
        print(f"   ⚠️  Primeiras unexpected: {result.unexpected_keys[:5]}")
    
    if len(result.missing_keys) == 0 and len(result.unexpected_keys) == 0:
        print("\n   " + "🎉" * 40)
        print("   🎉 SUCESSO TOTAL! 🎉")
        print("   " + "🎉" * 40)
        print("   ✅ Modelo pt-BR é 100% compatível com F5-TTS do repositório!")
        print("   ✅ Todas as dimensões customizadas carregadas corretamente!")
        print("   ✅ Zero missing keys, zero unexpected keys!")
        print("   " + "🎉" * 40)
    else:
        print("\n   ⚠️  Compatibilidade parcial - ajustes necessários")
    
    print("\n" + "=" * 80)
    print("CONCLUSÃO FINAL Sprint 1.2:")
    print("=" * 80)
    if len(result.missing_keys) == 0 and len(result.unexpected_keys) == 0:
        print("✅ F5-TTS do repositório oficial é 100% compatível!")
        print("✅ Configurações identificadas: ff_mult=2, mel_dim=100, text_num_embeds=2546, text_dim=512")
        print("✅ Modelo pt-BR pode ser usado diretamente")
        print("\n📋 Próximos Passos:")
        print("   1. Sprint 1.3: Criar backup e branch Git")
        print("   2. Sprint 2: Instalar F5-TTS do repositório oficial")
        print("   3. Sprint 3: Criar loader com configurações identificadas")
        print("   4. Sprint 4: Testar inferência com GTX 1050 Ti")
        print("   5. Sprint 5: Deploy em produção")
    else:
        print("⚠️  Ainda há incompatibilidades - investigar further")
    print("=" * 80)

except Exception as e:
    print(f"\n❌ ERRO: {e}")
    import traceback
    traceback.print_exc()
    print("\n" + "=" * 80)
    print("Necessário investigar incompatibilidades")
    print("=" * 80)
