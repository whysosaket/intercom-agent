# Intercom Auto-Responder

Automatically responds to Intercom messages using OpenAI, with Mem0 for answer memory and Slack for human-in-the-loop confirmation when confidence is low.

## How It Works

1. Customer sends a message in Intercom
2. Webhook fires → OpenAI generates a response with a confidence score
3. Past answers from Mem0 are used as context to improve responses over time
4. **High confidence (≥ 0.8)** → auto-replies directly in Intercom
5. **Low confidence (< 0.8)** → sends a review request to Slack with Approve / Edit / Reject buttons

## Prerequisites

- Docker & Docker Compose
- Intercom workspace (US region)
- OpenAI API key
- Mem0 platform account
- Slack workspace with a bot app

---

## Setup Guide

### 1. Intercom

**Get your Access Token:**
1. Go to [Intercom Developer Hub](https://developers.intercom.com/)
2. Create a new app (or use an existing one)
3. Go to **Configure → Authentication**
4. Copy the **Access Token**

**Get your Admin ID:**
1. Go to [Intercom API - List Admins](https://developers.intercom.com/docs/references/rest-api/api.intercom.io/Admins/listAdmins/)
2. Or call `GET https://api.intercom.io/admins` with your access token
3. Find your admin entry and copy the `id` field

**Set up the webhook:**
1. Go to **Configure → Webhooks** in your Intercom app settings
2. Set the webhook URL to `https://<your-domain>/webhooks/intercom`
3. Subscribe to these topics:
   - `conversation.user.created`
   - `conversation.user.replied`
4. Copy the **Webhook Secret** (found under **Configure → Authentication** as the Client Secret)

### 2. OpenAI

1. Go to [OpenAI API Keys](https://platform.openai.com/api-keys)
2. Create a new API key
3. The default model is `gpt-4o` — you can change it via `OPENAI_MODEL` in `.env`

### 3. Mem0

1. Sign up at [Mem0 Platform](https://app.mem0.ai/)
2. Go to **Settings → API Keys**
3. Create a new API key

No additional setup is needed — the app creates memory entries automatically using `infer=False` for verbatim storage.

### 4. Slack

**Create a Slack App:**
1. Go to [Slack API - Your Apps](https://api.slack.com/apps)
2. Click **Create New App → From scratch**
3. Name it (e.g., "Intercom Bot") and select your workspace

**Configure Bot Scopes:**
1. Go to **OAuth & Permissions → Scopes → Bot Token Scopes**
2. Add these scopes:
   - `chat:write` — send messages
   - `chat:write.public` — post to public channels
   - `channels:history` — read channel message history (needed for edit flow)

**Enable Interactivity:**
1. Go to **Interactivity & Shortcuts**
2. Turn on **Interactivity**
3. Set the **Request URL** to `https://<your-domain>/slack/events`

**Install the App:**
1. Go to **Install App** and click **Install to Workspace**
2. Authorize the requested permissions

**Get your credentials:**
- **Bot Token**: Found under **OAuth & Permissions** → `xoxb-...`
- **Signing Secret**: Found under **Basic Information → App Credentials**

**Get the Channel ID:**
1. Open Slack, right-click the channel where you want review messages
2. Click **View channel details**
3. The Channel ID is at the bottom (starts with `C`)

---

## Configuration

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

| Variable | Description | Where to find it |
|---|---|---|
| `INTERCOM_ACCESS_TOKEN` | Intercom API bearer token | Developer Hub → Authentication |
| `INTERCOM_WEBHOOK_SECRET` | Client Secret for HMAC verification | Developer Hub → Authentication |
| `INTERCOM_ADMIN_ID` | Admin ID used as the reply sender | `GET /admins` API call |
| `OPENAI_API_KEY` | OpenAI API key | platform.openai.com/api-keys |
| `OPENAI_MODEL` | Model name (default: `gpt-4o`) | Optional — change if needed |
| `MEM0_API_KEY` | Mem0 platform API key | app.mem0.ai → Settings |
| `SLACK_BOT_TOKEN` | Slack Bot OAuth token (`xoxb-...`) | Slack App → OAuth & Permissions |
| `SLACK_SIGNING_SECRET` | Slack app signing secret | Slack App → Basic Information |
| `SLACK_CHANNEL_ID` | Channel for review messages (`C...`) | Slack → Channel details |
| `CONFIDENCE_THRESHOLD` | Auto-respond threshold (default: `0.8`) | Set between 0.0–1.0 |
| `LOG_LEVEL` | Logging level (default: `INFO`) | DEBUG, INFO, WARNING, ERROR |
| `MOCK_MODE` | Enable mock mode (default: `false`) | Set to `true` for local testing |
| `CHAT_UI_ENABLED` | Enable chat test UI (default: `true`) | Set to `false` to disable `/chat` |

---

## Running

### Production (Docker)

```bash
# Build the Docker image
make build

# Start the server (detached)
make up

# View logs
make logs

# Stop
make down

# Restart
make restart

# Open a shell in the container
make shell
```

The server runs on **port 8000**. Verify it's working:

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

---

## Mock Mode

Mock mode lets you test the full AI pipeline locally without real Intercom or Slack credentials. Only the external messaging services are mocked — **OpenAI and Mem0 stay real** so you can properly test prompts, confidence scoring, and conversation memory.

### Prerequisites for mock mode

You still need valid keys for:
- `OPENAI_API_KEY` — real AI responses for prompt tuning
- `MEM0_API_KEY` — real conversation memory and knowledge base

Set these in your `.env` file before starting.

### Quick start

```bash
make mock
```

This runs `MOCK_MODE=true uvicorn app.main:api --host 0.0.0.0 --port 8000 --reload`.

Then open **http://localhost:8000/chat** in your browser to use the chat testing UI.

### What changes in mock mode

| Service | Behavior |
|---|---|
| **OpenAI** | **Real** — uses your API key, actual model responses |
| **Mem0** | **Real** — stores and retrieves conversation history and Q&A catalogue |
| **Intercom** | **Mocked** — logs replies to console instead of sending HTTP requests |
| **Slack** | **Mocked** — logs review requests to console instead of posting messages |

This means you get the exact same AI responses and memory behavior as production, just without messages actually going out to Intercom or Slack. Edit `app/prompts.py` to tune the system prompt or user prompt format, then restart the server to see changes.

---

## Chat Testing UI

The chat UI at `/chat` simulates customer conversations using the same AI pipeline as production.

### Two modes

**Automatic** — the AI response is sent immediately, just like a high-confidence auto-reply in production.

**Manual** — the AI generates a draft that you review with Approve / Edit / Reject buttons, mirroring the Slack review flow.

### How to use

1. Start the server (mock mode or production)
2. Open http://localhost:8000/chat
3. Click **New Session** to start a conversation
4. Type customer messages in the input box
5. Toggle between Automatic and Manual mode with the radio buttons
6. In Manual mode, review each AI draft before it's "sent"
7. Click any assistant message to see confidence and reasoning details in the side panel

Sessions are stored in memory and reset when the server restarts. Each session gets its own conversation history, so you can test multiple scenarios in parallel by opening multiple browser tabs.

### Disabling the chat UI

Set `CHAT_UI_ENABLED=false` in your `.env` to hide the `/chat` endpoint in production.

---

## Prompt Configuration

All prompt templates live in `app/prompts.py`:

- **`SYSTEM_PROMPT`** — the system message that defines the AI's role, confidence criteria, and JSON output format
- **`build_user_prompt()`** — assembles the user message from customer text, conversation history, and knowledge base matches

Edit this file to tune response style, confidence scoring, or output format. Changes take effect on server restart (immediate with `--reload`).

---

## Exposing Locally (for development)

Since Intercom and Slack need a public HTTPS URL to send webhooks, use [ngrok](https://ngrok.com/) during local development:

```bash
ngrok http 8000
```

Then use the ngrok HTTPS URL (e.g., `https://abc123.ngrok.io`) as the base for:
- Intercom webhook: `https://abc123.ngrok.io/webhooks/intercom`
- Slack Request URL: `https://abc123.ngrok.io/slack/events`

---

## Deploying to EC2 with Nginx

The project includes a production Docker Compose setup with Nginx for SSL termination.

### 1. Set up SSL certificates

Place your SSL cert and private key in the `nginx/ssl/` directory:

```
nginx/ssl/cert.pem
nginx/ssl/key.pem
```

For Let's Encrypt, you can use certbot to generate these, then copy or symlink them.

### 2. Configure your domain

Edit `nginx/nginx.conf` and replace `server_name _;` with your actual domain:

```nginx
server_name yourdomain.com;
```

### 3. Deploy

```bash
# Build and start with Nginx
make prod-build
make prod-up

# View logs
make prod-logs

# Stop
make prod-down
```

This starts two containers:
- **app** — FastAPI on port 8000 (internal only, not exposed to the host)
- **nginx** — reverse proxy on ports 80 and 443

Nginx handles:
- HTTP → HTTPS redirect on port 80
- SSL termination on port 443
- WebSocket upgrade for the chat UI at `/chat`
- Proxying all requests to the FastAPI app

### 4. Set your webhook URLs

Point Intercom and Slack to your domain:
- Intercom webhook: `https://yourdomain.com/webhooks/intercom`
- Slack Request URL: `https://yourdomain.com/slack/events`

---

## Syncing Existing Conversations

To import all your existing Intercom conversations into Mem0 (so the bot has context from day one), trigger a one-time sync:

```bash
curl -X POST http://localhost:8000/sync
# {"status":"sync_started","message":"Syncing all conversations in the background. Check logs for progress."}
```

This runs in the background and:
- Fetches all conversations from Intercom (paginated)
- Stores every message turn in per-conversation Mem0 history
- Extracts user-question → admin-reply pairs into the global answer catalogue

Monitor progress with `make logs`. Run this once after initial setup, or whenever you want to re-sync.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/webhooks/intercom` | Intercom webhook receiver |
| `POST` | `/slack/events` | Slack interactivity handler |
| `POST` | `/sync` | Sync all existing Intercom conversations into Mem0 |
| `GET` | `/chat` | Chat testing UI |
| `POST` | `/chat/sessions` | Create a new chat session |
| `GET` | `/chat/sessions` | List active chat sessions |
| `WS` | `/chat/ws/{session_id}` | WebSocket for real-time chat |
