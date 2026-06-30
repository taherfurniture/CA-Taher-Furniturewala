# Gmail OAuth2 Setup Guide

Complete these steps once. Total time: ~5 minutes.

---

## Step 1 — Create a Google Cloud Project

1. Go to **console.cloud.google.com**
2. Click the project dropdown (top-left) → **New Project**
3. Name it anything (e.g. `gmail-manager`) → **Create**
4. Wait ~10 seconds for it to be ready, then select it from the dropdown

---

## Step 2 — Enable the Gmail API

1. In the left sidebar: **APIs & Services → Library**
2. Search for **Gmail API** → click it → **Enable**

---

## Step 3 — Configure the OAuth Consent Screen

1. **APIs & Services → OAuth consent screen**
2. User Type: **External** → **Create**
3. Fill in required fields:
   - App name: `Gmail Manager` (or anything)
   - User support email: your Gmail address
   - Developer contact email: your Gmail address
4. Click **Save and Continue** through the Scopes screen (skip adding scopes here)
5. On the **Test users** screen, click **+ Add Users** and add your own Gmail address
6. Click **Save and Continue** → **Back to Dashboard**

> The app stays in "Testing" mode, which is fine for personal use.
> Up to 100 test users can be added.

---

## Step 4 — Create OAuth 2.0 Credentials

1. **APIs & Services → Credentials**
2. Click **+ Create Credentials → OAuth client ID**
3. Application type: **Desktop app**
4. Name: `gmail-manager-desktop` (or anything)
5. Click **Create**
6. In the popup, click **Download JSON**
7. Rename the downloaded file to **`credentials.json`**
8. Move it into this project folder (next to `email_manager.py`)

> `credentials.json` is in `.gitignore` — it will never be committed.

---

## Step 5 — Install Python Dependencies

```bash
pip install -r requirements.txt
```

---

## Step 6 — Set Up Your .env File

```bash
cp .env.example .env
```

Edit `.env` and fill in your Anthropic API key:

```
GOOGLE_CREDENTIALS_FILE=credentials.json
GOOGLE_TOKEN_FILE=token.json
ANTHROPIC_API_KEY=sk-ant-...   ← paste your key here
```

Get your Anthropic API key from **console.anthropic.com → API Keys**.

---

## Step 7 — First Run (triggers OAuth browser flow)

```bash
python email_manager.py triage
```

On first run:
1. A browser tab opens asking you to sign in to Google
2. Select your Gmail account
3. You'll see "Google hasn't verified this app" — click **Advanced → Go to gmail-manager (unsafe)**
4. Grant the requested permissions → **Continue**
5. The browser shows "The authentication flow has completed" — you can close it
6. `token.json` is saved automatically — future runs skip the browser step

---

## Scopes Granted

| Scope | Why needed |
|---|---|
| `gmail.readonly` | Read emails, threads, metadata |
| `gmail.send` | (Reserved — drafts are saved, never auto-sent) |
| `gmail.modify` | Save drafts, apply labels, archive |

---

## Troubleshooting

**`credentials.json` not found**
→ Re-download from Google Cloud Console → Credentials → your OAuth client → Download JSON

**`redirect_uri_mismatch`**
→ Make sure Application type is "Desktop app" (not Web application)

**Token expired / revoked**
→ Delete `token.json` and re-run — the browser flow will repeat

**`ANTHROPIC_API_KEY` error**
→ Check your `.env` file has the key set correctly (no extra spaces)

---

## Running the Tool

```bash
# Triage your unread inbox
python email_manager.py triage

# Draft a reply to a thread (get the thread ID from triage output)
python email_manager.py draft --thread 18f3a2b1c0d456

# Find threads you haven't heard back on in 7 days
python email_manager.py followup --days 7

# Weekly email digest
python email_manager.py summary
```
