# CleanupOldFilesUseCase

Use Case for cleaning old temporary files.

---

## Responsibility

Remove temporary files that exceed a maximum age.

**File**: `src/application/use_cases/cleanup_files.py`

---

## Parameters

```python
def __init__(
    self,
    storage_service: IStorageService,
    max_age_hours: int = 24
):
```

- `storage_service` - Storage service
- `max_age_hours` - Maximum file age (default: 24h)

---

## Main Method

### `execute() -> dict`

**Output**: Dictionary with cleanup statistics:
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

## Usage Example

```python
from src.application.use_cases import CleanupOldFilesUseCase

# Create Use Case
cleanup = CleanupOldFilesUseCase(
    storage_service=storage,
    max_age_hours=12  # Remove files > 12h
)

# Execute cleanup
result = await cleanup.execute()

print(f"Files removed: {result['removed_count']}")
print(f"Space freed: {result['freed_space_mb']:.2f} MB")
```

---

## Production Usage

### Cron Job (Linux)
```bash
# /etc/cron.d/ytcaption-cleanup
# Run cleanup every 6 hours
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

[⬅️ Back](../README.md)

**Version**: 3.0.0