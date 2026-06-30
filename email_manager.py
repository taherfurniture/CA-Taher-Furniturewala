#!/usr/bin/env python3
"""
email_manager.py — Gmail management powered by Claude AI.

Usage:
    python email_manager.py triage
    python email_manager.py draft --thread <thread_id>
    python email_manager.py followup --days <N>
    python email_manager.py summary
"""

import argparse
import base64
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]

CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
TOKEN_FILE = os.getenv("GOOGLE_TOKEN_FILE", "token.json")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


# ── Auth ──────────────────────────────────────────────────────────────────────

def get_gmail_service():
    """Authenticate via OAuth2 and return an authorised Gmail API service."""
    creds = None

    if Path(TOKEN_FILE).exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not Path(CREDENTIALS_FILE).exists():
                raise FileNotFoundError(CREDENTIALS_FILE)
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as fh:
            fh.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def get_claude_client():
    if not ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY is not set in your .env file.")
        sys.exit(1)
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


# ── Helpers ───────────────────────────────────────────────────────────────────

def confirm_action(prompt="Confirm action?"):
    """Gate all write operations. Returns True only for explicit 'y'."""
    answer = input(f"\n{prompt} [y/N]: ").strip().lower()
    if answer != "y":
        print("Aborted.")
        return False
    return True


def get_headers(msg):
    """Return a dict of header name → value from a Gmail message object."""
    return {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}


def extract_body(payload):
    """Recursively extract plain-text body from a Gmail payload."""
    body = ""
    if "parts" in payload:
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain":
                data = part.get("body", {}).get("data", "")
                if data:
                    body += base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
            elif "parts" in part:
                body += extract_body(part)
    else:
        if payload.get("mimeType") == "text/plain":
            data = payload.get("body", {}).get("data", "")
            if data:
                body += base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    return body or "[No text body]"


def get_full_body(service, msg_id):
    msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
    return extract_body(msg["payload"])


def section(title):
    print(f"\n{'=' * 70}")
    print(title)
    print("=" * 70)


# ── Subcommand: triage ────────────────────────────────────────────────────────

def cmd_triage(service):
    """Fetch unread emails and categorise as HIGH / MEDIUM / LOW urgency."""
    print("Fetching unread emails from inbox...")

    result = service.users().messages().list(
        userId="me", q="is:unread in:inbox", maxResults=20
    ).execute()

    messages = result.get("messages", [])
    if not messages:
        print("Inbox is clear — no unread emails.")
        return

    emails = []
    for m in messages:
        msg = service.users().messages().get(
            userId="me",
            id=m["id"],
            format="metadata",
            metadataHeaders=["From", "Subject", "Date"],
        ).execute()
        h = get_headers(msg)
        emails.append({
            "id": m["id"],
            "from": h.get("From", "Unknown"),
            "subject": h.get("Subject", "(no subject)"),
            "date": h.get("Date", ""),
            "snippet": msg.get("snippet", "")[:200],
        })

    email_block = "\n\n".join(
        f"ID: {e['id']}\nFrom: {e['from']}\nSubject: {e['subject']}\n"
        f"Date: {e['date']}\nSnippet: {e['snippet']}"
        for e in emails
    )

    prompt = f"""You are an email triage assistant for a professional Chartered Accountant.

Categorise each email as HIGH, MEDIUM, or LOW urgency using these rules:
  HIGH   — deadlines, urgent client requests, legal/regulatory notices, overdue payments
  MEDIUM — client queries needing a reply within the week, meeting requests, follow-ups
  LOW    — newsletters, FYI threads, marketing, automated notifications

Return ONLY a JSON array, no prose:
[{{"id": "...", "urgency": "HIGH|MEDIUM|LOW", "reason": "one short line"}}]

Emails:
{email_block}"""

    client = get_claude_client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    start, end = raw.find("["), raw.rfind("]") + 1
    triage = json.loads(raw[start:end]) if start != -1 else []
    urgency_map = {r["id"]: r for r in triage}

    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    emails.sort(key=lambda e: order.get(urgency_map.get(e["id"], {}).get("urgency", "LOW"), 2))

    section(f"INBOX TRIAGE  —  {len(emails)} unread emails")
    for e in emails:
        info = urgency_map.get(e["id"], {})
        urgency = info.get("urgency", "?")
        badge = {"HIGH": "[!! HIGH !!]", "MEDIUM": "[  MEDIUM  ]", "LOW": "[   LOW    ]"}.get(urgency, "[  ?????  ]")
        print(f"\n{badge}  {e['subject'][:55]}")
        print(f"              From : {e['from'][:60]}")
        print(f"              Date : {e['date'][:30]}")
        print(f"            Reason : {info.get('reason', '')}")
        print(f"         Thread ID : {e['id']}")


