# Gmail setup for Orbit

One-time, about 15 minutes, done by you in a browser. Orbit uses `@klodr/gmail-mcp`, a hardened fork of the GongRzhe Gmail MCP server, registered twice in Claude Code (one per account) with a token that cannot send.

## 0. Requirements
Node 22 or newer (`node --version`), Claude Code logged in.

## 1. Google Cloud OAuth client (once, shared by both accounts)
1. console.cloud.google.com, create a project called `orbit`.
2. APIs & Services, Library, enable **Gmail API**.
3. APIs & Services, OAuth consent screen: External, add both Gmail addresses as test users.
4. Credentials, Create credentials, **OAuth client ID**, type **Desktop app**. Download the JSON.

## 2. Two config folders, one per account
```bash
mkdir -p ~/.gmail-mcp/career ~/.gmail-mcp/personal
cp ~/Downloads/client_secret_*.json ~/.gmail-mcp/career/gcp-oauth.keys.json
cp ~/Downloads/client_secret_*.json ~/.gmail-mcp/personal/gcp-oauth.keys.json
```

## 3. Authenticate each account with the modify scope only
`gmail.modify` = read, label, archive, trash. No send, no compose, no settings. The server filters its tool list by the granted scopes, so `send_email` will not exist.

```bash
GMAIL_OAUTH_PATH=~/.gmail-mcp/career/gcp-oauth.keys.json \
GMAIL_CREDENTIALS_PATH=~/.gmail-mcp/career/credentials.json \
npx -y @klodr/gmail-mcp auth --scopes=gmail.modify
```
A browser opens; sign in as **SamShaheen.tech@gmail.com**, accept. Then the same for personal:
```bash
GMAIL_OAUTH_PATH=~/.gmail-mcp/personal/gcp-oauth.keys.json \
GMAIL_CREDENTIALS_PATH=~/.gmail-mcp/personal/credentials.json \
npx -y @klodr/gmail-mcp auth --scopes=gmail.modify
```
Sign in as your personal account this time.

## 4. Register both servers with Claude Code (user scope, so every fire sees them)
```bash
claude mcp add --scope user gmail-career \
  -e GMAIL_OAUTH_PATH=$HOME/.gmail-mcp/career/gcp-oauth.keys.json \
  -e GMAIL_CREDENTIALS_PATH=$HOME/.gmail-mcp/career/credentials.json \
  -e GMAIL_MCP_STATE_DIR=$HOME/.gmail-mcp/career \
  -e GMAIL_MCP_AUDIT_LOG=$HOME/git/orbit/logs/gmail-career-audit.jsonl \
  -- npx -y @klodr/gmail-mcp

claude mcp add --scope user gmail-personal \
  -e GMAIL_OAUTH_PATH=$HOME/.gmail-mcp/personal/gcp-oauth.keys.json \
  -e GMAIL_CREDENTIALS_PATH=$HOME/.gmail-mcp/personal/credentials.json \
  -e GMAIL_MCP_STATE_DIR=$HOME/.gmail-mcp/personal \
  -e GMAIL_MCP_AUDIT_LOG=$HOME/git/orbit/logs/gmail-personal-audit.jsonl \
  -- npx -y @klodr/gmail-mcp
```
The audit log is an append-only record of every Gmail call Orbit makes, in your repo's `logs/` (gitignored).

## 5. Confirm
```bash
claude mcp list
```
Both `gmail-career` and `gmail-personal` should show as connected. The next fire picks the ops tasks up on its own; nothing to re-queue.

## 6. Dry run first (recommended)
Add `-e GMAIL_MCP_DRY_RUN=true` to both `claude mcp add` commands for the first day. Every write call returns what it would have done without touching Gmail; the fire logs read normally. Remove the flag when the labels look right, re-add the servers, and it goes live.

## Revoking
`claude mcp remove gmail-career` and `claude mcp remove gmail-personal`, then delete `~/.gmail-mcp/`, then revoke the app at myaccount.google.com, Security, Third-party access.
