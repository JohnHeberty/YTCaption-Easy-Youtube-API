#!/bin/bash
# Script para verificar se o código no servidor Proxmox está atualizado

echo "🔍 Verificando código no servidor Proxmox..."
echo ""

echo "1️⃣ Verificando commits no servidor:"
git log --oneline -3
echo ""

echo "2️⃣ Verificando se método acall() existe no circuit_breaker.py:"
grep -n "async def acall" src/infrastructure/utils/circuit_breaker.py
echo ""

echo "3️⃣ Verificando se downloader.py usa acall():"
grep -n "acall" src/infrastructure/youtube/downloader.py
echo ""

echo "4️⃣ Verificando se há algum .call( que deveria ser .acall(:"
grep -n "_circuit_breaker.call(" src/infrastructure/youtube/downloader.py
echo ""

echo "5️⃣ Hash do arquivo circuit_breaker.py:"
md5sum src/infrastructure/utils/circuit_breaker.py
echo ""

echo "6️⃣ Hash do arquivo downloader.py:"
md5sum src/infrastructure/youtube/downloader.py
echo ""

echo "✅ Verificação completa!"
