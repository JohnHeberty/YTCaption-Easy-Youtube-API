# Phase 10: API Key Rate Limiting

**Status**: ⏳ PENDENTE  
**Prioridade**: 🟡 MEDIUM  
**Esforço Estimado**: 3 horas  
**Impacto**: Médio  
**ROI**: ⭐⭐⭐

---

## 📋 Objetivo

Implementar rate limiting baseado em API keys além do IP, permitindo controle granular por cliente/aplicação e integração com sistemas externos.

---

## 🎯 Motivação

**Limitações do rate limiting atual (IP-based)**:
- ❌ Usuários atrás de NAT compartilham limites
- ❌ Impossível diferenciar aplicações do mesmo usuário
- ❌ Difícil integrar com sistemas externos

**Benefícios de API Keys**:
- ✅ Rate limit independente por aplicação
- ✅ Revogação granular (desabilitar apenas 1 app)
- ✅ Auditoria: rastrear qual app fez cada request
- ✅ Limites customizados por tier

---

## 🏗️ Arquitetura

### API Key Structure
```
Format: ytcap_<env>_<random32chars>
Example: ytcap_prod_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
```

### Database Schema
```sql
CREATE TABLE api_keys (
    id UUID PRIMARY KEY,
    key_hash VARCHAR(64) NOT NULL UNIQUE,
    key_prefix VARCHAR(20) NOT NULL,  -- Primeiros 8 chars para display
    user_id UUID REFERENCES users(id),
    name VARCHAR(100),
    tier VARCHAR(50),
    rate_limit_per_minute INTEGER DEFAULT 5,
    rate_limit_per_day INTEGER DEFAULT 100,
    is_active BOOLEAN DEFAULT true,
    last_used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    
    INDEX idx_key_hash (key_hash),
    INDEX idx_user_id (user_id)
);
```

---

## 🛠️ Implementação

### 1. Generate API Key

```python
# src/infrastructure/security/api_key_handler.py
import secrets
import hashlib

class APIKeyHandler:
    @staticmethod
    def generate_key(env: str = "prod") -> tuple[str, str]:
        """
        Gera uma API key e retorna (key, hash).
        
        Returns:
            tuple: (plain_key, hashed_key)
        """
        random_part = secrets.token_urlsafe(24)  # 32 chars
        key = f"ytcap_{env}_{random_part}"
        
        # Hash para armazenar no banco
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        
        return key, key_hash
    
    @staticmethod
    def hash_key(key: str) -> str:
        """Hash uma API key."""
        return hashlib.sha256(key.encode()).hexdigest()
    
    @staticmethod
    def get_prefix(key: str) -> str:
        """Retorna prefixo para display (primeiros 8 chars)."""
        return key[:16]  # ytcap_prod_ab...
```

### 2. Endpoints de Gestão

```python
# src/presentation/api/routes/api_keys.py
@router.post("/api/v1/api-keys")
async def create_api_key(
    name: str,
    current_user: User = Depends(get_current_user)
):
    """Cria uma nova API key."""
    # Limitar a 5 keys ativas por usuário
    active_keys = await key_repo.count_active_by_user(current_user.id)
    if active_keys >= 5:
        raise HTTPException(400, "Maximum 5 active API keys allowed")
    
    # Gerar key
    plain_key, key_hash = APIKeyHandler.generate_key()
    prefix = APIKeyHandler.get_prefix(plain_key)
    
    # Salvar no banco
    api_key = await key_repo.create(APIKey(
        key_hash=key_hash,
        key_prefix=prefix,
        user_id=current_user.id,
        name=name,
        tier=current_user.tier,
        rate_limit_per_minute=get_rate_limit_for_tier(current_user.tier)
    ))
    
    return {
        "api_key": plain_key,  # ⚠️ Mostrar apenas 1 vez!
        "prefix": prefix,
        "name": name,
        "message": "Save this key securely. It won't be shown again."
    }

@router.get("/api/v1/api-keys")
async def list_api_keys(current_user: User = Depends(get_current_user)):
    """Lista API keys do usuário (sem revelar keys completas)."""
    keys = await key_repo.get_by_user(current_user.id)
    
    return {
        "api_keys": [
            {
                "id": k.id,
                "prefix": k.key_prefix,
                "name": k.name,
                "is_active": k.is_active,
                "last_used_at": k.last_used_at,
                "created_at": k.created_at
            }
            for k in keys
        ]
    }

@router.delete("/api/v1/api-keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    current_user: User = Depends(get_current_user)
):
    """Revoga uma API key."""
    await key_repo.revoke(key_id, current_user.id)
    return {"message": "API key revoked successfully"}
```

