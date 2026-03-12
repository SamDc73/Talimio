# Grafana-First Observability TODO for Talimio

Goal: get production-grade observability in place fast, with **Grafana Cloud as the only new signup right now**, and keep the stack **OTel-first**, low-abstraction, and easy to maintain across:

- Cloudflare-hosted React frontend
- Google Cloud Run FastAPI backend
- Neon Postgres

## Doc-Verified Direction

- [x] Use **Grafana Cloud** as the single front door for dashboards, alerts, traces, logs, RUM, and synthetics.
- [x] Use **Grafana Faro** for frontend observability. Grafana documents Faro as the frontend observability SDK and supports React + React Router integrations.
- [x] Use **OpenTelemetry** for backend instrumentation and export to Grafana Cloud over **OTLP**.
- [x] Start with **direct OTLP export from the backend app** to avoid adding another service immediately.
      Note: Grafana documents **Alloy** as the recommended production architecture, but direct OTLP from the app is the lower-maintenance starting point for a single Cloud Run backend. Add Alloy later only if routing, filtering, buffering, or multi-destination export becomes necessary.
- [x] Use **Grafana Synthetic Monitoring / k6 browser checks** to continuously run critical user journeys like signup, login, and course creation.
- [x] Do **not** add Sentry, Highlight, or Phoenix in phase 1.
      Why: the first real gap is app observability and alerting. Grafana can cover that now with less stack sprawl.

## What We Are Explicitly Not Doing First

- [x] Do not deploy **Grafana Alloy** in phase 1.
      Reason: one more moving service on Cloud Run is extra work and extra failure surface.
- [x] Do not add **Cloudflare-specific observability integrations** in phase 1.
      Reason: Talimio’s immediate pain is app failures, not CDN/WAF deep analytics.
- [x] Do not add **Neon-specific monitoring/exporters** in phase 1.
      Reason: user-facing failures should already be visible from frontend RUM + backend traces/logs + synthetic checks.
- [x] Do not add **LLM observability** in phase 1.
      Reason: first catch the request failures themselves before tracing prompt-level internals.

## Phase 0: Grafana Cloud Account + Structure

- [x] Create the Grafana Cloud stack.
- [x] Enable / note the products we will actually use now:
  - Grafana
  - Frontend Observability
  - Application Observability
  - Synthetic Monitoring
  - Alerting
- [x] Create a naming convention for environments and services:
  - `env=prod|staging`
  - `service=web|api`
  - `region=us-west1`
- [x] Decide one canonical release/version tag for both frontend and backend.
      Recommendation: Git SHA injected into both builds.

## Phase 1: Frontend Observability with Faro

### Why

- [x] Frontend observability is the fastest way to catch user-visible failures like:
  - `Failed to fetch`
  - route-specific failures
  - degraded page loads
  - broken create-course flows

### Implementation

- [x] Add Faro to the React app using the **React SDK**, not the plain script snippet.
      Why: this repo already uses React + `HashRouter`, so the React integration is the cleanest long-term fit.
- [x] Wire Faro into `web/src/main.jsx`.
- [x] Add React Router instrumentation for the current hash-routing setup.
- [x] Capture:
  - page loads
  - navigation changes
  - unhandled errors
  - handled app errors that currently only reach console logs
  - web vitals / performance timings
- [x] Enable session-level frontend observability in Grafana Cloud.
- [x] Add source-map upload for production builds.
      Recommendation: use the Grafana Faro bundler/Vite path rather than a custom script.

### Frontend Dashboard + Alerts

- [ ] Create a `web-prod` dashboard showing:
  - JS error count
  - error rate by route
  - slow page loads
  - failed fetches / network errors
  - release/version dimension
- [ ] Alert on:
  - sudden frontend error spike
  - create-course page / modal error spike
  - login/signup page error spike

## Phase 1: Backend Observability with OTel Direct to Grafana Cloud

### Why

- [x] Backend traces and logs should reveal request failures like:
  - `POST /api/v1/courses/` 4xx/5xx spikes
  - DB write failures
  - AI generation latency spikes
  - retries / timeouts

### Implementation

