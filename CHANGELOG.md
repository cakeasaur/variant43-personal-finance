## Changelog

### [0.1.0] — 2026-04-29

#### Added
- Transaction management: add / delete income and expenses
- Monthly dashboard: income, expense, balance cards with ‹ › month navigation
- Reports: bar charts by category and by day for current month
- Financial goals: create / edit / delete with progress bar and optional deadline
- Payment reminders: recurring (none / daily / weekly / monthly), mark as done
- AES-GCM encrypted SQLite database protected by user password (scrypt KDF)
- Cross-platform entrypoint (`main.py`) for desktop (PyInstaller) and Android (Buildozer)
- GitHub Actions CI: ruff lint + pytest + pip-audit (~30 s, headless, no Kivy)
- Docker support for running the same checks locally without installing Kivy

#### Security
- Plaintext DB lives only in system temp during runtime (`pfm_*.sqlite3`)
- Orphaned temp files from crashed sessions are cleaned up on next launch
- `atexit` handler ensures re-encryption even on unhandled exceptions