# ── Subcommand: draft ─────────────────────────────────────────────────────────

def cmd_draft(service, thread_id):
    """Generate a reply draft and optionally save it to Gmail Drafts."""
    print(f"Fetching thread {thread_id} ...")

    thread = service.users().threads().get(
        userId="me", id=thread_id, format="full"
    ).execute()
    messages = thread.get("messages", [])

    if not messages:
        print("Thread not found or empty.")
        return

    # Build readable thread context (last 5 messages)
    context_parts = []
    for msg in messages[-5:]:
        h = get_headers(msg)
        body = get_full_body(service, msg["id"])
        context_parts.append(
            f"From: {h.get('From', '')}\n"
            f"Date: {h.get('Date', '')}\n"
            f"Subject: {h.get('Subject', '')}\n\n"
            f"{body[:600]}"
        )

    last_headers = get_headers(messages[-1])
    reply_to = last_headers.get("Reply-To") or last_headers.get("From", "")
    subject = last_headers.get("Subject", "")
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    prompt = f"""You are drafting a professional email reply for a Chartered Accountant.

Thread context (most recent messages):
{'\\n\\n---\\n\\n'.join(context_parts)}

Write a concise, professional reply body only (no subject line).
End with a professional sign-off. The sender's title is CA (Chartered Accountant)."""

    client = get_claude_client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )

    draft_body = response.content[0].text.strip()

    section("GENERATED DRAFT")
    print(f"To      : {reply_to}")
    print(f"Subject : {subject}")
    print("-" * 70)
    print(draft_body)
    print("=" * 70)

    if not confirm_action("Save this draft to Gmail Drafts?"):
        return

    mime_msg = MIMEText(draft_body)
    mime_msg["To"] = reply_to
    mime_msg["Subject"] = subject
    raw_msg = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode()

    draft = service.users().drafts().create(
        userId="me",
        body={"message": {"raw": raw_msg, "threadId": thread_id}},
    ).execute()

    print(f"Draft saved to Gmail Drafts.  Draft ID: {draft['id']}")


# ── Subcommand: followup ──────────────────────────────────────────────────────