- [x] Instrument FastAPI with OpenTelemetry.
- [x] Export traces and metrics from the backend directly to Grafana Cloud OTLP endpoints.
- [x] Keep Cloud Run stdout/stderr logging as-is for now; do not build a custom log pipeline first.
- [x] Add release/version, environment, and service resource attributes to every export.
- [x] Add app-level span attributes for the most important request dimensions:
  - route
  - authenticated user id when safe
  - course id when relevant
  - AI model name when relevant
  - content type / feature area
- [ ] Create explicit spans around:
  - course creation orchestration
  - self-assessment generation
  - LLM course generation
  - persistence step / DB write boundary
  - document upload / processing

### Backend Logs

- [ ] Keep structured backend logs in JSON-ish form and include:
  - `service`
  - `env`
  - `release`
  - `route`
  - `user_id` where safe
  - `course_id` where relevant
  - stable error code / event name
- [x] Do not build a separate log shipper in phase 1.
- [x] Revisit Grafana Alloy or Google Cloud logs ingestion only after traces, RUM, and synthetics are live.

### Backend Dashboard + Alerts

- [ ] Create an `api-prod` dashboard showing:
  - request rate
  - error rate
  - p50 / p95 / p99 latency
  - top failing routes
  - course-generation latency
  - DB-related error count
  - AI-call latency
- [ ] Alert on:
  - any spike in `POST /api/v1/courses/` failures
  - elevated 5xx rate
  - latency spike on course generation
  - repeated DB write failures / structured validation failures

## Phase 1: Synthetic Monitoring

### Why

- [x] Synthetic monitoring is the cleanest way to learn about user-facing failures before users report them.

### Checks To Add First

- [x] Browser check: landing page loads.
- [x] Browser check: auth page loads.
- [ ] Browser check: signup -> verify -> login happy path in staging.
- [ ] Browser check: login -> create course happy path in staging.
- [ ] Browser check: login -> self-assessment -> create course in staging.
- [x] API check: `GET /api/v1/auth/options`
- [x] API check: `GET /api/v1/assistant/models`

### Alerts

- [x] Page alert if any critical browser journey fails 2 runs in a row.
- [x] Page alert if median synthetic journey time regresses badly.

## Phase 1: Cloudflare / Cloud Run / Neon Specific Decisions

### Cloudflare

- [x] Treat Cloudflare as delivery/security infrastructure, not the first observability source.
- [x] Do not add Cloudflare Workers integration unless Talimio starts using Workers/Pages Functions meaningfully.
- [x] Do not add Cloudflare zone metrics integration in phase 1 unless already on a qualifying Cloudflare plan and there is a concrete CDN/WAF question to answer.

### Cloud Run

- [x] Keep Cloud Run as the deployment target.
- [x] Export backend telemetry directly from the app for phase 1.
- [x] Keep Google Cloud Logging/Monitoring available as the safety net while Grafana becomes the main pane of glass.

### Neon

- [x] Do not add Neon-specific observability tooling in phase 1.
- [x] Detect DB pain first through request traces, DB failure logs, and route-level alerts.
- [x] Revisit dedicated Postgres dashboards only if DB tuning becomes a repeated operational issue.

## Phase 2: Tighten the Stack Only If Needed

- [ ] Add **Grafana Alloy** only if one of these becomes true:
  - we need telemetry routing to multiple backends
  - we need buffering / retry outside the app
  - we need centralized redaction / enrichment
  - we want Cloudflare / GCP / app telemetry normalized in one collector
- [ ] Add **Google Cloud integration** to Grafana Cloud if we want deeper Cloud Run / GCP infra views directly in Grafana.
- [ ] Add **Cloudflare integration** only if CDN/WAF/rate-limit visibility becomes operationally important.
- [ ] Add **Grafana AI Observability** later if prompt/tool/model tracing becomes the next bottleneck.

## Phase 3: LLM Observability with Langfuse

### Why

- [ ] Add LLM observability only after Grafana dashboards, alerts, frontend observability, backend traces, and synthetic checks are already stable.
      Reason: Talimio should first answer "is the product broken?" before adding a second observability surface for prompt/tool/model internals.
- [ ] Use **Langfuse**, not Phoenix, if we add a dedicated LLM observability layer on top of the Grafana stack.
      Reason: Langfuse is the cleaner fit for a Grafana-first, OTel-first stack because it is OTel-native and is documented to coexist with an existing OpenTelemetry/APM setup rather than replacing it.

