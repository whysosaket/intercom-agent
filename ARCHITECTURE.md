# Architecture Diagram — Intercom Auto-Responder

## System Overview

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              EXTERNAL SERVICES                                   │
│                                                                                  │
│  ┌─────────────┐   ┌─────────────┐   ┌──────────┐   ┌──────────┐   ┌─────────┐ │
│  │  Intercom    │   │  Slack      │   │  OpenAI  │   │  Mem0    │   │Mintlify │ │
│  │  (Customer   │   │  (Human     │   │  (LLM    │   │(Vector   │   │(Product │ │
│  │   Support)   │   │   Review)   │   │  Engine) │   │ Memory)  │   │  Docs)  │ │
│  └──────┬───────┘   └──────┬──────┘   └────┬─────┘   └────┬─────┘   └────┬────┘ │
└─────────┼──────────────────┼───────────────┼──────────────┼──────────────┼───────┘
          │                  │               │              │              │
          ▼                  ▼               ▼              ▼              ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                         FASTAPI APPLICATION (Port 8000)                          │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │                           WEBHOOK LAYER                                    │  │
│  │                                                                            │  │
│  │   POST /webhooks/intercom ──→ HMAC Verify ──→ Extract Message             │  │
│  │   POST /slack/events      ──→ Signature Verify ──→ Parse Action           │  │
│  │   POST /sync              ──→ Trigger Background Sync                     │  │
│  │   WS   /chat/ws/{id}      ──→ Chat Testing UI                            │  │
│  └──────────────────────────────────┬─────────────────────────────────────────┘  │
│                                     │                                            │
│                                     ▼                                            │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │                      ORCHESTRATOR AGENT (Central Hub)                      │  │
│  │                                                                            │  │
│  │  handle_incoming_message()                                                 │  │
│  │  ┌──────────────────────────────────────────────────────────────────────┐  │  │
│  │  │  1. Fetch Context  ──→  MemoryAgent                                 │  │  │
│  │  │  2. Generate Reply ──→  ResponseAgent                               │  │  │
│  │  │  3. Refine Output  ──→  PostProcessingAgent                         │  │  │
│  │  │  4. Route Decision ──→  Auto-Reply (Intercom) OR Review (Slack)     │  │  │
│  │  └──────────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                            │  │
│  │  Also owns: Intercom API client (httpx) for sending replies                │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │                            AGENT LAYER                                     │  │
│  │                                                                            │  │
│  │  ┌──────────────┐  ┌───────────────┐  ┌────────────────┐  ┌────────────┐  │  │
│  │  │ MemoryAgent  │  │ ResponseAgent │  │ PostProcessing │  │ SlackAgent │  │  │
│  │  │              │  │               │  │    Agent       │  │            │  │  │
│  │  │ Assembles    │  │ Primary LLM   │  │ Tone fix,      │  │ Sends      │  │  │
│  │  │ conversation │  │ response gen  │  │ confidence     │  │ review     │  │  │
│  │  │ context from │  │ + skill/doc   │  │ re-eval,       │  │ requests   │  │  │
│  │  │ memory       │  │ fallback      │  │ formatting     │  │ to Slack   │  │  │
│  │  └──────┬───────┘  └──────┬────────┘  └────────────────┘  └────────────┘  │  │
│  │         │                 │                                                │  │
│  │         ▼                 ▼                                                │  │
│  │  ┌──────────────┐  ┌─────────────────────────────────────┐                │  │
│  │  │ MemZeroAgent │  │         Fallback Chain              │                │  │
│  │  │              │  │                                     │                │  │
│  │  │ Mem0 SDK     │  │  DocAgent ──→ SkillAgent            │                │  │
│  │  │ wrapper      │  │  (Mintlify    (Local docs,          │                │  │
│  │  │ - search     │  │   search)      BM25 retrieval,      │                │  │
│  │  │ - add        │  │               tool execution)       │                │  │
│  │  │ - update     │  │                                     │                │  │
│  │  └──────────────┘  └─────────────────────────────────────┘                │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow: Incoming Customer Message

