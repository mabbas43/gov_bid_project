# Deployment

Nothing here has been deployed. The backend goes on Render or Railway with a persistent disk, and the
frontend goes on Vercel.

## Backend (Render)
1. Create a Blueprint from this repo. It picks up `render.yaml`.
2. Set `DEEPSEEK_API_KEY`, and set `CORS_ORIGINS` to your Vercel URL.
3. Check that `https://<backend>/health` returns `{"status":"ok"}`.

## Backend (Railway)
1. Create a service from this repo with `RAILWAY_DOCKERFILE_PATH=backend/Dockerfile`.
2. Attach a volume mounted at `/data`.
3. Set the same variables. Railway supplies `PORT`, and the container reads it.

## Frontend (Vercel)
1. Import the repo and set **Root Directory** to `frontend`.
2. Set `NEXT_PUBLIC_API_URL` to the backend URL. It is compiled in, so redeploy after changing it.

## Environment variables

| Variable | Where | Required | Default | Purpose |
|---|---|---|---|---|
| `DEEPSEEK_API_KEY` | Backend | For live mode | none | DeepSeek key. `API_KEY` also works. |
| `DEEPSEEK_MODEL` | Backend | No | `deepseek-chat` | Model name |
| `DEEPSEEK_BASE_URL` | Backend | No | `https://api.deepseek.com` | API base URL |
| `DEMO_MODE` | Backend | No | `false` | Starting value. The UI toggle overrides it and is saved in the database. |
| `DEMO_STEP_DELAY_MS` | Backend | No | `500` | Pacing of the demo timeline |
| `CORS_ORIGINS` | Backend | Yes in production | `http://localhost:3010` | Comma-separated frontend origins |
| `DATA_DIR` | Backend | Set by the Dockerfile | `./data` | Database and workspaces |
| `LLM_TIMEOUT_S`, `LLM_MAX_RETRIES` | Backend | No | `60`, `2` | Model call limits |
| `DEEPSEEK_INPUT_USD_PER_M`, `DEEPSEEK_OUTPUT_USD_PER_M` | Backend | No | `0.27`, `1.10` | Cost estimate in `make eval`. Check against current pricing. |
| `NEXT_PUBLIC_API_URL` | Frontend | Yes | `http://localhost:8010` | Backend URL |

## Checklist

**Before exposing it publicly**
- [ ] **Add authentication.** The API has none. Anyone with the URL can spend your DeepSeek credit, flip
      demo mode, edit the company profile and download bid packs. Put it behind an auth proxy or a private
      network, or keep `DEMO_MODE=true` with no key set on any public demo.
- [ ] Set a spending limit on the DeepSeek key.
- [ ] Set `CORS_ORIGINS` to the exact frontend origin. Never use `*`.

**Backend**
- [ ] The disk is mounted at `/data`, and data survives a redeploy.
- [ ] Exactly one instance and one worker: SQLite and background runs are in-process.
- [ ] Runs in progress during a deploy are marked failed at startup. Avoid deploying during a demo.
- [ ] Your proxy does not buffer `/runs/{id}/stream`. The API sends `X-Accel-Buffering: no`.

**Data**
- [ ] Replace the sample company profile: registration numbers and past projects are placeholders.
- [ ] Back up `/data/tenderscout.db`.

**After deploying**
- [ ] `GET /health` responds.
- [ ] `GET /llm-ping` returns a reply (this spends a few tokens).
- [ ] A demo-mode run completes from the Run Agent page and the bid pack downloads.
- [ ] A live-mode run reaches PPRA. If it fell back, the first timeline step says so.