### Architecture

- [ ] Keep **Grafana Cloud** as the primary pane of glass for whole-app health, alerts, RUM, route/request failures, and non-LLM backend traces.
- [ ] Add **Langfuse** only as the LLM-specific layer for:
  - generations
  - tool calls
  - prompt versions
  - token usage
  - cost
  - scores / evals
- [ ] Use the **OTEL-native Langfuse path**, not the legacy ingestion API.
      Recommendation: use the current OTLP endpoint and OpenTelemetry-native SDK/integration path documented by Langfuse.
- [ ] Use **OTLP HTTP/protobuf** for Langfuse export, not gRPC.
      Note: Langfuse documents OTLP HTTP/protobuf support and explicitly does not support gRPC on the OTLP ingestion endpoint.
- [ ] Reuse the existing **OpenTelemetry / W3C trace context** so every generation/tool span stays correlated with the surrounding FastAPI request trace.
- [ ] Do not add a second Talimio-specific tracing abstraction.
      Recommendation: instrument inside the existing LLM call path and existing domain wrappers only.

### Phase 3A: Tracing First, No Prompt Migration Yet

- [ ] Keep the current Grafana OTLP export path exactly as-is.
- [ ] Add Langfuse in the backend only; do not add a separate frontend LLM observability SDK.
- [ ] Start with the existing **LiteLLM** integration path instead of custom wrappers.
      Recommendation: use Langfuse's current LiteLLM OTEL integration and attach metadata on the existing completion calls.
- [ ] Configure Langfuse trace export with the current OTLP traces endpoint:
  - Langfuse Cloud US: `https://us.cloud.langfuse.com/api/public/otel/v1/traces`
  - Langfuse Cloud EU: `https://cloud.langfuse.com/api/public/otel/v1/traces`
  - Self-hosted: `https://<langfuse-host>/api/public/otel/v1/traces`
- [ ] Configure transport/auth exactly once via env:
  - `OTEL_EXPORTER_OTLP_TRACES_PROTOCOL=http/protobuf`
  - `OTEL_EXPORTER_OTLP_TRACES_HEADERS=Authorization=Basic <base64(public:secret)>`
- [ ] Keep the backend-side implementation low-abstraction:
  - use the existing request trace
  - attach Langfuse/LiteLLM metadata at the LLM call site
  - do not introduce a custom exporter wrapper or Talimio-specific trace DSL
- [ ] Record these fields on every production generation where available:
  - `generation_name`
  - `trace_id`
  - `session_id`
  - `tags`
  - model name
  - provider name
  - token counts
  - cost
  - tool names
  - course id / user id only when safe
- [ ] Add explicit generation/tool spans for:
  - course generation
  - self-assessment generation
  - retrieval step
  - tool execution
  - final persistence boundary
- [ ] Do not send every backend span to Langfuse by default.
      Goal: Grafana keeps full app traces; Langfuse receives the LLM-relevant observations.

### Phase 3B: Prompt Versioning Only After Traces Are Useful

- [ ] Do not migrate prompts into Langfuse Prompt Management in the same step as initial tracing.
- [ ] After tracing is stable, move only the high-value prompts first:
  - course generation system prompt
  - self-assessment prompt
  - retrieval / synthesis prompt
- [ ] Link the executed prompt version to the generation trace.
      Goal: Langfuse should answer which prompt version was active for a bad output or regression.
- [ ] Keep prompt rollout simple:
  - one named prompt per use case
  - versioned revisions in Langfuse
  - no local prompt registry abstraction on top

### Phase 3C: Scores / Evals After Prompt Versioning

- [ ] Add scores/evals only after prompt-linked traces are already flowing.
- [ ] Start with a very small set of production-useful scores:
  - output accepted / rejected
  - hallucination suspected
  - tool failure
  - user retry after answer
  - generation too slow
- [ ] Prefer attaching scores directly to traces/generations instead of building a separate evaluation service first.

### Decision Gates