```
Customer sends message in Intercom
          │
          ▼
┌─────────────────────────┐
│ Intercom Webhook Event  │  (conversation.user.created / conversation.user.replied)
│ POST /webhooks/intercom │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ HMAC-SHA1 Verification  │──── FAIL ──→ 401 Unauthorized
└────────────┬────────────┘
             │ PASS
             ▼
┌─────────────────────────┐
│ Extract:                │
│ - conversation_id       │
│ - message_body (HTML→   │
│   plain text)           │
│ - contact_info (name,   │
│   email, id)            │
└────────────┬────────────┘
             │
             ▼  (Background Task)
┌──────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR PIPELINE                      │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ STEP 1: Memory Retrieval (MemoryAgent)                 │  │
│  │                                                        │  │
│  │  ├─→ MemZeroAgent.search_conversation_history()        │  │
│  │  │   (user-specific memory, top_k=5)                   │  │
│  │  │                                                     │  │
│  │  ├─→ MemZeroAgent.search_global_catalogue()            │  │
│  │  │   (FAQ / knowledge base, top_k=3)                   │  │
│  │  │                                                     │  │
│  │  └─→ Compute confidence_boost                          │  │
│  │      (if top global match score >= 0.95 → +0.1)        │  │
│  │                                                        │  │
│  │  Output: MemoryContext {history, matches, boost}        │  │
│  └────────────────────────────────────────────────────────┘  │
│                         │                                    │
│                         ▼                                    │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ STEP 2: Response Generation (ResponseAgent)            │  │
│  │                                                        │  │
│  │  ├─→ Build prompt (system + user + memory context)     │  │
│  │  ├─→ Call OpenAI API (gpt-5)                           │  │
│  │  ├─→ Parse JSON: {text, confidence, reasoning,         │  │
│  │  │               requires_human, is_followup}          │  │
│  │  ├─→ Apply memory confidence boost (+0.1 if matched)   │  │
│  │  │                                                     │  │
│  │  └─→ If confidence < threshold & !requires_human:      │  │
│  │      ├─→ Try DocAgent (Mintlify search)                │  │
│  │      │   └─→ Falls back to SkillAgent if conf < 0.6   │  │
│  │      └─→ Use higher-confidence response                │  │
│  │                                                        │  │
│  │  Output: GeneratedResponse {text, confidence,          │  │
│  │          reasoning, source}                            │  │
│  └────────────────────────────────────────────────────────┘  │
│                         │                                    │
│                         ▼                                    │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ STEP 3: Post-Processing (PostProcessingAgent)          │  │
│  │                                                        │  │
│  │  ├─→ Fix tone (friendly, professional)                 │  │
│  │  ├─→ Remove hedging language                           │  │
│  │  ├─→ Enforce formatting (code blocks, links)           │  │
│  │  ├─→ Check relevance to original question              │  │
│  │  └─→ Re-evaluate confidence (conservative)             │  │
│  │                                                        │  │
│  │  Output: Refined GeneratedResponse                     │  │
│  └────────────────────────────────────────────────────────┘  │
│                         │                                    │
│                         ▼                                    │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ STEP 4: Routing Decision                               │  │
│  │                                                        │  │
│  │  confidence >= 0.8 ─────────────┐                      │  │
│  │       │                         │                      │  │
│  │       ▼                         ▼                      │  │
│  │  ┌──────────┐          ┌──────────────┐                │  │
│  │  │AUTO-REPLY│          │ SLACK REVIEW │                │  │
│  │  └────┬─────┘          └──────┬───────┘                │  │
│  │       │                       │                        │  │
│  │       ▼                       ▼                        │  │
│  │  Intercom API:           Slack API:                    │  │
│  │  POST reply              Post message with             │  │
│  │       │                  [Approve][Edit][Reject]       │  │
│  │       ▼                                                │  │
│  │  Mem0: Store                                           │  │
│  │  exchange in                                           │  │
│  │  user memory                                           │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## Data Flow: Slack Review Actions

```
┌──────────────────────────────────────────────────────────┐
│                   SLACK REVIEW MESSAGE                    │
│                                                          │
│  Customer: "How do I reset my API key?"                  │
│  AI Response: "You can reset your key from..."           │
│  Confidence: 0.65 | Reasoning: "..."                     │
│                                                          │
│  [✅ Approve]  [✏️ Edit]  [❌ Reject]                     │
└─────┬──────────────┬──────────────┬──────────────────────┘
      │              │              │
      ▼              ▼              ▼
