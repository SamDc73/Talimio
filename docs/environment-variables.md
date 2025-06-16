# Environment Variables

This document describes all environment variables used in the Learning Roadmap application.

## Frontend Environment Variables

The frontend uses Vite for configuration. All frontend environment variables must be prefixed with `VITE_`.

### API Configuration

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `VITE_API_BASE` | Base URL for API requests. Leave unset for same-domain deployments. | `/api/v1` | `http://localhost:8080/api/v1` |
| `VITE_PROXY_TARGET` | Backend URL for Vite dev server proxy | `http://localhost:8080` | `http://localhost:8080` |

### Development Server Configuration

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `VITE_DEV_SERVER_PORT` | Port for Vite development server | `5173` | `3000` |

### Feature Flags

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `VITE_DEBUG_MODE` | Enable debug mode | `true` | `false` |
| `VITE_ENABLE_AUTH` | Enable authentication features | `true` | `false` |
| `VITE_ENABLE_PERSONALIZATION` | Enable personalization features | `true` | `false` |
| `VITE_ENABLE_ANALYTICS` | Enable analytics tracking | `false` | `true` |

### External Services (Optional)

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `VITE_SENTRY_DSN` | Sentry error tracking DSN | - | `https://...@sentry.io/...` |
| `VITE_GA_TRACKING_ID` | Google Analytics tracking ID | - | `UA-XXXXXXXXX-X` |

## Backend Environment Variables

### Server Configuration

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `API_HOST` | Host address for the API server | `127.0.0.1` | `0.0.0.0` |
| `API_PORT` | Port for the API server | `8080` | `8000` |

### Database Configuration

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `DATABASE_URL` | PostgreSQL connection URL | - | `postgresql://user:pass@localhost/dbname` |

### Environment Settings

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `ENVIRONMENT` | Application environment | `development` | `production` |
| `DEBUG` | Enable debug mode | `True` | `False` |

### Authentication Settings

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `JWT_SECRET_KEY` | Secret key for JWT tokens | `test-secret-key-change-in-production` | `your-secret-key` |
| `JWT_ALGORITHM` | JWT signing algorithm | `HS256` | `HS256` |
| `JWT_EXPIRE_HOURS` | JWT token expiration in hours | `24` | `72` |
| `AUTH_DISABLED` | Disable authentication (dev only) | `false` | `true` |

### AI Model API Keys

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `OLLAMA_API_BASE` | Ollama API base URL | - | `http://localhost:11434` |
| `OPENAI_API_KEY` | OpenAI API key | - | `sk-...` |
| `OPENROUTER_API_KEY` | OpenRouter API key | - | `sk-or-...` |
| `ANTHROPIC_API_KEY` | Anthropic API key | - | `sk-ant-...` |
| `GEMINI_API_KEY` | Google Gemini API key | - | `...` |
| `DEEPSEEK_API_KEY` | DeepSeek API key | - | `...` |
| `HUGGINGFACE_API_KEY` | HuggingFace API key | - | `hf_...` |

### Memory System Settings

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `MEMORY_EMBEDDING_MODEL` | Model for memory embeddings | `huggingface/Qwen/Qwen3-Embedding-8B` | `openai/text-embedding-3-small` |
| `MEMORY_LLM_MODEL` | LLM model for memory processing | `openai/gpt-4o-mini` | `anthropic/claude-3-sonnet` |
| `MAX_MEMORIES_PER_USER` | Maximum memories per user | `1000` | `500` |
| `MEMORY_RELEVANCE_THRESHOLD` | Relevance threshold for memory retrieval | `0.7` | `0.8` |

## Deployment Scenarios

### Local Development (Default)

No environment variables required! The application works out of the box with sensible defaults:

```bash
# Frontend runs on http://localhost:5173
cd frontend && pnpm run dev

# Backend runs on http://localhost:8080
cd backend && uvicorn src.main:app --reload
```

### Same-Domain Production

When frontend and backend are served from the same domain:

```bash
# Frontend .env
# No VITE_API_BASE needed - uses relative paths

# Backend .env
API_HOST=0.0.0.0
API_PORT=8080
DATABASE_URL=postgresql://user:pass@localhost/dbname
JWT_SECRET_KEY=your-production-secret-key
ENVIRONMENT=production
DEBUG=False
```

### Cross-Domain Production

When frontend and backend are on different domains:

```bash
# Frontend .env
VITE_API_BASE=https://api.example.com/api/v1

# Backend .env (same as above plus CORS configuration)
API_HOST=0.0.0.0
API_PORT=8080
# Configure CORS in your deployment
```

### Docker Deployment

```bash
# Frontend Dockerfile
ARG VITE_API_BASE
ENV VITE_API_BASE=$VITE_API_BASE

# Backend environment
API_HOST=0.0.0.0
API_PORT=8080
DATABASE_URL=postgresql://user:pass@db:5432/dbname
```

## Best Practices

1. **Never commit `.env` files** - Use `.env.example` as templates
2. **Use strong secrets** in production for `JWT_SECRET_KEY`
3. **Leave `VITE_API_BASE` unset** for same-domain deployments (uses relative paths)
4. **Set appropriate feature flags** based on your deployment needs
5. **Configure AI API keys** only for the models you plan to use

## Migration Guide

If you're upgrading from a version with hardcoded values:

1. Copy `.env.example` files to `.env` in both frontend and backend directories
2. Update any custom ports or domains you were using
3. Remove any local modifications to hardcoded values
4. Restart both frontend and backend services

The application will continue to work exactly as before, but now with full configurability!