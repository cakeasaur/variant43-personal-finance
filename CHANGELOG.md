## Changelog

### [0.2.0] — 2026-05-17

#### Changed
- Migrated UI layer from Kivy to Flet 0.85.1 (Flutter-based renderer)
- New entrypoint: `main_flet.py` (replaces `main.py` + `src/app.py`)
- Overview screen redesigned: delta metrics vs previous month, top expense
  categories panel, dynamic income/expenses chart (matplotlib → PNG)

#### Added
- Categories screen: full CRUD with type badge (income / expense / both)
- Settings screen: password change, encryption status, app info
- `income_by_day()` reporting function for dual-line chart

#### Fixed
- Encryption on window close: LIFO atexit race — temp DB was deleted before
  `shutdown_encrypt` could encrypt it; fixed by removing atexit from `_new_temp_db`
- Empty states centered horizontally across all screens
- Transaction rows without category: name centered vertically, no "—" placeholder

#### Removed
- Kivy UI layer (`src/ui/`, `src/app.py`, `main.py`, `buildozer.spec`)

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
