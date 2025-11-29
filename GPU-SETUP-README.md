# 🚀 Setup Automático de GPU para Containers LXC Proxmox

Este guia explica como usar o script `gpu-fix.sh` para configurar automaticamente o NVIDIA Container Toolkit em containers LXC do Proxmox.

## 📋 Pré-requisitos

### No Host Proxmox (obrigatório)

1. **GPU NVIDIA configurada** no host Proxmox
2. **Driver NVIDIA instalado** no host
3. **GPU Passthrough configurado** para o container LXC

#### Configuração no Host Proxmox

No arquivo `/etc/pve/lxc/<CONTAINER_ID>.conf`, adicione:

```bash
# Habilita features necessárias
features: nesting=1

# GPU Passthrough - Dispositivos
lxc.cgroup2.devices.allow: c 195:* rwm
lxc.cgroup2.devices.allow: c 510:* rwm

# Monta dispositivos GPU
lxc.mount.entry: /dev/nvidia0 dev/nvidia0 none bind,optional,create=file 0 0
lxc.mount.entry: /dev/nvidiactl dev/nvidiactl none bind,optional,create=file 0 0
lxc.mount.entry: /dev/nvidia-uvm dev/nvidia-uvm none bind,optional,create=file 0 0
lxc.mount.entry: /dev/nvidia-uvm-tools dev/nvidia-uvm-tools none bind,optional,create=file 0 0

# Monta nvidia-smi e bibliotecas essenciais
lxc.mount.entry: /usr/bin/nvidia-smi usr/bin/nvidia-smi none bind,optional,create=file 0 0
lxc.mount.entry: /usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1 usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1 none bind,optional,create=file 0 0

# ⭐ IMPORTANTE: Para PyTorch funcionar, adicione também:
lxc.mount.entry: /usr/lib/x86_64-linux-gnu/libcuda.so usr/lib/x86_64-linux-gnu/libcuda.so none bind,optional,create=file 0 0
lxc.mount.entry: /usr/lib/x86_64-linux-gnu/libcuda.so.1 usr/lib/x86_64-linux-gnu/libcuda.so.1 none bind,optional,create=file 0 0
lxc.mount.entry: /usr/lib/x86_64-linux-gnu/libcuda.so.550.163.01 usr/lib/x86_64-linux-gnu/libcuda.so.550.163.01 none bind,optional,create=file 0 0
```

**Nota**: Substitua `<CONTAINER_ID>` pelo ID do seu container e ajuste a versão do driver (550.163.01) conforme necessário.

Após editar, reinicie o container:
```bash
pct stop <CONTAINER_ID>
pct start <CONTAINER_ID>
```

### No Container LXC

- **Debian 11+** ou **Ubuntu 20.04+**
- **Docker instalado** (opcional, mas recomendado)
- **Acesso root** no container

## 🎯 Uso do Script

### 1. Copiar o script para o container

```bash
# Opção 1: Via wget/curl (se tiver o script em um servidor web)
wget https://seu-servidor.com/gpu-fix.sh
chmod +x gpu-fix.sh

# Opção 2: Via scp do host
scp gpu-fix.sh root@<IP_DO_CONTAINER>:/root/

# Opção 3: Copiar e colar o conteúdo
nano gpu-fix.sh
# Cole o conteúdo e salve (Ctrl+X, Y, Enter)
chmod +x gpu-fix.sh
```

### 2. Executar o script

```bash
sudo bash gpu-fix.sh
```

O script irá:
1. ✅ Verificar permissões root
2. ✅ Detectar a distribuição Linux
3. ✅ Verificar disponibilidade da GPU
4. ✅ Remover instalações antigas conflitantes
5. ✅ Configurar repositório NVIDIA
6. ✅ Instalar NVIDIA Container Toolkit
7. ✅ Configurar Docker runtime
8. ✅ Aplicar configurações específicas para LXC
9. ✅ Configurar libcuda.so (se disponível)
10. ✅ Testar a instalação
11. ✅ Gerar relatório

### 3. Verificar instalação

```bash
# Teste 1: nvidia-smi
nvidia-smi

# Teste 2: Docker info
docker info | grep -i runtime

# Teste 3: Container de teste
docker run --rm --runtime=nvidia --gpus all \
  nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

## 📊 Output Esperado

```
==========================================
NVIDIA Container Toolkit Installer
Para Proxmox LXC com GPU Passthrough
==========================================