┌──────────┐  ┌────────────┐  ┌──────────┐
│ APPROVE  │  │   EDIT     │  │  REJECT  │
└────┬─────┘  └─────┬──────┘  └────┬─────┘
     │              │              │
     ▼              ▼              ▼
Send reply     Open modal     Mark rejected
to Intercom    with text      in Slack
     │              │              │
     ▼              ▼              │
Store in       Human edits    No Intercom
Mem0 (user     & submits      reply sent
memory)             │
     │              ▼
     │         Send edited
     │         reply to
     │         Intercom
     │              │
     │              ▼
     │         Store in Mem0:
     │         - user memory
     │         - global catalogue
     │           (curated QA)
     ▼
If from skill
agent → store
in global
catalogue
```

---

## Agent Hierarchy & Ownership

```
OrchestratorAgent
│   Owns: httpx AsyncClient (Intercom API)
│   Role: Central coordinator, pipeline execution
│
├── MemoryAgent
│   │   Role: Context assembly
│   │
│   └── MemZeroAgent
│       Owns: Mem0 MemoryClient
│       Role: Search/store in Mem0 (user + global namespaces)
│
├── ResponseAgent
│   │   Owns: OpenAI AsyncClient
│   │   Role: Primary response generation
│   │
│   └── Fallback Chain
│       │
│       ├── DocAgent
│       │   Owns: OpenAI client, httpx client
│       │   Role: Search Mintlify docs (llms.txt index → page fetch)
│       │
│       └── SkillAgent
│           Owns: OpenAI client, BM25 retriever
│           Role: Local doc navigation (think-act-observe loop)
│           Tools: read_file, fetch_url, run_script
│
├── PostProcessingAgent
│   Owns: OpenAI AsyncClient (optional)
│   Role: Tone, formatting, relevance, confidence refinement
│
└── SlackAgent
    Owns: Slack AsyncWebClient (optional, mock-able)
    Role: Send review messages, handle button/modal callbacks
