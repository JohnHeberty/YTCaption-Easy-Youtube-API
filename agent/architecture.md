# Arquitetura do Monorepo

## Estrutura Geral

Monorepo multi-app. Não existe `package.json` raiz nem workspace manager.

Cada subprojeto tem seu próprio `package.json` e deve ser instalado, executado e buildado separadamente.

| Diretório | Descrição | Status |
|---|---|---|
| `PetCare/` | App cliente para tutor de pet — Vite + React + Tailwind | Ativo |
| `PetCarePro/` | App profissional para groomer/veterinário — Vite + React + Tailwind | Ativo |
| `expo/PetCareExpo/` | App mobile — Expo / React Native | Ativo |
| `services/PetCareAdmin/` | Painel admin — Vite + React + TS + Tailwind + Prisma + Express | Ativo |
| `PetCareChat/` | Serviço de chat | Stub |

### Regras Estruturais
- `PetCare/` e `PetCarePro/` têm estrutura parecida, dependências parecidas e `theme.ts`.
- Não estão linkados por workspace.
- Código compartilhado está duplicado.
- Mudanças em um app podem precisar ser espelhadas no outro.
- Não importar diretamente arquivos entre `PetCare/` e `PetCarePro/` sem decisão explícita.
- Não assumir backend existente.
- Não assumir orquestração global na raiz.

### Caminhos Importantes
- Host/local: `/root/PetCare`
- MCP Repomix Docker: `/workspace`
- Ao rodar comandos shell: usar caminhos do host.
- Ao usar Repomix MCP: `directory = /workspace`

## Navegação

### Apps Vite (`PetCare/` e `PetCarePro/`)
- `App.tsx` usa navegação manual baseada em state machine.
- `switch` em uma string `AppState`.
- Não usa React Router.
- Histórico salvo em array no React state.
- Histórico persistido em `localStorage`.
- Namespaces: `PetCare → petcare_*`, `PetCarePro → petcarepro_*`.
- Não substituir por React Router sem pedido explícito.

### PetCareAdmin
- Usa React Router v7 com layout aninhado (`AdminShell`).
- Rotas em `src/router/routes.config.ts`.
- Guards de role em `src/router/RouteGuard.tsx`.

### Expo (`PetCareExpo/`)
- Usa `@react-navigation/stack`.
- Entry point: `expo/PetCareExpo/src/navigation/AppNavigator.js`.

## Vite Base Paths

Não remover nem alterar sem pedido explícito:
- `PetCare`: `/petcare/`
- `PetCarePro`: `/petcarepro/`

Necessários para deploy em subpath e assets corretos em produção.

## Theme System

- Apps Vite têm `theme.ts` semelhantes.
- Brand primary: `#00B14F`.
- Tailwind usa CSS variables em `styles/stylesglobals.css`.
- PetCareAdmin: dark mode toggle no perfil, `localStorage` persistence, sync com `prefers-color-scheme`.
- Preservar o sistema de tema atual.

## Maps

- Apps Vite: `react-leaflet`, `leaflet`, OpenStreetMap tiles.
- `PetCareExpo`: Leaflet via `react-native-webview`; não usa `react-native-maps` diretamente.
- PetCareAdmin: Leaflet para visualizações de mapa.

## Dados e Estado

Dados são locais/mock (não assumir backend):
- `PetCare`: `localStorage`.
- `PetCareExpo`: `AsyncStorage`, `StorageService`.
- `PetCareAdmin`: Prisma + PostgreSQL + PostGIS (backend real), JWT HS256 com `jsonwebtoken`, bcrypt via `bcryptjs`.
- Tokens access (15m) + refresh (7d) em `localStorage` com chaves `petcareadmin_*`.

## Convenções Obrigatórias

Preservar sempre:
- `"use client"` no topo dos `App.tsx` dos apps Vite.
- Alias `@/` apontando para a raiz do subprojeto.
- `noUnusedLocals: false`.
- `noUnusedParameters: false`.
- Textos de UI em português do Brasil.
- Estrutura de componentes existente.
- Sistema de tema atual.
- Responsividade existente.
- Padrões de navegação existentes.
- Vite base paths.
- Nomes e namespaces de storage existentes.

Diretórios comuns: `pages/`, `ui/`, `shared/`, `dialogs/`, `figma/`, `components/`, `styles/`.

## PetCareAdmin — Arquitetura Específica

### Stack
- Vite + React + TypeScript + Tailwind + Prisma + PostgreSQL + PostGIS + Express 5.x.

### Backend
- Express 5.x como backend REST para rotas `/api/v1/*`.
- Rotas admin: `/api/v1/admin/*`.
- Rotas runtime: `/api/v1/app/*`.
- Middleware `authMiddleware` + `requireRoles(...roles)` como guards centrais.
- Singleton `PrismaClient` em `src/api/db.ts`.

### Roles
- `superadmin`, `operations`, `support`, `finance`, `moderation`.

### Database
- UUID PK, soft delete (`deletedAt`), `version` integer, valores em `*_cents`.
- PostGIS requer extensão `postgis` habilitada no PostgreSQL.

### UI Kit
- Componentes `forwardRef`, fully typed, barrel export em `ui/index.ts`.
- Toast DOM-based para chamadas imperativas fora de componentes.
- Validadores compostos com `compose(...)` e padrão `ValidatorFn<T>`.
