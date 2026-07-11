# Flowise Configuration

Flowise is the visual builder for reusable AI chains and agent flows. n8n should handle schedules, triggers, notifications, and cross-app automation. Flowise should handle reasoning chains, retrieval workflows, reusable prompts, and agentic pipelines.

## Environment

Set these values in `.env`:

```text
FLOWISE_URL=https://your-flowise-cloud-url
FLOWISE_API_KEY=your-flowise-api-key
LOCAL_FLOWISE_URL=http://localhost:3001
```

If you want to use the local Docker Flowise instance, leave `FLOWISE_URL` blank and run:

```powershell
docker compose up --build flowise
```

Local Flowise opens at `http://localhost:3001`.

## Recommended Flowise Chatflows

Create these chatflows first:

- `ai-ops-orchestrator`: turns current tasks, reports, and metrics into next actions.
- `revenue-idea-generator`: creates and scores passive/revenue-producing offers.
- `grant-research-assistant`: summarizes grant opportunities and fit.
- `content-engine`: turns research into posts, outlines, scripts, and product copy.
- `code-review-assistant`: reviews code/test output and produces fixes.

## API Bridge

The AI Operations API can call Flowise:

```text
GET  /integrations/flowise/health
POST /integrations/flowise/predict
```

Example body:

```json
{
  "chatflow_id": "your-chatflow-id",
  "question": "Create the top 5 revenue actions for today.",
  "override_config": {}
}
```

## Browser Setup

Since you are already logged in, use Chrome to create or import the chatflows in Flowise. After each chatflow is created, copy its chatflow ID into `.env` or a future `config/flowise_chatflows.yaml` mapping.