```

---

## Memory Architecture (Mem0)

```
┌──────────────────────────────────────────────────────┐
│                    MEM0 PLATFORM                     │
│                  (Vector Memory)                     │
│                                                      │
│  ┌────────────────────┐  ┌────────────────────────┐  │
│  │  USER-SPECIFIC     │  │  GLOBAL CATALOGUE      │  │
│  │  MEMORY            │  │  (FAQ Knowledge Base)  │  │
│  │                    │  │                        │  │
│  │  Namespace:        │  │  Namespace:            │  │
│  │  user_id = email   │  │  user_id =             │  │
│  │  or conversation_id│  │  "global_catalogue"    │  │
│  │                    │  │                        │  │
│  │  Contains:         │  │  Contains:             │  │
│  │  - Past Q&A turns  │  │  - Curated QA pairs    │  │
│  │  - Per-customer    │  │  - Edited responses    │  │
│  │    context         │  │  - Skill agent answers │  │
│  │                    │  │  - Synced Intercom     │  │
│  │  Written when:     │  │    conversations       │  │
│  │  - Auto-reply sent │  │                        │  │
│  │  - Approved reply  │  │  Written when:         │  │
│  │    sent            │  │  - Human edits reply   │  │
│  │                    │  │  - Skill agent answer  │  │
│  │  Read when:        │  │    approved            │  │
│  │  - New message     │  │  - /sync executed      │  │
│  │    from same user  │  │                        │  │
│  │                    │  │  Read when:            │  │
│  │                    │  │  - Every new message   │  │
│  │                    │  │    (top_k=3)           │  │
│  └────────────────────┘  └────────────────────────┘  │
│                                                      │
│  Search returns: [{memory, score}, ...]              │
│  Score >= 0.95 → confidence boost +0.1               │
└──────────────────────────────────────────────────────┘
```

---

## Confidence Score Journey

```
                    ┌─────────────────┐
                    │  OpenAI returns  │
                    │  initial score   │
                    │  (0.0 - 1.0)    │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Memory Boost?   │
                    │ Global match    │
                    │ score >= 0.95   │──── YES ──→ score += 0.1
                    └────────┬────────┘             (cap at 1.0)
                             │ NO
                             ▼
                    ┌─────────────────┐
                    │ score < 0.8 &   │
                    │ !requires_human?│──── YES ──→ Try DocAgent/SkillAgent
                    └────────┬────────┘             Use higher score if better
                             │ NO
                             ▼
                    ┌─────────────────┐
                    │ PostProcessing  │
                    │ re-evaluation   │──→ May adjust conservatively
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ FINAL SCORE     │
                    │                 │
                    │ >= 0.8 → AUTO   │
                    │ <  0.8 → SLACK  │
                    └─────────────────┘
```

---

## Deployment Architecture

```
                    ┌──────────────────┐
                    │   Internet       │
                    │   (HTTPS:443)    │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              │    PRODUCTION │              │    DEVELOPMENT
              │              ▼              │
              │    ┌─────────────────┐     │    ┌─────────────────┐
              │    │     Nginx       │     │    │  Docker:        │
              │    │  (SSL termination│     │    │  FastAPI +      │
              │    │   reverse proxy)│     │    │  Uvicorn        │
              │    │   Port 80/443  │     │    │  Port 8000      │
              │    └────────┬────────┘     │    │                 │
              │             │              │    │  MOCK_MODE=true │
              │             ▼              │    │  (Intercom/Slack│
              │    ┌─────────────────┐     │    │   mocked,       │
              │    │  FastAPI +      │     │    │   OpenAI/Mem0   │
              │    │  Uvicorn        │     │    │   real)          │
              │    │  Port 8000      │     │    └─────────────────┘
              │    │  (internal)     │     │
              │    └─────────────────┘     │
              └────────────────────────────┘
```

---

## Technology Stack

```
┌─────────────────────────────────────────────┐
│                 APPLICATION                  │
│                                             │
│  Language:     Python 3.12                  │
│  Framework:    FastAPI (async)              │
│  Server:       Uvicorn                      │
│  Validation:   Pydantic v2                  │
│  HTTP Client:  httpx (async)               │
│                                             │
├─────────────────────────────────────────────┤
│               AI / ML LAYER                 │
│                                             │
│  LLM:         OpenAI (gpt-5 / gpt-5-mini) │
│  Memory:      Mem0 Platform (vector search) │
│  Retrieval:   BM25 (local skill docs)      │
│                                             │
├─────────────────────────────────────────────┤
│            EXTERNAL INTEGRATIONS            │
│                                             │
│  Customer:   Intercom API (webhooks + REST) │
│  Review:     Slack API (interactive msgs)   │
│  Docs:       Mintlify (llms.txt index)      │
│                                             │
├─────────────────────────────────────────────┤
│              INFRASTRUCTURE                 │
│                                             │
│  Container:  Docker (Python 3.12-slim)      │
│  Proxy:      Nginx (SSL, WebSocket)         │
│  Compose:    docker-compose (dev + prod)    │
│  Storage:    Mem0 (cloud) + local JSON      │
└─────────────────────────────────────────────┘
```