### 3. Authentication Dependency

```python
# src/presentation/api/dependencies.py
from fastapi import Header, HTTPException

async def get_api_key(
    x_api_key: Optional[str] = Header(None)
) -> APIKey:
    """
    Valida API key do header X-API-Key.
    """
    if not x_api_key:
        raise HTTPException(401, "X-API-Key header required")
    
    if not x_api_key.startswith("ytcap_"):
        raise HTTPException(401, "Invalid API key format")
    
    # Hash e buscar no banco
    key_hash = APIKeyHandler.hash_key(x_api_key)
    api_key = await key_repo.get_by_hash(key_hash)
    
    if not api_key or not api_key.is_active:
        raise HTTPException(401, "Invalid or inactive API key")
    
    # Verificar expiração
    if api_key.expires_at and api_key.expires_at < datetime.utcnow():
        raise HTTPException(401, "API key expired")
    
    # Atualizar last_used_at (async task para não bloquear)
    asyncio.create_task(key_repo.update_last_used(api_key.id))
    
    return api_key

async def get_current_user_from_key(
    api_key: APIKey = Depends(get_api_key)
) -> User:
    """Carrega usuário associado à API key."""
    return await user_repo.get_by_id(api_key.user_id)
```

### 4. Rate Limiting com API Key

```python
# src/presentation/api/middlewares/api_key_rate_limiter.py
from slowapi import Limiter

def get_api_key_identifier(request: Request) -> str:
    """
    Usa API key como identificador para rate limiting.
    Fallback para IP se não houver API key.
    """
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return f"api_key:{api_key[:16]}"  # Usar prefix
    return f"ip:{request.client.host}"

limiter = Limiter(key_func=get_api_key_identifier)

# Usar em rotas
@router.post("/api/v1/transcribe")
@limiter.limit("10/minute")  # Rate limit personalizado por API key
async def transcribe_video(
    request: Request,
    api_key: APIKey = Depends(get_api_key)
):
    # API key válida, aplicar rate limit dela
    if api_key.rate_limit_per_minute:
        # Verificar rate limit customizado
        ...
```

---

## 📊 Métricas

```python
api_key_usage_total = Counter('api_key_usage_total', ['key_prefix', 'endpoint'])
api_key_rate_limit_exceeded = Counter('api_key_rate_limit_exceeded_total', ['key_prefix'])
api_key_active_total = Gauge('api_key_active_total', ['tier'])
```

---

## 🔒 Segurança

### Best Practices
1. **Never log full keys**: Apenas prefixo em logs
2. **Hash storage**: Armazenar apenas hash SHA-256
3. **Rate limiting**: Prevenir brute-force de keys
4. **Rotation**: Encorajar rotação periódica
5. **Scope**: Considerar scopes (read, write, admin)

### Key Rotation
```python
@router.post("/api/v1/api-keys/{key_id}/rotate")
async def rotate_api_key(key_id: str, current_user: User):
    """Gera nova key e revoga a antiga."""
    old_key = await key_repo.get_by_id(key_id, current_user.id)
    
    # Criar nova key
    new_key, new_hash = APIKeyHandler.generate_key()
    new_api_key = await key_repo.create(APIKey(
        key_hash=new_hash,
        name=f"{old_key.name} (rotated)",
        user_id=current_user.id
    ))
    
    # Revogar antiga após 7 dias (grace period)
    await key_repo.schedule_revoke(old_key.id, days=7)
    
    return {
        "new_api_key": new_key,
        "message": "Old key will be revoked in 7 days"
    }
```

---

**Próxima Phase**: [Phase 11: Documentation v2.2](./11-documentation.md)
