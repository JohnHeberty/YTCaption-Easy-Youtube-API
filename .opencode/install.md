# Instalação e Manutenção — OpenCode Plugins & MCP

## Plugins

Instalar todos os plugins declarados no `opencode.json`:

```powershell
opencode plugin @tarquinen/opencode-dcp@latest
opencode plugin opencode-pty@latest
opencode plugin opencode-websearch-cited@1.2.0
```

### Fallback manual (se `opencode plugin` falhar)

O opencode também lê plugins do `package.json` do diretório onde ele é iniciado
(raiz do projeto ou `~/.config/opencode/`). Para instalar manualmente:

```powershell
# Por projeto (raiz do repositório)
cd .opencode
npm install @tarquinen/opencode-dcp@latest
npm install opencode-pty@latest
npm install opencode-websearch-cited@1.2.0

# Por usuário (global — afeta todos projetos)
cd ~/.config/opencode
npm install @tarquinen/opencode-dcp@latest
npm install opencode-pty@latest
npm install opencode-websearch-cited@1.2.0
```

### Problema conhecido: cache corrompido

O opencode mantém um cache próprio em `~/.cache/opencode/packages/`.
Se um plugin falhar com `Cannot find module '...'`, o cache pode estar corrompido
(extração parcial, `package.json` faltando, etc.).

**Solução:** reinstalar a dependência faltante dentro do cache do plugin.

Exemplo com `@tarquinen/opencode-dcp` (precisa de `@anthropic-ai/tokenizer`):

```powershell
# 1. Remover o pacote corrompido
Remove-Item -Recurse -Force "$env:USERPROFILE\.cache\opencode\packages\@tarquinen\opencode-dcp@latest\node_modules\@anthropic-ai"

# 2. Reinstalar a dependência no diretório do cache
cd "$env:USERPROFILE\.cache\opencode\packages\@tarquinen\opencode-dcp@latest"
npm install @anthropic-ai/tokenizer@0.0.4

# 3. Verificar
node -e "require('@anthropic-ai/tokenizer')"
# Deve retornar sem erro, exportando countTokens e getTokenizer
```

## MCP Servers

Configurados no `opencode.json` na seção `"mcp"`.

### repomix

Container Docker que empacota o repositório para contexto da IA.

```powershell
docker pull ghcr.io/yamadashy/repomix:latest
```

> **Atenção:** o comando no `opencode.json` monta `/root/PetCare:/workspace`
> (caminho Linux). No Windows, ajuste o bind mount para o caminho real:
> ```json
> "command": ["docker", "run", "-i", "--rm", "-v",
>   "C:/caminho/para/discomex:/workspace",
>   "ghcr.io/yamadashy/repomix", "--mcp"]
> ```

### serena

Container Docker com o servidor MCP da Serena (análise de código).

```powershell
docker pull ghcr.io/oraios/serena:1.2.0
```

> **Atenção:** mesmo problema de bind mount com caminho Linux.
> Ajuste o volume para o caminho Windows real se for usar.

### context7

MCP remoto (não precisa de instalação). Atualmente desabilitado
(`"enabled": false`).

## Verificação

Após instalar/consertar plugins, reinicie o opencode e confira:

```powershell
# Listar plugins carregados (dentro do opencode)
opencode plugin list

# Verificar se o servidor MCP responde
opencode mcp list
```

Se o erro persistir, limpe o cache inteiro e reinstale:

```powershell
Remove-Item -Recurse -Force "$env:USERPROFILE\.cache\opencode\packages"
# Depois reinstale os plugins (comandos da seção "Plugins" acima)
```
