# Bug #002: Celery Multiprocessing Permission Error on Windows

## Status
✅ **RESOLVED**

## Date
2026-01-03

## Severity
🟡 **MEDIUM** - Blocks async task execution on Windows development environment

## Description
When running Celery worker on Windows, the worker fails with permission errors related to multiprocessing pool workers:
```
PermissionError: [WinError 5] Access is denied
PermissionError: [WinError 13] Access is denied
OSError: [WinError 6] The handle is invalid
```

The worker receives tasks but cannot execute them due to multiprocessing pool failures.

## Error Details
```
[2026-01-03 01:34:20,470: ERROR/SpawnPoolWorker-3] Pool process <billiard.pool.Worker object at 0x...> error: PermissionError(13, 'Access is denied', None, 5, None)
Traceback (most recent call last):
  File "...\billiard\pool.py", line 473, in receive
    ready, req = _receive(1.0)
  File "...\billiard\pool.py", line 445, in _recv
    return True, loads(get_payload())
  File "...\billiard\queues.py", line 394, in get_payload
    with self._rlock:
  File "...\billiard\synchronize.py", line 118, in __exit__
    return self._semlock.__exit__(*args)
OSError: [WinError 6] The handle is invalid

During handling of the above exception, another exception occurred:
...
PermissionError: [WinError 5] Access is denied
```

## Root Cause
Celery's default multiprocessing pool (`prefork` or `processes`) uses Unix-style process forking which is not fully supported on Windows. Windows uses `spawn` instead of `fork` for creating child processes, which causes issues with:

1. **Shared memory synchronization** - Windows handles shared memory differently than Unix
2. **Process handles** - Windows process handles behave differently, leading to permission errors
3. **Semaphore locks** - The `billiard` library (Celery's multiprocessing backend) has compatibility issues with Windows semaphores

This is a known limitation of Celery on Windows when using the default multiprocessing pool.

## Environment
- **OS**: Windows 10/11
- **Python Version**: 3.11
- **Celery Version**: 5.6.1+
- **Platform**: Windows (win32)
- **Celery Pool**: Default (prefork/processes - not compatible with Windows)

## Steps to Reproduce
1. Start Celery worker on Windows:
   ```bash
   poetry run celery -A config worker -l info
   ```
2. Trigger an async task (e.g., portfolio import)
3. Worker receives the task but fails when trying to execute it
4. Multiple `PermissionError` and `OSError` exceptions appear in worker logs
5. Task remains in queue but never completes

## Solution

### Quick Fix
Use the `solo` pool for Windows, which uses a single-threaded execution model compatible with Windows:

```bash
poetry run celery -A config worker -l info --pool=solo
```

### For Development with Auto-reload
```bash
poetry run celery -A config worker -l info --pool=solo --reload
```

### Why Solo Pool Works
The `solo` pool:
- Runs tasks in the same process (no forking/spawning)
- Avoids Windows multiprocessing issues
- Suitable for development and small workloads
- Compatible with Windows, macOS, and Linux

### Alternative: Configure in Settings (Optional)
You can configure the pool in Django settings for automatic Windows detection:

```python
# config/settings/base.py
import sys

# Use solo pool on Windows
if sys.platform == "win32":
    CELERY_WORKER_POOL = "solo"
```

However, this is optional - using the command-line flag is sufficient.

## Prevention

1. **Documentation**: Add Windows-specific Celery setup instructions to README
2. **Development Setup**: Include `--pool=solo` in development scripts/documentation
3. **CI/CD**: Use appropriate pool for each platform (solo for Windows, prefork for Linux)
4. **Error Handling**: The `start_import` view already has fallback to synchronous execution if Celery fails

## Related Files
- `config/celery.py` - Celery app configuration
- `config/settings/base.py` - Celery settings
- `apps/portfolios/views.py` - Has fallback logic for Celery failures
- `apps/portfolios/tasks.py` - Celery task definitions

## Notes
- This is a platform-specific limitation, not a bug in the application code
- The `solo` pool is sufficient for development and small production workloads
- For high-throughput production on Windows, consider:
  - Using Linux containers (Docker)
  - Running Celery workers on a Linux server
  - Using `gevent` or `eventlet` pools (requires additional dependencies)
- The application already has graceful fallback to synchronous execution if Celery is unavailable

## Resolution Date
2026-01-03

## Fixed By
- Documented the issue and solution
- Updated worker startup command to use `--pool=solo` for Windows
- Added fallback logic in `start_import` view to handle Celery failures gracefully