def cmd_followup(service, days):
    """List sent threads with no incoming reply after N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_epoch = int(cutoff.timestamp())

    print(f"Searching for sent threads with no reply in the last {days} days...")

    result = service.users().messages().list(
        userId="me",
        q=f"in:sent before:{cutoff_epoch}",
        maxResults=40,
    ).execute()

    messages = result.get("messages", [])
    if not messages:
        print("No qualifying sent emails found.")
        return

    profile = service.users().getProfile(userId="me").execute()
    my_email = profile["emailAddress"].lower()

    seen_threads = set()
    stale = []

    for m in messages:
        tid = m["threadId"]
        if tid in seen_threads:
            continue
        seen_threads.add(tid)

        thread = service.users().threads().get(
            userId="me", id=tid, format="metadata",
            metadataHeaders=["From", "Subject", "Date", "To"],
        ).execute()

        msgs = thread.get("messages", [])
        if not msgs:
            continue

        last = msgs[-1]
        last_from = get_headers(last).get("From", "").lower()

        # If the last message in the thread is still from me, no reply received
        if my_email in last_from:
            first_h = get_headers(msgs[0])
            last_h = get_headers(last)
            stale.append({
                "thread_id": tid,
                "subject": first_h.get("Subject", "(no subject)"),
                "to": first_h.get("To", "?"),
                "last_sent": last_h.get("Date", "?"),
                "msg_count": len(msgs),
            })

    if not stale:
        print(f"No unreplied threads older than {days} days. All caught up!")
        return

    section(f"FOLLOW-UP NEEDED  —  {len(stale)} threads  (no reply in {days}+ days)")
    for t in stale:
        print(f"\nThread ID  : {t['thread_id']}")
        print(f"Subject    : {t['subject'][:60]}")
        print(f"To         : {t['to'][:60]}")
        print(f"Last sent  : {t['last_sent'][:30]}")
        print(f"Messages   : {t['msg_count']}")


# ── Subcommand: summary ───────────────────────────────────────────────────────

def cmd_summary(service):
    """Generate a weekly digest of inbox activity using Claude."""
    week_ago_epoch = int((datetime.now(timezone.utc) - timedelta(days=7)).timestamp())

    print("Pulling this week's inbox activity...")

    result = service.users().messages().list(
        userId="me",
        q=f"in:inbox after:{week_ago_epoch}",
        maxResults=40,
    ).execute()

    messages = result.get("messages", [])
    if not messages:
        print("No inbox activity in the past 7 days.")
        return

    # Deduplicate to threads
    thread_ids = list(dict.fromkeys(m["threadId"] for m in messages))

    threads_data = []
    for tid in thread_ids[:25]:
        thread = service.users().threads().get(
            userId="me", id=tid, format="metadata",
            metadataHeaders=["From", "Subject", "Date"],
        ).execute()
        msgs = thread.get("messages", [])
        if not msgs:
            continue

        first_h = get_headers(msgs[0])
        last_h = get_headers(msgs[-1])
        is_unread = "UNREAD" in msgs[-1].get("labelIds", [])

        threads_data.append({
            "subject": first_h.get("Subject", "(no subject)"),
            "from": first_h.get("From", "?"),
            "last_date": last_h.get("Date", "?"),
            "msg_count": len(msgs),
            "unread": is_unread,
        })

    thread_list = "\n".join(
        f"- [{('UNREAD' if t['unread'] else 'read')}] {t['subject'][:55]} "
        f"| From: {t['from'][:35]} | Messages: {t['msg_count']}"
        for t in threads_data
    )

    unread_count = sum(1 for t in threads_data if t["unread"])

    prompt = f"""Write a concise weekly email digest (under 300 words) for a Chartered Accountant.

Date: {datetime.now().strftime('%d %B %Y')}
Total threads this week: {len(threads_data)}
Unread threads: {unread_count}

Thread list:
{thread_list}

Structure the digest as:
1. Quick stats (one sentence)
2. Key topics / themes this week
3. Items likely needing follow-up or action
4. Anything that looks urgent

Be actionable and professional."""

    client = get_claude_client()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )

    section(f"WEEKLY EMAIL DIGEST  —  {datetime.now().strftime('%d %B %Y')}")
    print(response.content[0].text.strip())
    print("=" * 70)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Gmail management powered by Claude AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python email_manager.py triage\n"
            "  python email_manager.py draft --thread 18f3a2b1c0d\n"
            "  python email_manager.py followup --days 5\n"
            "  python email_manager.py summary\n"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("triage", help="Prioritise unread inbox emails by urgency")

    dp = sub.add_parser("draft", help="Generate and optionally save a reply draft")
    dp.add_argument("--thread", required=True, metavar="ID", help="Gmail thread ID")

    fp = sub.add_parser("followup", help="List threads awaiting a reply")
    fp.add_argument("--days", type=int, default=7, metavar="N",
                    help="Flag threads with no reply after N days (default: 7)")

    sub.add_parser("summary", help="Weekly digest of inbox activity")

    args = parser.parse_args()

    try:
        service = get_gmail_service()
    except FileNotFoundError:
        print(f"ERROR: {CREDENTIALS_FILE} not found.")
        print("Follow GMAIL_SETUP.md to download your OAuth credentials.")
        sys.exit(1)
    except Exception as exc:
        print(f"ERROR during Gmail authentication: {exc}")
        sys.exit(1)

    dispatch = {
        "triage": lambda: cmd_triage(service),
        "draft": lambda: cmd_draft(service, args.thread),
        "followup": lambda: cmd_followup(service, args.days),
        "summary": lambda: cmd_summary(service),
    }
    dispatch[args.command]()


if __name__ == "__main__":
    main()
