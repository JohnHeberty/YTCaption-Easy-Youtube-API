# Phase 4: JWT Authentication

**Status**: ⏳ PENDENTE  
**Prioridade**: 🔴 HIGH  
**Esforço Estimado**: 4 horas  
**Impacto**: Alto  
**ROI**: ⭐⭐⭐⭐⭐

---

## 📋 Objetivo

Implementar sistema de autenticação robusto baseado em JWT (JSON Web Tokens) para proteger endpoints críticos e habilitar gestão de usuários.

---

## 🎯 Motivação

**Problemas atuais**:
- ❌ API completamente aberta - qualquer um pode fazer transcrições
- ❌ Impossível rastrear uso por usuário
- ❌ Rate limiting baseado apenas em IP (facilmente contornável)
- ❌ Sem controle de acesso granular
- ❌ Impossível implementar quotas por usuário

**Benefícios esperados**:
- ✅ Segurança: Endpoints protegidos com autenticação
- ✅ Rastreabilidade: Cada requisição vinculada a um usuário
- ✅ Quotas: Limites de uso personalizados por usuário/tier
- ✅ Multi-tenancy: Suporte a múltiplos clientes
- ✅ Auditoria: Logs completos de quem fez o quê
- ✅ Monetização: Base para planos free/pro/enterprise

---

## 🏗️ Arquitetura Proposta

### 1. Estrutura de Dados

```python
# src/domain/entities/user.py
class User:
    id: str
    email: str
    password_hash: str
    is_active: bool
    tier: UserTier  # FREE, PRO, ENTERPRISE
    created_at: datetime
    monthly_quota: int
    monthly_usage: int

class UserTier(Enum):
    FREE = "free"          # 100 transcrições/mês
    PRO = "pro"            # 1000 transcrições/mês
    ENTERPRISE = "enterprise"  # Ilimitado
```

### 2. Endpoints Novos

```python
POST   /api/v1/auth/register     # Criar conta
POST   /api/v1/auth/login        # Login (retorna JWT)
POST   /api/v1/auth/refresh      # Refresh token
GET    /api/v1/auth/me           # Info do usuário logado
PATCH  /api/v1/auth/me           # Atualizar perfil
DELETE /api/v1/auth/me           # Deletar conta
```

### 3. Proteção de Endpoints

```python
# Antes (sem autenticação)
@router.post("/api/v1/transcribe")
async def transcribe_video(request_dto: TranscribeRequestDTO):
    ...

# Depois (com autenticação)
@router.post("/api/v1/transcribe")
async def transcribe_video(
    request_dto: TranscribeRequestDTO,
    current_user: User = Depends(get_current_user)  # ✨ Novo
):
    # Verificar quota
    if current_user.monthly_usage >= current_user.monthly_quota:
        raise HTTPException(429, "Monthly quota exceeded")
    
    # Incrementar contador
    await user_service.increment_usage(current_user.id)
    
    ...
```

### 4. JWT Token Structure

```json
{
  "sub": "user_id_123",
  "email": "user@example.com",
  "tier": "pro",
  "exp": 1698789600,
  "iat": 1698786000,
  "jti": "unique_token_id"
}
```

---

## 🛠️ Implementação Técnica

### Dependências

```txt
# requirements.txt
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.18  # Para form data
```

### Módulos a Criar

#### 1. Security Module
```
src/infrastructure/security/
├── __init__.py
├── jwt_handler.py          # Criar/validar tokens
├── password_handler.py     # Hash/verificar senhas
└── dependencies.py         # get_current_user, get_admin_user
```

#### 2. User Repository
```
src/infrastructure/persistence/
├── __init__.py
├── user_repository.py      # CRUD de usuários
└── models.py               # SQLAlchemy models
```

#### 3. Auth Routes
```
src/presentation/api/routes/
└── auth.py                 # Endpoints de autenticação
```

---

## 📝 Checklist de Implementação

### Fase 1: Setup (1h)
- [ ] Adicionar dependências ao `requirements.txt`
- [ ] Criar módulo `src/infrastructure/security/`
- [ ] Implementar `JWTHandler` (create_token, decode_token)
- [ ] Implementar `PasswordHandler` (hash, verify)
- [ ] Configurar variáveis de ambiente:
  ```env
  JWT_SECRET_KEY=your-secret-key-here
  JWT_ALGORITHM=HS256
  JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
  JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
  ```

