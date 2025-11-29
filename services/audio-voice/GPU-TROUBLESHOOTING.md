# Configuração GPU para Audio-Voice Service em Proxmox LXC

## Problema Identificado

O serviço `audio-voice` está rodando mas a GPU não está sendo detectada pelo PyTorch devido a incompatibilidade de versão entre:
- **Driver NVIDIA no host Proxmox**: 550.163.01  
- **Biblioteca CUDA compat na imagem Docker**: 550.54.15

```
Error 803: system has unsupported display driver / cuda driver combination
```

## Status Atual

✅ NVIDIA Container Toolkit instalado e configurado  
✅ Runtime nvidia funcionando (dispositivos montados)  
✅ nvidia-smi funciona dentro do container  
✅ Serviço rodando em modo CPU (funcional mas lento)  
❌ PyTorch CUDA não detecta GPU

## Solução: Configurar Bind Mounts no Proxmox LXC

### 1. No Host Proxmox (como root)

Localize o arquivo de configuração do container LXC (onde `134` é o ID do container):

```bash
nano /etc/pve/lxc/134.conf
```

### 2. Adicionar Bind Mounts das Bibliotecas NVIDIA

Adicione estas linhas ao arquivo de configuração:

```
# GPU NVIDIA - Bibliotecas do Driver
lxc.mount.entry = /usr/lib/x86_64-linux-gnu/libcuda.so /var/lib/lxc/134/rootfs/usr/lib/x86_64-linux-gnu/libcuda.so none bind,optional,create=file 0 0
lxc.mount.entry = /usr/lib/x86_64-linux-gnu/libcuda.so.1 /var/lib/lxc/134/rootfs/usr/lib/x86_64-linux-gnu/libcuda.so.1 none bind,optional,create=file 0 0
lxc.mount.entry = /usr/lib/x86_64-linux-gnu/libcuda.so.550.163.01 /var/lib/lxc/134/rootfs/usr/lib/x86_64-linux-gnu/libcuda.so.550.163.01 none bind,optional,create=file 0 0
```

**Nota**: Ajuste o caminho `/var/lib/lxc/134/rootfs` se o container estiver em outro local.

### 3. Reiniciar o Container LXC

```bash
pct stop 134
pct start 134
```

### 4. Verificar Montagens (dentro do LXC)

```bash
mount | grep nvidia
ls -la /usr/lib/x86_64-linux-gnu/libcuda*
```

### 5. Testar GPU no Container Docker

```bash
cd /home/YTCaption-Easy-Youtube-API/services/audio-voice
docker compose restart
docker exec audio-voice-api python -c "import torch; print('CUDA:', torch.cuda.is_available(), '| GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A')"
```

## Alternativa: Atualizar Imagem Base Docker

Se não tiver acesso ao host Proxmox, pode-se usar uma imagem Docker mais antiga com driver compatível:

```dockerfile
# Usar CUDA 11.8 que é compatível com driver 550.x
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04
```

E ajustar a instalação do PyTorch:

```bash
pip install torch==2.4.0 torchaudio==2.4.0 --index-url https://download.pytorch.org/whl/cu118
```

## Verificação Final

Após aplicar a solução, execute:

```bash
# Teste 1: nvidia-smi no container
docker exec audio-voice-api nvidia-smi

# Teste 2: PyTorch CUDA
docker exec audio-voice-api python -c "import torch; assert torch.cuda.is_available(), 'CUDA not available'; print(f'✓ GPU: {torch.cuda.get_device_name(0)}')"

# Teste 3: Logs do serviço
docker logs audio-voice-api 2>&1 | grep -i cuda
```

Se tudo estiver OK, você verá:
```
✓ GPU: NVIDIA GeForce RTX 3090
```

## Configuração Atual do Docker

O `docker-compose.yml` já está configurado corretamente com:
- `runtime: nvidia`
- `NVIDIA_VISIBLE_DEVICES=all`
- `NVIDIA_DRIVER_CAPABILITIES=compute,utility`
- Bind mount de `libnvidia-ml.so.1`
- Deploy resources com GPU

## Troubleshooting

### Se ainda não funcionar:

1. **Verificar versão do driver no container:**
   ```bash
   docker exec audio-voice-api cat /proc/driver/nvidia/version
   ```

2. **Verificar bibliotecas carregadas:**
   ```bash
   docker exec audio-voice-api ldconfig -p | grep -i cuda
   ```

3. **Forçar LD_LIBRARY_PATH (temporário):**
   ```bash
   docker exec audio-voice-api bash -c "export LD_LIBRARY_PATH='/usr/lib/x86_64-linux-gnu:\$LD_LIBRARY_PATH' && python -c 'import torch; print(torch.cuda.is_available())'"
   ```

## Contato

Para suporte adicional, verifique:
- [NVIDIA Container Toolkit Docs](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/)
- [Proxmox GPU Passthrough](https://pve.proxmox.com/wiki/PCI(e)_Passthrough)
