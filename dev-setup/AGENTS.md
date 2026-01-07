# DEV-SETUP KNOWLEDGE BASE

## OVERVIEW
Idempotent setup runner that orchestrates scripts in `runs/`.

## STRUCTURE
```
dev-setup/
├── run.sh          # Main orchestrator script
└── runs/           # Individual setup scripts
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| **Run Setup** | `run.sh` | Handles args, filtering, dry-runs |
| **Add Script** | `runs/` | Prefix with number for order |

## CONVENTIONS
- **Filtering**: `run.sh <filter>` grep-matches script names
- **Dry Run**: `run.sh --dry` skips execution
- **Logging**: Use `log()` function
- **Execution**: Use `execute()` wrapper

## COMMANDS
```bash
./run.sh          # Run all
./run.sh basic    # Run scripts matching "basic"
./run.sh --dry    # Simulate run
```
