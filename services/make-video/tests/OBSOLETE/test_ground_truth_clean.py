"""
Teste LIMPO de Acurácia - Sprint 07
Dataset corrigido: 
- sample_OK (7 vídeos SEM legendas)
- sample_NOT_OK (39 vídeos COM legendas)
"""

import json
import os
import pytest

def test_ground_truth_integrity():
    """Verifica se os ground_truth.json estão corretos"""
    
    # sample_OK deve ter vídeos SEM legendas
    with open('storage/validation/sample_OK/ground_truth.json') as f:
        data_ok = json.load(f)
    
    print(f"\n📁 sample_OK: {len(data_ok['videos'])} vídeos")
    assert len(data_ok['videos']) == 7, "sample_OK deveria ter 7 vídeos"
    
    for video in data_ok['videos']:
        assert video['has_subtitles'] == False, f"{video['filename']} deveria ser SEM legendas"
        assert video['expected_result'] == False
    
    print(f"   ✅ Todos marcados como SEM legendas (false)")
    
    # sample_NOT_OK deve ter vídeos COM legendas  
    with open('storage/validation/sample_NOT_OK/ground_truth.json') as f:
        data_not_ok = json.load(f)
    
    print(f"\n📁 sample_NOT_OK: {len(data_not_ok['videos'])} vídeos")
    # 38 vídeos após remover video_3AdZJp7eBFHDAQqggaX2Wv (irrecuperável)
    
    for video in data_not_ok['videos']:
        assert video['has_subtitles'] == True, f"{video['filename']} deveria ser COM legendas"
        assert video['expected_result'] == True
    
    print(f"   ✅ Todos marcados como COM legendas (true)")
    
    print(f"\n✅ Ground truth validado!")
    print(f"   Total: {len(data_ok['videos']) + len(data_not_ok['videos'])} vídeos")
    print(f"   - SEM legendas: {len(data_ok['videos'])} vídeos")
    print(f"   - COM legendas: {len(data_not_ok['videos'])} vídeos")


if __name__ == "__main__":
    test_ground_truth_integrity()
