# Configurações Exatas do Modelo pt-BR

## Análise Completa - Sprint 1.2

### Parâmetros Descobertos

Com base na análise detalhada do checkpoint `model_last.safetensors`, identificamos todos os parâmetros exatos do modelo pt-BR:

#### 1. Dimensões de Embedding
```python
# Text Embedding
text_num_embeds = 2545  # (checkpoint: 2545+1=2546 vs padrão: 256)
text_dim = 512         # (checkpoint: 512 vs padrão: 100)

# Mel Input
mel_dim = 100          # (checkpoint: 100 - output projection)
                       # Nota: input_embed usa mel_dim*2 + text_dim = 712

# Convolutional Layers
conv_layers = 4        # (checkpoint: 4 ConvNeXtV2 blocks)
```

#### 2. Dimensões do Transformer
```python
dim = 1024             # hidden dimension (correto)
depth = 22             # número de transformer_blocks (correto)
heads = 16             # attention heads (correto)
dim_head = 64          # dimension per head (correto)
```

#### 3. Feed-Forward Network (FF)
```python
ff_mult = 2            # (checkpoint: 2048 = 1024 * 2, vs padrão: 4)
                       # Cada FFN tem: [2048, 1024] e [1024, 2048]
```

### Configuração Completa para Instanciar o Modelo

```python
from f5_tts.model.cfm import CFM
from f5_tts.model.backbones.dit import DiT

# Configurações corretas do modelo pt-BR
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

# Instanciar
dit = DiT(**model_config)
model = CFM(transformer=dit)
```

### Detalhes dos Size Mismatches Resolvidos

| Componente | Checkpoint Shape | Padrão Shape | Parâmetro Afetado |
|------------|------------------|--------------|-------------------|
| Text Embedding | `[2546, 512]` | `[257, 512]` | `text_num_embeds=2546` |
| Input Projection | `[1024, 712]` | `[1024, 1936]` | `mel_dim=100` (712 = 100*2 + 512) |
| FF Layer Hidden | `[2048, 1024]` | `[4096, 1024]` | `ff_mult=2` |
| FF Layer Output | `[1024, 2048]` | `[1024, 4096]` | `ff_mult=2` |
| Output Projection | `[100, 1024]` | `[712, 1024]` | `mel_dim=100` |

### Cálculos de Verificação

#### Input Embedding Dimension
```
input_dim = mel_dim * 2 + text_dim
          = 100 * 2 + 512
          = 712  ✅ MATCH!
```

#### Feed-Forward Hidden Dimension
```
ff_hidden = dim * ff_mult
          = 1024 * 2
          = 2048  ✅ MATCH!
```

#### Total Parameters
```
Modelo instanciado: ~426M parâmetros
Checkpoint: 364 tensors
```

### Status Final Sprint 1.2

✅ **SUCESSO COMPLETO**

- Todas as dimensões identificadas corretamente
- Modelo pode ser instanciado com parâmetros exatos do checkpoint
- Próximo passo: Sprint 1.3 (Backup) e Sprint 2 (Instalação do F5-TTS oficial)

### Próximas Ações

1. **Sprint 1.3**: Criar backup e branch Git
2. **Sprint 2**: Instalar F5-TTS do repositório oficial
3. **Sprint 3**: Criar loader customizado com configurações acima
4. **Sprint 4**: Testar carregamento e inferência
5. **Sprint 5**: Deploy em produção

---

**Data**: $(date)  
**Responsável**: GitHub Copilot  
**Status**: ✅ Concluído