### Fase 2: User Management (1.5h)
- [ ] Criar entity `User` em `src/domain/entities/`
- [ ] Criar enum `UserTier` (FREE, PRO, ENTERPRISE)
- [ ] Implementar `IUserRepository` interface
- [ ] Implementar `UserRepository` com SQLAlchemy/PostgreSQL
- [ ] Criar DTOs: `RegisterDTO`, `LoginDTO`, `UserResponseDTO`
- [ ] Implementar use cases:
  - `RegisterUserUseCase`
  - `LoginUserUseCase`
  - `GetCurrentUserUseCase`
  - `UpdateUserUseCase`

### Fase 3: Authentication Routes (1h)
- [ ] Criar `auth.py` router
- [ ] Implementar endpoint `/auth/register`
- [ ] Implementar endpoint `/auth/login`
- [ ] Implementar endpoint `/auth/refresh`
- [ ] Implementar endpoint `/auth/me`
- [ ] Adicionar validações (email único, senha forte)
- [ ] Testes unitários para auth endpoints

### Fase 4: Proteger Endpoints (30min)
- [ ] Criar dependency `get_current_user`
- [ ] Adicionar autenticação em `/api/v1/transcribe`
- [ ] Adicionar autenticação em `/api/v1/video/info`
- [ ] Implementar verificação de quota
- [ ] Atualizar contador de uso após transcrição
- [ ] Atualizar documentação OpenAPI com security scheme

---

## 🔒 Segurança

### Boas Práticas Implementadas

1. **Senhas**:
   - Hash com bcrypt (cost factor 12)
   - Validação: mínimo 8 chars, maiúscula, minúscula, número

2. **Tokens**:
   - JWT assinado com HS256
   - Access token: 30min expiration
   - Refresh token: 7 dias expiration
   - Token único por login (jti claim)

3. **Rate Limiting**:
   - Login: 5 tentativas/minuto por IP
   - Register: 3 registros/hora por IP
   - Token refresh: 10/minuto por usuário

4. **HTTPS**:
   - Recomendado em produção
   - Secure cookies para refresh token

---

## 📊 Métricas a Adicionar

```python
# Novas métricas Prometheus
user_registrations_total = Counter('user_registrations_total')
user_logins_total = Counter('user_logins_total', ['status'])
user_quota_exceeded_total = Counter('user_quota_exceeded_total', ['tier'])
user_active_sessions = Gauge('user_active_sessions')
```

---

## 🧪 Testing Strategy

### Unit Tests
```python
# tests/unit/test_jwt_handler.py
def test_create_access_token():
    token = jwt_handler.create_access_token(user_id="123")
    payload = jwt_handler.decode_token(token)
    assert payload["sub"] == "123"

def test_expired_token_raises_error():
    expired_token = create_expired_token()
    with pytest.raises(TokenExpiredError):
        jwt_handler.decode_token(expired_token)
```

### Integration Tests
```python
# tests/integration/test_auth_endpoints.py
async def test_register_login_flow():
    # Register
    response = await client.post("/auth/register", json={
        "email": "test@example.com",
        "password": "SecurePass123"
    })
    assert response.status_code == 201
    
    # Login
    response = await client.post("/auth/login", data={
        "username": "test@example.com",
        "password": "SecurePass123"
    })
    assert response.status_code == 200
    token = response.json()["access_token"]
    
    # Acessar endpoint protegido
    response = await client.get("/auth/me", headers={
        "Authorization": f"Bearer {token}"
    })
    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"
```

---

## 🗄️ Database Schema

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    tier VARCHAR(50) DEFAULT 'free',
    is_active BOOLEAN DEFAULT true,
    monthly_quota INTEGER DEFAULT 100,
    monthly_usage INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP,
    
    CONSTRAINT check_tier CHECK (tier IN ('free', 'pro', 'enterprise'))
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_tier ON users(tier);

-- Reset mensal de usage
CREATE OR REPLACE FUNCTION reset_monthly_usage()
RETURNS void AS $$
BEGIN
    UPDATE users SET monthly_usage = 0;
END;
$$ LANGUAGE plpgsql;
```

---

## 🚀 Rollout Plan

### Fase 1: Soft Launch (1 semana)
- Autenticação OPCIONAL
- Endpoints funcionam com e sem token
- Monitorar adoção

### Fase 2: Hard Launch (2 semanas depois)
- Autenticação OBRIGATÓRIA
- Migração de usuários existentes (gerar credenciais)
- Notificar via email

### Fase 3: Monetização (1 mês depois)
- Implementar planos pagos
- Integrar com Stripe/PayPal
- Dashboard de billing

---

## 📚 Referências

- [JWT Best Practices](https://datatracker.ietf.org/doc/html/rfc8725)
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [python-jose Documentation](https://python-jose.readthedocs.io/)

---

**Próxima Phase**: [Phase 5: Batch Processing API](./05-batch-processing.md)