- [ ] Add Langfuse only when at least one of these becomes true:
  - prompt failures are hard to debug from Grafana traces alone
  - we need prompt/version comparison across releases
  - we need token/cost visibility per feature or model
  - we need evals/scoring on production traces
  - agent/tool behavior becomes a repeated debugging bottleneck

### Success Criteria

- [ ] One linked flow shows:
  - frontend action in Grafana
  - backend request trace in Grafana
  - nested LLM trace in Langfuse
  - failed tool/model/persistence step with enough context to debug quickly
- [ ] We can answer:
  - which prompt version regressed
  - which model/provider is slow or expensive
  - which tool call failed
  - which user-visible feature is driving token and cost growth
- [ ] The implementation stays low-abstraction:
  - no second collector added just for phase 3
  - no custom trace wrapper layer
  - no legacy Langfuse ingestion API

## Immediate Success Criteria

- [ ] One Grafana dashboard answers:
  - Is prod broken right now?
  - Is the frontend broken or the backend broken?
  - Which route is failing?
  - Which release introduced it?
- [ ] One alert wakes us up for:
  - course creation failures
  - auth flow failures
  - major frontend error spikes
  - synthetic journey failures
- [ ] One trace lets us follow:
  - browser action
  - API request
  - AI generation span
  - persistence failure

## Recommended First Implementation Order

- [ ] 1. Create Grafana Cloud stack
- [ ] 2. Add Faro to frontend
- [ ] 3. Upload frontend source maps
- [ ] 4. Add backend OTel traces + metrics direct to Grafana Cloud
- [ ] 5. Create `web-prod` and `api-prod` dashboards
- [ ] 6. Create critical alerts
- [ ] 7. Add browser synthetic checks for create-course flow
- [ ] 8. Only then decide whether Alloy, Cloudflare integration, or AI observability are actually needed
- [ ] 9. If prompt/tool/model visibility becomes the next bottleneck, add Langfuse as the dedicated LLM observability layer

## Official References

- [ ] Grafana Cloud docs: https://grafana.com/docs/grafana-cloud/
- [ ] Grafana Frontend Observability overview: https://grafana.com/docs/grafana-cloud/monitor-applications/frontend-observability/introduction/
- [ ] Grafana Frontend Observability architecture: https://grafana.com/docs/grafana-cloud/monitor-applications/frontend-observability/introduction/how-it-works/
- [ ] Grafana React instrumentation quickstart: https://grafana.com/docs/grafana-cloud/monitor-applications/frontend-observability/get-started/instrument-react/
- [ ] Grafana Faro source maps / bundlers: https://grafana.com/docs/grafana-cloud/monitor-applications/frontend-observability/configure/sourcemap-uploads/
- [ ] Grafana Frontend Observability alerting: https://grafana.com/docs/grafana-cloud/monitor-applications/frontend-observability/create-alerts/alerting/
- [ ] Grafana OTLP ingestion: https://grafana.com/docs/grafana-cloud/send-data/otlp/
- [ ] Grafana Alloy recommendation / setup: https://grafana.com/docs/opentelemetry/collector/grafana-alloy/
- [ ] Grafana Application Observability instrumentation: https://grafana.com/docs/opentelemetry/instrument/
- [ ] Grafana Synthetic Monitoring docs: https://grafana.com/docs/grafana-cloud/testing/synthetic-monitoring/
- [ ] k6 browser checks in Synthetic Monitoring: https://grafana.com/whats-new/2025-05-01-k6-browser-checks-in-synthetic-monitoring-are-generally-available/
- [ ] Grafana Cloudflare Workers integration: https://grafana.com/docs/grafana-cloud/monitor-infrastructure/integrations/integration-reference/integration-cloudflare-workers/
- [ ] Grafana Cloudflare integration: https://grafana.com/docs/grafana-cloud/monitor-infrastructure/integrations/integration-reference/integration-cloudflare/
- [ ] Grafana Google Cloud observability: https://grafana.com/docs/grafana-cloud/monitor-infrastructure/monitor-cloud-provider/gcp/
- [ ] Google Cloud Run observability: https://cloud.google.com/run/docs/monitoring
- [ ] OpenTelemetry Python instrumentation: https://opentelemetry.io/docs/languages/python/instrumentation/
- [ ] OpenTelemetry Python logs note: https://opentelemetry.io/docs/languages/python/exporters/
