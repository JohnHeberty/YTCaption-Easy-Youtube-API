# Validação

## Regra Principal

Toda alteração deve ser validada quando possível.

Preferência de validação:
```
1. Teste específico do fluxo alterado
2. Type-check
3. Lint
4. Build
5. Verificação manual descrita
```

## Apps Vite (`PetCare`, `PetCarePro`)

```bash
npm run lint
npx tsc --noEmit
npm run build
```

Rodar no subprojeto correto.

## PetCareAdmin

```bash
npm run lint
npx tsc --noEmit
npm run build
npx prisma validate
npx prisma generate
```

## Expo (`PetCareExpo`)

```bash
npx expo start --web
```

Se houver lint configurado:
```bash
npm run lint
```

Não inventar script `test` se não existir.

## Se Não Puder Validar

Responder claramente:
```
Validação:
- Não executada.

Motivo:
- ...

Como validar manualmente:
- ...

Risco restante:
- ...
```

Nunca dizer "testado" sem teste real.

## Templates de Resposta Final

### Com arquivos alterados
```
Arquivos alterados:
- ...

O que mudou:
- ...

Como validei:
- ...

Observações/riscos:
- ...
```

### Sem arquivos alterados
```
Arquivos alterados:
- Nenhum.

O que foi feito:
- ...

Como validar:
- ...

Observações/riscos:
- ...
```

### Validação não executada
```
Validação:
- Não executada.

Motivo:
- ...

Como validar manualmente:
- ...

Risco restante:
- ...
```
