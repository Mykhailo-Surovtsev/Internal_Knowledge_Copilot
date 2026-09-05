# Support Knowledge Copilot

A grounded internal-knowledge API for Support Operations. It retrieves relevant policy and escalation-playbook fragments from Markdown files, then uses an LLM to formulate an answer with cited source filenames.

This is deliberately an internal tool, not a customer-facing chatbot. It demonstrates a practical AI workflow for helping support teams find approved information without treating a model response as a source of truth.

## What it demonstrates

- Python, FastAPI, and documented HTTP APIs;
- RAG: document chunking, embeddings, vector search, and grounded answers;
- structured LLM output with source validation;
- safe fallbacks when no context is available or an LLM provider is unavailable;
- an internal API key for sensitive endpoints;
- structured request logs, request IDs, readiness checks, tests, and evaluation cases;
- Docker packaging with persistent local Qdrant storage.

## Architecture

~~~mermaid
flowchart LR
    Docs[Support policies and playbooks] --> Chunk[Chunk Markdown]
    Chunk --> Embed[FastEmbed embeddings]
    Embed --> Store[(Qdrant local index)]

    Agent[Support agent or internal tool] --> API[FastAPI]
    API --> Search[Semantic search]
    Store --> Search
    Search --> Context[Retrieved context]
    Context --> LLM[Groq structured-output model]
    LLM --> Answer[Answer, sources, grounded flag]
~~~

## Key design decisions

| Decision | Why it matters |
| --- | --- |
| The model sees only retrieved chunks | It is instructed to answer from the knowledge base, not from assumed company policy. |
| Source filenames are validated | The model cannot cite a file that was not retrieved. |
| Empty context returns a deterministic fallback | The service does not call an LLM when retrieval produced no context. |
| `POST /index` is protected when a key is configured | A user who can reach the API should not be able to rebuild the knowledge base accidentally. |
| Health and readiness are separate | The process can be alive while the vector index is absent or unavailable. |
| Qdrant closes during application shutdown | The embedded store does not rely on interpreter cleanup. |

The included documents are fictional examples: an incident-response guide, a support-escalation playbook, and an internal work-policy document. Do not index production information until access, retention, and privacy requirements are defined.

## Quick start

### 1. Configure local secrets

Copy the template, then add a Groq key only to the ignored `.env` file:

~~~powershell
Copy-Item .env.example .env
~~~

~~~text
GROQ_API_KEY=your_groq_key
# Optional: this model is the default when GROQ_MODEL is omitted.
GROQ_MODEL=qwen/qwen3.8-27b
# Optional for a local demo. Set a long random value before exposing the API.
API_SHARED_SECRET=
~~~

`GROQ_API_KEY` is needed only for `POST /ask`. Indexing and semantic search work locally without it.

### 2. Run locally

~~~powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8001
~~~

Open [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs). Call `POST /index` once after startup or after changing a Markdown document.

### 3. Run with Docker

~~~powershell
docker build --tag support-knowledge-copilot:1.0.0 .

New-Item -ItemType Directory -Force storage
$projectPath = (Get-Location).Path

docker run --rm --name support-knowledge-copilot --env-file .env --publish 127.0.0.1:8001:8001 --mount "type=bind,source=$projectPath\storage,target=/app/storage" support-knowledge-copilot:1.0.0
~~~

The port binds only to `127.0.0.1`. Do not expose it on a network until `API_SHARED_SECRET`, HTTPS, access control, and rate limits are configured.

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Process liveness check |
| `GET` | `/ready` | Vector-index readiness check |
| `GET` | `/chunks` | Inspect indexed document chunks |
| `POST` | `/index` | Rebuild the local vector index |
| `POST` | `/search` | Return retrieved chunks and relevance scores |
| `POST` | `/ask` | Return a grounded answer with source filenames |

If `API_SHARED_SECRET` is set, `/chunks`, `/index`, `/search`, and `/ask` require this header:

~~~text
X-Internal-Api-Key: your_shared_secret
~~~

Example `POST /ask` body:

~~~json
{
  "query": "When should a support ticket be escalated to the urgent queue?"
}
~~~

Example response:

~~~json
{
  "answer": "Escalate when a customer cannot access a core function, reports a security or privacy issue, or reports a duplicate payment or suspected fraud.",
  "sources": ["support_escalation.md"],
  "grounded": true
}
~~~

For a question without support in the retrieved context, the API returns `grounded: false` and an empty source list. A missing index returns `409`; a missing model key returns `503`; an upstream model failure returns `502`.

## Observability and evaluation

Each request produces a JSON log with a request ID, method, path, response status, and latency. The same ID is returned in `X-Request-ID`. Invalid request-ID headers are replaced with a generated UUID before logging.

Run unit tests:

~~~powershell
python -m pytest -q
~~~

Run the end-to-end evaluation only after configuring Groq:

~~~powershell
python -m app.evaluation
~~~

The evaluation covers supported policy questions, an unsupported parental-leave question, and a prompt-injection attempt. It checks the `grounded` flag and expected sources; it is not a measure of production answer quality.