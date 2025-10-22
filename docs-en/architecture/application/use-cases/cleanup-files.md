# CleanupOldFilesUseCase

Use Case para limpeza de arquivos temporários antigos.

---

## Responsabilidade

Remover arquivos temporários que excedem uma idade máxima.

**Arquivo**: `src/application/use_cases/cleanup_files.py`

---

## Parâmetros

```python
def __init__(
    self,
    storage_service: IStorageService,
    max_age_hours: int = 24
):
```

- `storage_service` - Serviço de armazenamento
- `max_age_hours` - Idade máxima dos arquivos (padrão: 24h)

---

## Método Principal

### `execute() -> dict`

**Saída**: Dicionário com estatísticas de limpeza:
```python
{
    "success": True,
    "removed_count": 15,
    "storage_before_mb": 450.2,
    "storage_after_mb": 120.5,
    "freed_space_mb": 329.7
}
```

---

## Exemplo de Uso

```python
from src.application.use_cases import CleanupOldFilesUseCase

# Criar Use Case
cleanup = CleanupOldFilesUseCase(
    storage_service=storage,
    max_age_hours=12  # Remover arquivos > 12h
)

# Executar limpeza
result = await cleanup.execute()

print(f"Arquivos removidos: {result['removed_count']}")
print(f"Espaço liberado: {result['freed_space_mb']:.2f} MB")
```

---

## Uso em Produção

### Cron Job (Linux)
```bash
# /etc/cron.d/ytcaption-cleanup
# Executar limpeza a cada 6 horas
0 */6 * * * python -m scripts.cleanup_old_files
```

### Systemd Timer (Linux)
```ini
# /etc/systemd/system/ytcaption-cleanup.timer
[Unit]
Description=YTCaption cleanup timer

[Timer]
OnBootSec=10min
OnUnitActiveSec=6h

[Install]
WantedBy=timers.target
```

### Task Scheduler (Windows)
```powershell
$action = New-ScheduledTaskAction -Execute "python" -Argument "-m scripts.cleanup_old_files"
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 6)
Register-ScheduledTask -TaskName "YTCaption Cleanup" -Action $action -Trigger $trigger
```

---

[⬅️ Voltar](../README.md)

**Versão**: 3.0.0