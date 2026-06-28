# QA - Mathematical Benchmark Evaluation and AI Q&A Platform

QA is a web platform for mathematical research questions. It has two main modules:

1. **AI QA**: submit a mathematical question to the Doubao deep-thinking model and generate multiple independent answers in one request.
2. **Benchmark Make**: turn a problem, reference solution, rubric, Doubao answer, and analysis into an English `.tex` benchmark document.

Internal service URL:

```text
http://10.9.22.19:3002/
```

The server is on an internal network. Access requires the appropriate LAN or VPN connection.

## Product Behavior

### AI QA

- A user can request 1 to 8 independent answers for one question.
- Each answer slot is a separate model request. Slots do not share conversation context with each other.
- Generation runs in the backend. The frontend creates a session, navigates to the session page, and polls until answers are stored.
- The user-facing experience should be understood as background generation followed by final result display. The initial QA flow does not promise token-by-token streaming in the UI.
- The stored result for each slot contains the model's returned thinking summary and final answer.
- A completed slot can be regenerated independently.
- If the user leaves the page after submitting a question, backend tasks continue running and the finished answers can be viewed later from history.

### Benchmark Make

- A benchmark draft contains six required fields:
  1. Problem
  2. Origin of the Problem
  3. Solution to Problem
  4. Rubric
  5. Doubao Model's Answer
  6. Doubao Model's Answer Analysis
- The backend uses `claude-agent-sdk` with DeepSeek V4 Pro to generate an English `.tex` document.
- Each generation runs in an isolated sandbox directory. The model only receives the current session input file and the benchmark skill files.
- Drafts can be saved, regenerated, hidden, pinned, and downloaded after generation.
- The progress bar is a frontend animation. It is not a precise model progress indicator.

### Accounts and History

- Login is username-only. There is no password.
- Entering the same username returns to the same account.
- QA and Benchmark history entries can be pinned or hidden.
- Login is rate-limited by client IP: 10 login attempts per minute.

## Technology Stack

| Layer | Technology |
| --- | --- |
| Backend | FastAPI + Uvicorn |
| Database | SQLite in WAL mode |
| Frontend | React + Vite |
| AI QA | OpenAI SDK + Volcengine Ark Responses API |
| AI QA model | `doubao-seed-2-1-pro-260628` |
| Benchmark Make | `claude-agent-sdk` + DeepSeek Anthropic-compatible API |
| Benchmark model | `deepseek-v4-pro[1m]` |
| Service port | `3002` |

SQLite database path:

```text
server/data/arxiv_qa.db
```

## Repository Layout

```text
QA/
├── backend/
│   ├── app.py          # FastAPI entrypoint and SPA static file serving
│   ├── auth.py         # Username login, JWT, login rate limiting
│   ├── database.py     # SQLite schema and lightweight migrations
│   ├── ai_qa.py        # AI QA, Ark Responses API, SSE events, continuation, persistence
│   └── benchmark.py    # Benchmark Make, sandbox isolation, claude-agent-sdk, .tex output
├── frontend-web/       # React/Vite frontend
├── .claude/skills/
│   └── benchmark/      # Benchmark skill and reference template
├── scripts/
│   ├── backup.sh       # Database and code snapshot backup
│   ├── restore.sh      # Backup restore helper
│   └── setup-cron.sh   # Hourly backup cron installer
├── requirements.txt
└── server/data/        # SQLite database directory, ignored by Git
```

## Secret Management

The GitHub repository should contain placeholders only. Do not commit real API keys, JWT secrets, SSH passwords, or server credentials.

Replace these placeholders only in the local or server runtime copy:

| File | Placeholder | Purpose |
| --- | --- | --- |
| `backend/ai_qa.py` | `<VOLC_ENGINE_API_KEY>` | Volcengine Ark API key |
| `backend/benchmark.py` | `<DEEPSEEK_API_KEY>` | DeepSeek API key |
| `backend/auth.py` | `<JWT_SECRET_KEY>` | JWT signing secret |

Before pushing to GitHub, verify that these files contain placeholders rather than real secrets.

## AI QA Model Configuration

The current AI QA module uses the Volcengine Ark Responses API through the OpenAI SDK:

```python
BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
MODEL = "doubao-seed-2-1-pro-260628"
MAX_OUTPUT_TOKENS = 262144
MAX_CONTINUATIONS = 20
ARK_MAX_RPM = 500
MAX_CONCURRENT_ARK_REQUESTS = 500
ARK_MAX_WAIT_TIMEOUT_MS = "300000"

response = await client.responses.create(
    model=MODEL,
    instructions=SYSTEM_PROMPT,
    input=input_data,
    stream=True,
    max_output_tokens=MAX_OUTPUT_TOKENS,
    extra_body={"thinking": {"type": "enabled"}},
    reasoning={"effort": "high"},
    extra_headers={"X-Ark-Max-Wait-Timeout-Ms": ARK_MAX_WAIT_TIMEOUT_MS},
    previous_response_id=prev_response_id,
)
```

Notes:

- `BASE_URL` matches Ark's OpenAI-compatible endpoint.
- `doubao-seed-2-1-pro-260628` supports Responses API.
- `thinking.type="enabled"` is supported by this model.
- `reasoning.effort="high"` is used for difficult mathematical questions.
- `max_output_tokens` controls the combined output budget for reasoning/thinking summary plus final answer in Responses API.
- `X-Ark-Max-Wait-Timeout-Ms="300000"` allows Ark to queue burst traffic for up to 5 minutes before timing out.
- The backend consumes Ark streaming events for reliability, but the product does not rely on token-by-token display in the initial frontend QA flow.

Ark's public limit for this model is `500 RPM` and `1,000,000 TPM`. The exact public `Inflight Batchsize` value is not documented, so high-concurrency long-running questions may still encounter queuing, 429 responses, or long waits.

## AI QA Continuation and Recovery

The backend implements several safeguards around Ark Responses API events:

1. **Length continuation**: if a response is incomplete or stops with `finish_reason == "length"`, the backend continues with `previous_response_id`.
2. **Empty-answer recovery**: if a Responses API call returns an empty `answer` and a `previous_response_id` is available, the backend uses the same Responses API context with `EMPTY_ANSWER_PROMPT` to ask the model to provide the final answer. This is same-context continuation, not a separate new-agent retry loop.
3. **Aggregate event reconciliation**: `response.output_text.done` and `response.reasoning_summary_text.done` are used to reconcile missed or partial delta events.
4. **Completed-event fallback**: `response.completed` is inspected as a final fallback for output text.
5. **Local RPM guard**: a sliding-window limiter and semaphore keep request starts within the public 500 RPM model limit.

Backend SSE events include `queued`, `started`, `thinking`, `answer`, `done`, `error`, `continuation`, and `max_cont`. Some of these events are primarily backend lifecycle signals and may not be visibly represented in the current UI.

## Benchmark Make Configuration

Benchmark generation uses `claude-agent-sdk` with a sandboxed working directory:

```python
DEEPSEEK_ENV = {
    "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic",
    "ANTHROPIC_MODEL": "deepseek-v4-pro[1m]",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "deepseek-v4-pro[1m]",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "deepseek-v4-pro[1m]",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "deepseek-v4-flash",
    "CLAUDE_CODE_SUBAGENT_MODEL": "deepseek-v4-flash",
    "CLAUDE_CODE_EFFORT_LEVEL": "max",
    "CLAUDE_CODE_STREAM_CLOSE_TIMEOUT": "3600000",
}

opts = ClaudeAgentOptions(
    cwd=str(sandbox),
    setting_sources=["project"],
    skills="all",
    allowed_tools=["Skill", "Read", "Write"],
    permission_mode="bypassPermissions",
    env=DEEPSEEK_ENV,
    system_prompt=SYSTEM_PROMPT,
    model="deepseek-v4-pro",
    include_partial_messages=True,
    load_timeout_ms=3600000,
)
```

The sandbox contains:

- `input.md`
- `output.tex`
- `.claude/skills/benchmark/SKILL.md`
- `.claude/skills/benchmark/references/`

The model is instructed to read only `input.md`, load the benchmark skill, and write the complete `.tex` output to `output.tex`.

## Local Setup

Prerequisites:

- Python 3.10+
- Node.js 22+
- Valid Volcengine Ark and DeepSeek API keys

Install Python dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Build the frontend:

```bash
cd frontend-web
npm install
npm run build
cd ..
```

Replace the local placeholders in:

- `backend/ai_qa.py`
- `backend/benchmark.py`
- `backend/auth.py`

Run the app:

```bash
python3 -m uvicorn backend.app:app --host 0.0.0.0 --port 3002
```

Open:

```text
http://localhost:3002/
```

## Frontend Development

For frontend-only development:

```bash
cd frontend-web
npm install
npm run dev
```

For production-style serving through FastAPI, rebuild the frontend:

```bash
cd frontend-web
npm run build
```

FastAPI serves `frontend-web/dist` directly when the directory exists.

## Server Deployment

Typical deployment directory:

```text
/home/liangchangyao/QA
```

Example update flow:

```bash
cd /home/liangchangyao/QA
git pull
cd frontend-web
npm install
npm run build
cd ..
pkill -f "uvicorn.*backend.app" 2>/dev/null || true
nohup python3 -m uvicorn backend.app:app --host 0.0.0.0 --port 3002 > nohup.out 2>&1 &
```

If the code was freshly pulled from GitHub, restore the runtime secrets after pulling and before restarting the service.

Always back up the production database before deployment or rollback:

```text
server/data/arxiv_qa.db
```

## Backup and Restore

Manual backup:

```bash
scripts/backup.sh
```

Install hourly backups:

```bash
scripts/setup-cron.sh
```

Default backup behavior:

- Database backups are written to `$HOME/QA-backups/db`.
- Code snapshots are written to `$HOME/QA-backups/code`.
- The latest 72 backups are retained, approximately 3 days of hourly backups.

Restore helpers:

```bash
scripts/restore.sh list
scripts/restore.sh db
scripts/restore.sh code
scripts/restore.sh full
```

## Database Tables

| Table | Purpose |
| --- | --- |
| `users` | Username-based accounts |
| `ai_sessions` | AI QA question sessions |
| `ai_answers` | One row per generated answer slot |
| `benchmark_sessions` | Benchmark drafts |
| `benchmark_outputs` | Generated `.tex` output and status |

`ai_answers` has a unique index on:

```sql
(session_id, slot)
```

This prevents multiple stored rows for the same answer slot in the same session.

## Verified Behavior

- The server runs on port `3002`.
- The `Test` account has completed multi-slot AI QA tests.
- Long mathematical questions can continue running in the backend and are stored when completed.
- Recent 2-slot testing showed no cross-user, cross-session, or cross-slot writes.
- The backend correctly marks sessions as running while generation is in progress and clears running state after completion.
- The Ark Responses API fields used by AI QA have been checked against the official Volcengine Ark documentation.
- The GitHub branch should contain placeholder secrets only. Server runtime files may contain real secrets and should not be pushed as-is.

## Common Questions

**Does AI QA show token-by-token streaming in the UI?**

No. The backend consumes streaming Responses API events, but the initial user-facing QA flow is background generation plus polling/final result display.

**Why can difficult math questions take a long time?**

The model runs with deep thinking enabled and `reasoning.effort="high"`. Difficult mathematical questions may spend several minutes waiting, thinking, or generating.

**What happens if the model returns a thinking summary but no final answer?**

If a response id is available, the backend attempts same-context continuation with `EMPTY_ANSWER_PROMPT`. If the result is still unsatisfactory, regenerate the affected slot.

**Do multiple answer slots affect each other?**

No. Slots are independent model requests and are stored by `(session_id, slot)`.

**Can real server secrets be pushed to GitHub?**

No. GitHub should contain placeholders only. If a real secret may have been exposed, rotate it.

## Maintenance Checklist

- Back up `server/data/arxiv_qa.db` before deployments and rollbacks.
- After changes, test login, AI QA generation, slot regeneration, Benchmark draft save, and Benchmark generation.
- Before pushing, verify that `backend/ai_qa.py`, `backend/benchmark.py`, and `backend/auth.py` contain placeholders.
- Watch for 429 errors, long-running sessions, empty answers, and TPM/RPM pressure during high-concurrency use.
