# mail-agent — agent guide

General CLI email agent (read/send/search any inbox) + mutual-fund document requester.

> Self-contained rules. Source of truth: chirag127/workspace/knowledge/. Manual sync.

## Fleet rules (canonical — apply on every task)

### Prose + output
- **Caveman/terse.** Drop articles, filler, hedging. Answer in word 1. Code before prose. Full sentences only for irreversible-action confirmations.

### Code
- **Minimum everything.** Smallest unit that works. MAXIMIZE community packages, MINIMIZE own code. Build COMPLETE not MVP. Tests everywhere. Latest dep versions.
- **The ladder**: native/platform → codebase reuse → stdlib → one line → minimal own code.
- **Edit > Write.** No speculative scaffolding. Reuse existing patterns.

### Git
- **main only.** Direct commit on own repos, push by default, never force-push main. Conventional commits. Scan for secrets before push.

### Secrets — ALWAYS commit encrypted .env.enc
- Plaintext `.env` git-ignored; **sops+age-encrypted `.env.enc` committed** (recoverable). `.env.enc` MUST NOT be git-ignored. Fleet recipient `age1c40qjam…`, key in Bitwarden.

### Web + facts
- Search web ≥2× before non-trivial tool/pricing/library decisions.

## Project-specific (this repo)

- **Email engine = Himalaya CLI v2** (not v1 — config schema differs). `mail.py` wraps it via subprocess + `--json`. Needs the `himalaya` binary on PATH + a Gmail **App Password** (2FA on). Config rendered from `.env` → `config/himalaya-config.toml`.
- **CAS module** (`cas.py`) uses `casparser` + `pyxirr`. PDF password = investor PAN uppercase. Flow: request CAS from CAMS/KFintech/MFCentral → IMAP-poll inbox → download PDF → parse → XIRR.
- **Templates** (`templates/`): 4 folio-statement (RTA) + 9 scheme-literature (AMC) request bodies. `index.json` (RTA) + `index-amc-literature.json` (AMC) registries; `index-amc.json` = AMC/RTA email-address directory.
- **CLI**: `mail-agent list-templates | send-request | fetch-cas | inbox | search`.
- **Tests**: `py -3.13 -m pytest -q` (72 tests, all external calls mocked). Python 3.12+ (box python is 3.11; use `py -3.13`).
- **Private repo** — touches your inbox + PAN + folio. Never make public.
