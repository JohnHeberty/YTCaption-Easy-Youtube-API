# Comandos por Subprojeto

Todos os comandos devem rodar dentro do subprojeto correto. Nunca assumir comando na raiz do monorepo.

## PetCare

```bash
cd /root/PetCare/PetCare
npm install
npm run dev
npm run build
npm run lint
npx tsc --noEmit
```

## PetCarePro

```bash
cd /root/PetCare/PetCarePro
npm install
npm run dev
npm run build
npm run lint
npx tsc --noEmit
```

## PetCareExpo

```bash
cd /root/PetCare/expo/PetCareExpo
npm install
npx expo start
npx expo start --android
npx expo start --ios
npx expo start --web
```

Observações:
- Possui Jest em devDeps, mas não possui script `test`.
- Possui ESLint e Prettier configurados.
- Não criar scripts novos sem necessidade.

## PetCareAdmin

```bash
cd /root/PetCare/services/PetCareAdmin
npm install
npm run dev
npm run build
npm run lint
npx tsc --noEmit

# Server
npm run server
npm run server:start

# Database
npm run db:migrate
npm run db:seed
npx prisma generate
npx prisma validate
```

## Comandos Permitidos

```bash
npm run lint
npm run build
npx tsc --noEmit
npx expo start --web
```

## Comandos Proibidos Sem Confirmação

```
deploy
git reset
git clean
rm -rf amplo
migrações destrutivas
instalação global
alteração de infraestrutura
remoção em massa
```

## Política de Execução

Antes de rodar comandos:
1. Confirmar subprojeto correto.
2. Evitar rodar na raiz.
3. Verificar se o comando é necessário.
4. Evitar comandos longos sem motivo.
5. Evitar alterações colaterais.
6. Não instalar dependências globalmente.
7. Não executar comandos destrutivos.

Se comando falhar:
1. Ler o erro relevante, não o log inteiro.
2. Identificar causa provável.
3. Corrigir se estiver no escopo.
4. Reexecutar somente se fizer sentido.
5. Informar falha se não puder corrigir.
6. Registrar aprendizado durável em memória, se aplicável.