[✓] Executando como root
[INFO] Distribuição detectada: debian 12
[✓] Dispositivos NVIDIA encontrados
[✓] Limpeza concluída
[✓] Repositório configurado
[✓] NVIDIA Container Toolkit instalado
[✓] Docker runtime configurado
[✓] Configuração LXC aplicada (no-cgroups=true, mode=legacy)
[✓] Docker reiniciado
==========================================
[INFO] Testando configuração...
==========================================
[✓] Runtime nvidia detectado
[✓] nvidia-container-cli funcionando
[✓] Container teste executou nvidia-smi com sucesso!
==========================================
[INFO] INSTALAÇÃO CONCLUÍDA
==========================================
```

## 🔧 Troubleshooting

### Problema: PyTorch não detecta GPU

**Sintoma:**
```python
import torch
print(torch.cuda.is_available())  # False
```

**Solução:**

Certifique-se de que os bind mounts do `libcuda.so` estão configurados no host Proxmox (veja seção "Pré-requisitos" acima).

Dentro do container, verifique:
```bash
ls -la /usr/lib/x86_64-linux-gnu/libcuda*
```

Se não aparecer, adicione os bind mounts no arquivo `/etc/pve/lxc/<CONTAINER_ID>.conf` do host Proxmox.

### Problema: "Error 803: driver/cuda combination"

**Causa:** Incompatibilidade de versão entre driver e CUDA toolkit.

**Solução:**

Verifique as versões:
```bash
# Versão do driver
cat /proc/driver/nvidia/version

# Versão CUDA no container Docker
docker exec <container> nvcc --version
```

Se incompatíveis, use uma imagem Docker com CUDA compatível ou atualize o driver.

### Problema: "could not select device driver nvidia"

**Causa:** Runtime nvidia não configurado.

**Solução:**

Execute o script novamente ou configure manualmente:
```bash
nvidia-ctk runtime configure --runtime=docker
systemctl restart docker
```

### Problema: Dispositivos /dev/nvidia* não existem

**Causa:** GPU passthrough não configurado no Proxmox.

**Solução:**

Verifique a configuração LXC no host Proxmox (veja "Pré-requisitos").

## 📁 Logs

O script gera um log completo em:
```
/var/log/nvidia-container-toolkit-install.log
```

Para ver o log:
```bash
cat /var/log/nvidia-container-toolkit-install.log
```

## 🐳 Uso com Docker Compose

Adicione ao seu `docker-compose.yml`:

```yaml
services:
  seu-servico:
    image: sua-imagem
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - NVIDIA_DRIVER_CAPABILITIES=compute,utility
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
```

## ✨ Features do Script

- ✅ **Detecção automática** da distribuição
- ✅ **Cleanup inteligente** de instalações antigas
- ✅ **Workarounds para LXC** (no-cgroups, legacy mode)
- ✅ **Testes automáticos** após instalação
- ✅ **Logging completo** de todas operações
- ✅ **Output colorido** para fácil leitura
- ✅ **Idempotente** - pode ser executado múltiplas vezes
- ✅ **Error handling** robusto

## 🔄 Atualização

Para atualizar o NVIDIA Container Toolkit:

```bash
# Execute o script novamente
sudo bash gpu-fix.sh
```

O script automaticamente remove versões antigas e instala a mais recente.

## 📚 Referências

- [NVIDIA Container Toolkit Documentation](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/)
- [Proxmox GPU Passthrough Wiki](https://pve.proxmox.com/wiki/PCI(e)_Passthrough)
- [Docker GPU Support](https://docs.docker.com/config/containers/resource_constraints/#gpu)

## 🆘 Suporte

Em caso de problemas, consulte:
1. Logs: `/var/log/nvidia-container-toolkit-install.log`
2. Documentação: `GPU-TROUBLESHOOTING.md`
3. Teste manual: Execute os comandos da seção "Verificar instalação"

---

**Desenvolvido para YTCaption Audio-Voice Service**  
Script testado em: Debian 12, Ubuntu 22.04 (Proxmox LXC)  
Última atualização: 2025-11-29
