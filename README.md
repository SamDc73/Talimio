# Talimio

An all-in-one, AI-powered learning platform. Create custom courses, chat with your books and videos, and it adapts as you learn.

## Quick Start (Docker Compose)

Prerequisites: Docker and Docker Compose installed.

Environment: All required .env values are defined directly in `docker-compose.yml`. You do not need `backend/.env`. To customize, edit the backend service `environment` block and optionally uncomment provider API keys.

1. Clone the repo

```
git clone https://github.com/SamDc73/Talimio.git
cd Talimio
```

2. Start the stack

```
docker compose up -d
```

3. Open the apps

- Frontend: http://localhost:5173
- API (FastAPI): http://localhost:8080

4. Optional: Pull Ollama models (first run)

- Skip if you use cloud LLMs and set provider keys in `docker-compose.yml`.

```
docker exec -it ollama ollama pull gpt-oss:20b
docker exec -it ollama ollama pull nomic-embed-text
```

Note: To disable the local LLM, comment out the `ollama` service in `docker-compose.yml` and set `PRIMARY_LLM_MODEL` to a cloud model. Provide the relevant API key(s) in the same `environment` block.

5. Stop/Update the stack

```
docker compose down
# update later
docker compose pull && docker compose up -d
```

## Local Development (without Docker)

1. Clone the repo

```
git clone https://github.com/SamDc73/Talimio.git
cd Talimio
```

2. Backend (Python 3.12+, uv):

```
cd backend
uv sync
cp .env.example .env
uv run uvicorn src.main:app --reload --port 8080
```

3. Frontend (Node + pnpm):

- Now in a diffrent tab/window:

```
cd web
cp .env.example .env
pnpm install
pnpm dev
```

4. Now you can open the apps:

- Frontend: http://localhost:5173
- API (FastAPI): http://localhost:8080

## Contributing

Any type of contribution is greatly apprietiated!

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

Questions, help, or feedback? Join our [Discord](https://discord.gg/YMCUFFjkCV)
