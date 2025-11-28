# 📚 Índice Completo - Otimização de Disco

Bem-vindo à documentação completa da otimização de disco do serviço **audio-voice**.

---

## 🚀 INÍCIO RÁPIDO (5 minutos)

Se você quer aplicar as otimizações **AGORA**, siga estes passos:

```bash
# 1. Entre no diretório
cd services/audio-voice

# 2. Execute o script automático (com preview)
chmod +x apply-all-optimizations.sh
./apply-all-optimizations.sh --dry-run

# 3. Se OK, aplique de verdade
./apply-all-optimizations.sh

# 4. Siga os próximos passos mostrados no terminal
```

**Pronto!** As otimizações estão aplicadas. Agora leia [APPLY_OPTIMIZATION.md](./APPLY_OPTIMIZATION.md) para o build.

---

## 📖 DOCUMENTAÇÃO COMPLETA

### 🔴 NÍVEL 1: EXECUTIVO (Para Gerentes/Tech Leads)

| Documento | Descrição | Tempo de Leitura |
|-----------|-----------|------------------|
| **[INCIDENT_REPORT.md](./INCIDENT_REPORT.md)** | 📊 Relatório executivo do incidente com análise de impacto, root cause e ROI | 10 min |
| **[README_OPTIMIZATION.md](./README_OPTIMIZATION.md)** | 📋 Visão geral de toda a otimização, quick start e checklist | 5 min |

### 🟡 NÍVEL 2: IMPLEMENTAÇÃO (Para Desenvolvedores)

| Documento | Descrição | Tempo de Leitura |
|-----------|-----------|------------------|
| **[APPLY_OPTIMIZATION.md](./APPLY_OPTIMIZATION.md)** | 🚀 **GUIA PASSO A PASSO** completo para aplicar otimizações | 20 min |
| **[DISK_OPTIMIZATION_REPORT.md](./DISK_OPTIMIZATION_REPORT.md)** | 🔍 Análise técnica detalhada do problema e solução | 15 min |

### 🟢 NÍVEL 3: INFRAESTRUTURA (Para DevOps/SRE)

| Documento | Descrição | Tempo de Leitura |
|-----------|-----------|------------------|
| **[INFRASTRUCTURE_SETUP.md](./INFRASTRUCTURE_SETUP.md)** | 🔧 Configuração completa de infraestrutura (LVM, monitoramento, backups) | 30 min |

---

## 📁 ARQUIVOS CRIADOS

### Dockerfiles e Configurações

| Arquivo | Tipo | Descrição |
|---------|------|-----------|
| **Dockerfile.optimized** | Dockerfile | ✅ Novo Dockerfile com multi-stage build (-40% disco) |
| **.dockerignore.optimized** | Config | ✅ Exclusões completas de contexto de build (-80% lixo) |
| **daemon.json.example** | Config | ✅ Configuração otimizada do Docker daemon |

### Scripts Automáticos

| Script | Função | Uso |
|--------|--------|-----|
| **apply-all-optimizations.sh** | 🤖 Aplica TODAS as otimizações automaticamente | `./apply-all-optimizations.sh` |
| **scripts/validate-optimization.sh** | ✅ Valida otimizações (pre/post build) | `./scripts/validate-optimization.sh pre` |
| **scripts/check-disk.sh** | 📊 Monitora espaço em disco automaticamente | `./scripts/check-disk.sh 80` |
| **scripts/download_models.py** | 🤖 Baixa modelos TTS no runtime (não no build) | `python scripts/download_models.py` |

### Documentação Técnica

| Documento | Conteúdo |
|-----------|----------|
| **README_OPTIMIZATION.md** | Índice geral, quick start, lições aprendidas |
| **DISK_OPTIMIZATION_REPORT.md** | Análise técnica, comparativos, recomendações |
| **APPLY_OPTIMIZATION.md** | Tutorial passo a passo de aplicação |
| **INFRASTRUCTURE_SETUP.md** | Configuração de LVM, monitoramento, backups |
| **INCIDENT_REPORT.md** | Relatório executivo do incidente |
| **INDEX.md** | Este documento (índice visual) |

---

## 🎯 FLUXO DE TRABALHO RECOMENDADO

### Para Desenvolvedores

```
1. Ler README_OPTIMIZATION.md (visão geral)
   ↓
2. Executar apply-all-optimizations.sh
   ↓
3. Seguir APPLY_OPTIMIZATION.md (build e deploy)
   ↓
4. Validar com validate-optimization.sh
```

### Para DevOps/SRE

