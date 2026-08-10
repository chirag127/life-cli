# mail-agent

General CLI email agent, plus a mutual-fund document requester. Sends/reads mail through the [himalaya](https://github.com/pimalaya/himalaya) binary, requests MF documents from RTAs and AMCs, polls IMAP for the reply, parses the returned CAS PDF with [casparser](https://github.com/codereverser/casparser), and computes portfolio XIRR with [pyxirr](https://github.com/Anexen/pyxirr).

Minimal own code — himalaya does mail transport, casparser parses statements, pyxirr does the math.

## Install

```bash
pip install -e .
```

Requires:

- **himalaya** binary on PATH — `cargo install himalaya` (or download a release). Configure it for Gmail (see `config/himalaya-config.sample.toml`).
- **Gmail App Password** — Google account with 2FA, generate an App Password, put it in `.env` and in the himalaya config.

## Two document families

| Family | Source | What | Sent to |
|---|---|---|---|
| Folio statements (CAS) | RTA (CAMS / KFintech) | consolidated account statement PDF for all folios | `RTA_EMAIL` |
| Scheme literature | AMC | 9 scheme documents (SID, KIM, SAI, factsheet, portfolio disclosure, TER, half-yearly, annual report, addenda) | `AMC_EMAIL` |

## CAS workflow

```
mail-agent cas-request  ->  himalaya send request to RTA
        |
        v
mail-agent cas-poll     ->  IMAP poll every IMAP_POLL_SECONDS until PDF arrives or IMAP_POLL_TIMEOUT
        |
        v
mail-agent cas-parse    ->  casparser reads PDF (CAS_PASSWORD)
        |
        v
mail-agent cas-xirr     ->  pyxirr XIRR over the parsed transactions
```

## Usage

```bash
# general email
mail-agent send --to a@b.com --subject "Hi" --body "text"
mail-agent list --folder INBOX --limit 20
mail-agent read <id>

# folio statements (CAS)
mail-agent cas-request                       # email RTA for the CAS PDF
mail-agent cas-poll                           # wait for reply, save attachment to DOWNLOAD_DIR
mail-agent cas-parse downloads/cas.pdf         # parse -> JSON
mail-agent cas-xirr downloads/cas.pdf          # parse + compute portfolio XIRR

# scheme literature
mail-agent docs-request --scheme "<scheme name>"   # email AMC for the 9 documents
mail-agent docs-list                                # the 9 document types requested
```

## Config

`.env` (copy from `.env.example`):

| Key | Meaning |
|---|---|
| `GMAIL_ADDRESS` | your Gmail address |
| `GMAIL_APP_PASSWORD` | Gmail App Password |
| `HIMALAYA_ACCOUNT` | himalaya account name (`gmail`) |
| `IMAP_FOLDER` | folder to poll (`INBOX`) |
| `IMAP_POLL_SECONDS` | poll interval |
| `IMAP_POLL_TIMEOUT` | give up after N seconds |
| `DOWNLOAD_DIR` | where attachments land (`downloads`) |
| `CAS_PASSWORD` | password on the CAS PDF |
| `RTA_EMAIL` | RTA recipient for CAS requests |
| `AMC_EMAIL` | AMC recipient for scheme-doc requests |

## Security

- Gmail **App Password** lives in `.env` only. Never the real account password.
- `.env` is **git-ignored**. Never commit it.
- Commit the encrypted `.env.enc` instead (sops + age); decrypt locally to `.env`.
- `config/himalaya-config.toml` (real, with the App Password) is git-ignored; only `config/himalaya-config.sample.toml` is committed.
- `downloads/` (may contain your CAS PDF) is git-ignored.
