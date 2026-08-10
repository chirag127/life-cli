# gsuite-agent — one-time credential setup

You do these once (browser). Everything else is automated.

## A. Google OAuth (~7 min) — sign in as chiragsinghal127@gmail.com

### 1. Create project
- console.cloud.google.com → project dropdown → **New Project** → name `gsuite-agent` → Create → select it.

### 2. Enable APIs (click Enable on each)
- Gmail: https://console.cloud.google.com/apis/library/gmail.googleapis.com
- Drive: https://console.cloud.google.com/apis/library/drive.googleapis.com
- Docs: https://console.cloud.google.com/apis/library/docs.googleapis.com
- Sheets: https://console.cloud.google.com/apis/library/sheets.googleapis.com
- Calendar: https://console.cloud.google.com/apis/library/calendar-json.googleapis.com
- Optional: People (contacts), Tasks, Photos Library APIs.

### 3. OAuth consent screen (APIs & Services → OAuth consent screen)
- User Type **External** → Create.
- App name `gsuite-agent`, support email + dev email = yours → Save and Continue.
- Scopes → Save and Continue (scopes set in code).
- **Test users → Add**: BOTH `chiragsinghal127@gmail.com` + `whyiswhen@gmail.com` → Save.
- (Testing mode = no Google review; tokens expire 7 days. Click **Publish App** to make permanent — still no review for personal use.)

### 4. OAuth client (APIs & Services → Credentials)
- **+ Create Credentials → OAuth client ID** → type **Desktop app** → name `gsuite-agent` → Create.
- **Download JSON**.

### 5. Save it exactly here
```
config/google-oauth-client.json
```

### 6. Mint tokens (agent runs; you click Allow in the browser)
```
py -3.13 -m gsuite_agent.gtool -A why accounts list
py -3.13 -m gsuite_agent.gtool -A chirag accounts list
```

## B. Microsoft (Azure) OAuth (~3 min) — for Outlook/OneDrive/Calendar

### 1. Register an app
- portal.azure.com → **Microsoft Entra ID → App registrations → New registration**.
- Name `gsuite-agent`. Supported account types: **Accounts in any org directory and personal Microsoft accounts** (so personal Outlook.com + work both work).
- Redirect URI: platform **Public client/native**, value `http://localhost`.
- Register.

### 2. Copy the Client ID
- Overview page → copy **Application (client) ID**.

### 3. Put it in .env (git-ignored)
```
MICROSOFT_CLIENT_ID=<the client id>
MICROSOFT_TENANT_ID=common
```

### 4. Mint token (agent runs; you sign in)
```
py -3.13 -m gsuite_agent.gtool -P microsoft -A why mail inbox
```

## C. GitHub
Already authed via `gh`. Nothing to do.

## D. Mutual funds (optional, why account)
Put your PAN (uppercase) in `.env`: `INVESTOR_PAN=ABCDE1234F`

## Cloud automation (GitHub Actions, free public minutes)
After tokens exist locally: the refresh tokens get stored as GitHub Secrets;
scheduled workflows in the `cloud-automation` repo mint short-lived access tokens
and run without a browser. See that repo's README.