```
1. Ler INCIDENT_REPORT.md (contexto)
   ↓
2. Implementar INFRASTRUCTURE_SETUP.md (LVM, monitoramento)
   ↓
3. Configurar daemon.json e crons
   ↓
4. Validar com check-disk.sh
```

### Para Tech Leads/Gerentes

```
1. Ler INCIDENT_REPORT.md (executive summary)
   ↓
2. Revisar comparativos (ANTES vs DEPOIS)
   ↓
3. Aprovar plano de ação
   ↓
4. Acompanhar implementação
```

---

## 🔍 NAVEGAÇÃO POR TÓPICO

### 🐛 Entender o Problema

- **O que aconteceu?** → [INCIDENT_REPORT.md - Seção "O Que Aconteceu"](./INCIDENT_REPORT.md#-executive-summary)
- **Por que lotou o disco?** → [DISK_OPTIMIZATION_REPORT.md - Seção "Como Lotou o Disco"](./DISK_OPTIMIZATION_REPORT.md#-como-esse-dockerfile-lotou-seu-disco)
- **Análise técnica** → [INCIDENT_REPORT.md - Seção "Análise Técnica"](./INCIDENT_REPORT.md#-análise-técnica-detalhada)

### ✅ Aplicar Soluções

- **Quick start (automático)** → [INDEX.md - Início Rápido](#-início-rápido-5-minutos)
- **Passo a passo manual** → [APPLY_OPTIMIZATION.md](./APPLY_OPTIMIZATION.md)
- **Validação** → `scripts/validate-optimization.sh`

### 🔧 Configurar Infraestrutura

- **Particionar disco** → [INFRASTRUCTURE_SETUP.md - Seção 2](./INFRASTRUCTURE_SETUP.md#-2-particionamento-lvm)
- **Monitoramento** → [INFRASTRUCTURE_SETUP.md - Seção 3](./INFRASTRUCTURE_SETUP.md#-3-monitoramento-automático)
- **Limpeza automática** → [INFRASTRUCTURE_SETUP.md - Seção 4](./INFRASTRUCTURE_SETUP.md#-4-limpeza-automática)

### 📊 Comparativos e Resultados

- **Antes vs Depois** → [INCIDENT_REPORT.md - Seção "Resultados"](./INCIDENT_REPORT.md#-resultados)
- **Economia estimada** → [INCIDENT_REPORT.md - Seção "Economia"](./INCIDENT_REPORT.md#-economia-estimada)

### 🛡️ Prevenção

- **Checklist pré-build** → [APPLY_OPTIMIZATION.md - Seção 5.2](./APPLY_OPTIMIZATION.md#52-checklist-pré-build)
- **Monitoramento contínuo** → [INFRASTRUCTURE_SETUP.md - Seção 3](./INFRASTRUCTURE_SETUP.md#-3-monitoramento-automático)
- **Plano de recuperação** → [INFRASTRUCTURE_SETUP.md - Seção 7](./INFRASTRUCTURE_SETUP.md#-7-plano-de-recuperação-de-desastre)

---

## 🎓 RECURSOS ADICIONAIS

### Scripts Utilitários

```bash
# Validar ANTES do build
./scripts/validate-optimization.sh pre

# Validar DEPOIS do build
./scripts/validate-optimization.sh post

# Monitorar disco manualmente
./scripts/check-disk.sh 80

# Baixar modelos (primeira vez)
python scripts/download_models.py

# Aplicar tudo automaticamente
./apply-all-optimizations.sh
```

### Comandos Úteis

```bash
# Verificar espaço
df -h

# Limpar Docker
docker system prune -af --volumes

# Ver tamanho de imagens
docker images audio-voice

# Histórico de camadas
docker history audio-voice:3.0.0

# Tamanho do contexto de build
tar --exclude-from=.dockerignore -czf - . | wc -c
```

---

## 🆘 TROUBLESHOOTING RÁPIDO

| Problema | Solução |
|----------|---------|
| **Build lotando disco** | [APPLY_OPTIMIZATION.md - Troubleshooting](./APPLY_OPTIMIZATION.md#troubleshooting) |
| **Container não inicia** | `docker-compose logs` |
| **Modelos não baixam** | `docker-compose exec audio-voice python scripts/download_models.py` |
| **Filesystem corrompido** | [INFRASTRUCTURE_SETUP.md - Recovery](./INFRASTRUCTURE_SETUP.md#-7-plano-de-recuperação-de-desastre) |
| **Crons não funcionam** | `crontab -l` para verificar |

---

## 📊 MÉTRICAS DE SUCESSO

Após aplicar as otimizações, você deve observar:

- ✅ **Uso de disco durante build:** -40% (de ~25 GB para ~15 GB)
- ✅ **Tamanho da imagem final:** -35% (de ~18 GB para ~12 GB)
- ✅ **Tempo de build:** -20-30% mais rápido
- ✅ **Número de camadas:** -33% (de ~15 para ~10)
- ✅ **Contexto de build:** -80% (de ~2 MB para ~0.4 MB)

**Validação:** Use `./scripts/validate-optimization.sh post` para verificar.

---

## 📞 SUPORTE E CONTATO

### Dúvidas ou Problemas?

1. **Consulte a documentação** neste índice
2. **Execute** `./scripts/check-disk.sh` para diagnóstico
3. **Verifique logs** com `docker-compose logs`
4. **Abra issue** no repositório com output dos comandos

### Contribuições

Encontrou um bug na documentação? Tem sugestões de melhoria?

- Abra uma **Pull Request**
- Adicione sua melhoria à documentação
- Compartilhe com a equipe!

---

## 📅 CHANGELOG

### v3.0.0 (2025-11-28) - Otimização de Disco

#### ✅ Adicionado
- Multi-stage Dockerfile
- .dockerignore completo
- Scripts de monitoramento e validação
- Documentação completa (10 arquivos)
- Script de aplicação automática

#### 🔧 Modificado
- Download de modelos movido para runtime
- Consolidação de camadas Docker
- Limpeza agressiva de caches

#### 🗑️ Removido
- Build-essentials da imagem final
- Download de modelos durante build
- Arquivos desnecessários do contexto

### v2.0.0 (anterior)
- ❌ Dockerfile sem otimizações
- ❌ Lotava disco durante build
- ❌ Sem documentação de prevenção

---

## 🎯 PRÓXIMOS PASSOS

### Imediatos (Esta Sprint)
- [ ] Aplicar otimizações em staging
- [ ] Validar build otimizado
- [ ] Deploy em produção
- [ ] Monitorar por 24-48h

### Curto Prazo (Próximas 2 Semanas)
- [ ] Implementar LVM particionado
- [ ] Configurar alertas automáticos
- [ ] Treinar equipe nas mudanças
- [ ] Documentar runbooks

### Médio Prazo (Próximo Mês)
- [ ] Revisar outros Dockerfiles do projeto
- [ ] Implementar CI/CD com validação de tamanho
- [ ] Estabelecer SLOs para uso de disco
- [ ] Post-mortem completo do incidente

---

## 📚 LEITURA RECOMENDADA POR PERFIL

### 👨‍💼 Gerente/Tech Lead
1. [INCIDENT_REPORT.md](./INCIDENT_REPORT.md) (10 min)
2. [README_OPTIMIZATION.md](./README_OPTIMIZATION.md) (5 min)

**Total:** 15 minutos

### 👨‍💻 Desenvolvedor
1. [README_OPTIMIZATION.md](./README_OPTIMIZATION.md) (5 min)
2. [APPLY_OPTIMIZATION.md](./APPLY_OPTIMIZATION.md) (20 min)
3. Executar `apply-all-optimizations.sh`

**Total:** 30 minutos + execução

### 🔧 DevOps/SRE
1. [INCIDENT_REPORT.md](./INCIDENT_REPORT.md) (10 min)
2. [INFRASTRUCTURE_SETUP.md](./INFRASTRUCTURE_SETUP.md) (30 min)
3. [APPLY_OPTIMIZATION.md](./APPLY_OPTIMIZATION.md) (20 min)

**Total:** 60 minutos

---

## ✅ CHECKLIST FINAL

Use esta checklist para garantir que tudo foi implementado:

### Arquivos
- [ ] Dockerfile otimizado aplicado
- [ ] .dockerignore otimizado aplicado
- [ ] Scripts instalados em /usr/local/bin
- [ ] daemon.json configurado

### Infraestrutura
- [ ] /var/lib/docker em partição separada (recomendado)
- [ ] Monitoramento de disco ativo
- [ ] Limpeza automática configurada
- [ ] Alertas funcionando

### Processos
- [ ] Checklist pré-build documentado
- [ ] Runbooks atualizados
- [ ] Equipe treinada
- [ ] Post-mortem realizado

---

**Última atualização:** 28 de Novembro de 2025  
**Versão da Documentação:** 1.0  
**Mantido por:** Equipe Audio Voice Service

---

💡 **Dica:** Salve este arquivo nos favoritos do seu navegador para acesso rápido à documentação!
