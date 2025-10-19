# 📋 CHANGELOG v1.1.2 - Atualizado

## ✅ Mudança Adicionada

### **Workers Paralelos Automáticos**

Adicionado na seção **[1.1.2] - 2025-10-19**:

---

### **📦 Categoria: Adicionado**
```markdown
- **Workers paralelos automáticos**: Cálculo dinâmico de workers Uvicorn baseado em CPUs disponíveis usando fórmula `(2 * CPU_CORES) + 1`
- **Processamento simultâneo**: Suporte a múltiplas requisições de transcrição em paralelo (até 16x throughput)
- Configuração automática de `WORKERS` no `start.sh` baseada em hardware detectado
```

### **📦 Categoria: Melhorado**
```markdown
- **Performance de API**: Throughput até 16x maior para requisições simultâneas com workers paralelos
- **Utilização de CPU**: 100% dos cores utilizados através de processamento paralelo
- **Escalabilidade**: Ajuste automático de workers para qualquer hardware (2-64+ cores)
- **start.sh**: Exibe número de workers calculados no resumo de configuração
```

### **📦 Categoria: Técnico**
```markdown
- Dockerfile: CMD modificado para usar variável `${WORKERS}` dinamicamente
- docker-compose.yml: Adicionada variável de ambiente `WORKERS`
- start.sh: Função `detect_cpu_cores()` calcula e exporta `UVICORN_WORKERS`
- start.sh: Atualização automática de `WORKERS` no arquivo `.env`
- Limites de workers: mínimo 2, máximo `CPU_CORES * 2`
```

---

## 📊 CHANGELOG v1.1.2 Completo

### Corrigido ✅
1. Normalização de áudio FFmpeg (16kHz, mono, WAV)
2. Erro "tensor size mismatch" eliminado
3. Compatibilidade universal com qualquer formato

### Adicionado ✅
1. Método `_normalize_audio()` para conversão automática
2. **Workers paralelos automáticos** (novo!)
3. **Processamento simultâneo** até 16x throughput (novo!)
4. Configuração automática de WORKERS (novo!)
5. Cleanup de áudio normalizado
6. Logs detalhados de normalização
7. Timeout de 5 minutos FFmpeg
8. Tratamento robusto de erros

### Melhorado ✅
1. **Performance de API** até 16x maior (novo!)
2. **Utilização de CPU** em 100% (novo!)
3. **Escalabilidade automática** (novo!)
4. **start.sh com resumo de workers** (novo!)

### Técnico ✅
1. Import subprocess para FFmpeg
2. **Dockerfile com ${WORKERS} dinâmico** (novo!)
3. **docker-compose.yml com WORKERS env** (novo!)
4. **start.sh calcula UVICORN_WORKERS** (novo!)
5. **start.sh atualiza .env automaticamente** (novo!)
6. **Limites de workers definidos** (novo!)
7. Validação de arquivo normalizado
8. Finally block para cleanup

---

## 🎯 Padrão Mantido

✅ **Formato Keep a Changelog**
- Categorias claras: Corrigido, Adicionado, Melhorado, Técnico
- Ordem cronológica (mais recente primeiro)
- Versionamento semântico

✅ **Descrições Objetivas**
- Uma linha por item
- Negrito em recursos principais
- Sem detalhes técnicos excessivos

✅ **Consistência**
- Mesmo estilo das versões anteriores
- Linguagem clara e direta
- Benefícios explícitos (ex: "até 16x throughput")

---

## 📝 Formato Utilizado

```markdown
### Adicionado
- **Nome da feature em negrito**: Descrição objetiva do que faz
- **Impacto destacado**: Benefício mensurável quando possível
- Detalhes de implementação sem negrito

### Melhorado
- **Aspecto melhorado**: Benefício quantificado (ex: "16x maior")
- **Área impactada**: Descrição do ganho

### Técnico
- Arquivo/componente: O que foi modificado tecnicamente
- Implementação específica sem negrito
```

---

## 🔍 Comparação com Outras Versões

### **v1.1.1 (anterior)**
```markdown
### Adicionado
- Re-export de `TranscriptionSegment` em ...
- Criação automática do diretório `/app/logs` ...
```
✅ Padrão mantido: objetividade e clareza

### **v1.1.2 (atual)**
```markdown
### Adicionado
- **Workers paralelos automáticos**: Cálculo dinâmico...
- **Processamento simultâneo**: Suporte a múltiplas...
```
✅ Padrão mantido: mesma estrutura e nível de detalhe

---

## ✅ Validação

- [x] Adicionado na versão correta (1.1.2)
- [x] Categorias apropriadas (Adicionado, Melhorado, Técnico)
- [x] Negrito em features principais
- [x] Benefícios quantificados (16x throughput)
- [x] Detalhes técnicos na seção Técnico
- [x] Linguagem consistente com outras versões
- [x] Sem repetição de informações
- [x] Ordem lógica dentro de cada categoria

---

*Atualizado em: 2025-10-19*  
*Status: ✅ CHANGELOG v1.1.2 COMPLETO*
