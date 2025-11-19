# Talimio

An all-in-one, AI-powered learning platform. Create custom courses, chat with your books and videos, highlight to make flashcards, and it adapts as you learn.

## Quick Start (Docker Compose)

Prerequisites: Docker and Docker Compose installed.

1. Clone the repo

```
git clone https://github.com/SamDc73/Talimio.git
cd Talimio
```

2. Prepare backend env

```
cp backend/.env.example backend/.env
```

3. Start the stack

```
docker compose up -d
```

4. Open the apps

- Frontend: http://localhost:5173
- API (FastAPI): http://localhost:8080

5. Learn and have fun, and give feadback!

```
docker compose down                 # stop
# or remove data too (CAUTION)
docker compose down -v              # stop and remove named volumes
# update later
docker compose pull && docker compose up -d
```

### Models (Ollama) and Auto‑Pull

- Set models via env; any value starting with `ollama/` is auto‑pulled by the Ollama service at startup:
  - `PRIMARY_LLM_MODEL=ollama/llama3.2:3b`
  - `RAG_EMBEDDING_MODEL=ollama/nomic-embed-text`
  - `MEMORY_LLM_MODEL=ollama/llama3.2:3b`
  - `MEMORY_EMBEDDING_MODEL=openai/text-embedding-3-small` (requires `OPENAI_API_KEY` to use memory embeddings)
  - `MEMORY_EMBEDDING_OUTPUT_DIM=1536`

- Don’t want auto‑pull? First request will lazy‑pull the model (slower cold start), or pre‑pull manually:
  - Docker:
    - `docker compose exec talimio_ollama ollama pull llama3.2:3b`
    - `docker compose exec talimio_ollama ollama pull nomic-embed-text`
  - Or via HTTP API:
    - `curl -s http://localhost:11434/api/pull -d '{"name":"llama3.2:3b"}'`
    - `curl -s http://localhost:11434/api/pull -d '{"name":"nomic-embed-text"}'`

## Local Development (without Docker)

Backend (Python 3.12+, uv):

```
cd backend
uv sync
uv run uvicorn src.main:app --reload --port 8080
```

Frontend (Node + pnpm):

```
cd web
pnpm install
pnpm dev   # http://localhost:5173
```

The dev frontend proxies API calls to `http://localhost:8080` by default.

## Contributing

Start tiny. Most merged PRs are under 50 lines and take 5–10 minutes. Small wins compound and we review those fastest.

### First timer flow:

1. Pick one tiny improvement

- Fix a typo, clarify a log/error message, tidy a function name, or improve copy.
- Good places: `README.md`, `backend/src/**` (messages/docs), `web/src/**` (copy/UI nits).

2. Run it locally

- Use Quick Start above, and test it out.

3. Run checks before PR

- Backend: `cd backend && ruff check src --fix`
- Backend types: `cd backend && uvx ty check src`
- Frontend: `cd frontend && pnpm run lint`

4. Open a draft PR

- Two bullets are enough: why it helps, what changed.

## Support

Questions, help, or feedback? Join our Discord:
https://discord.gg/YMCUFFjkCV
