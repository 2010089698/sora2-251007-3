# Sora2 Video Generation & Playback MVP Design (Node.js Edition)

## 1. Goal & Scope
- Provide a lightweight browser experience that lets a user describe a video, submit the prompt to OpenAI's Sora2 Videos API, monitor progress, and watch the final output.
- Minimize moving parts: a single Express server plus static frontend assets.
- Keep the codebase ready for future enhancements such as authentication or multi-user support.

## 2. User Stories
1. **Prompt Submission:** As a creator, I want to submit a text prompt so that Sora2 can generate a new video for me.
2. **Generation Status:** As a creator, I want to see whether my video is queued, processing, completed, or failed.
3. **Playback & Download:** As a creator, I want to stream or download the finished video in my browser.
4. **History Review (Stretch):** As a creator, I want to revisit my recent prompts and results for iteration.

## 3. High-Level Architecture
```
+----------------------+           +---------------------------+
|  Static Frontend UI  | <------> |  Express API + Poller     |
| (Vanilla HTML/JS/CSS)|           |  (Node.js + SQLite)       |
+----------------------+           +---------------------------+
                                               |
                                               v
                                     +--------------------+
                                     |  OpenAI Videos API |
                                     +--------------------+
```

- The Express app serves both the REST API and the static frontend assets.
- Jobs are stored in SQLite for persistence across restarts.
- A background timer within the same Node.js process polls OpenAI for job updates.

## 4. Backend Components (Express)
- **Routes**
  - `POST /api/videos` — validate prompt, forward to OpenAI Videos API (`POST /v1/videos`), persist job metadata.
  - `GET /api/videos` — return all stored jobs ordered by creation date.
  - `GET /api/videos/:id` — fetch a single job record.
  - `GET /api/videos/:id/media` — proxy OpenAI's `/videos/{job_id}/content?variant=...` stream after completion.
- **Persistence**
  - SQLite via `better-sqlite3` stores job fields: prompt, Sora job ID, status, content metadata (variant/token expiry), error message, timestamps.
- **OpenAI Integration**
  - Uses the Videos API with headers `Authorization: Bearer <OPENAI_API_KEY>` and `OpenAI-Beta: sora2=v1`.
  - Once a job reaches `completed`, the backend no longer stores static asset URLs. Instead it proxies playback requests to OpenAI's `GET /videos/{id}/content` endpoint, forwarding the desired `variant` (for example `source`, `preview`, etc.).
  - Any transient download credentials (such as short-lived tokens or expiry timestamps) are kept server-side so the browser always talks to the local `/api/videos/{id}/media` endpoint.
- **Polling Loop**
  - `setInterval` every 10s queries pending jobs (`status` not in `completed/failed/cancelled`).
  - Updates local records when OpenAI reports status changes or when video content becomes streamable.

## 5. Frontend Components (Vanilla JS)
- **Prompt Form** — collects prompt text, aspect ratio, optional duration, and format.
- **Job List** — polls `GET /api/videos` every 10s, showing status badges, metadata, and inline `<video>` playback once `/videos/{id}/content` is available.
- **Feedback Messages** — notifies users about submission success/failure.

## 6. Data Model
| Field | Description |
|-------|-------------|
| `id` | Local UUID for the job card displayed in the UI. |
| `prompt` | Submitted text prompt. |
| `aspect_ratio` | Optional aspect ratio passed to OpenAI. |
| `duration` | Optional duration in seconds. |
| `format` | Preferred output format (e.g., `mp4`). |
| `sora_job_id` | Identifier returned by OpenAI. |
| `status` | `queued`, `in_progress`, `completed`, `failed`, etc. |
| `content_variant` | The default variant name used when proxying `/videos/{id}/content`. |
| `content_ready_at` | Timestamp recorded when streaming becomes available. |
| `content_token` / `content_token_expires_at` | (Server-side only) Optional temporary credentials returned by OpenAI. |
| `error_message` | Failure reason if reported by the API. |
| `created_at` / `updated_at` | ISO timestamps for auditing. |

## 7. API Payloads
- **Create Video Request**
```json
POST /api/videos
{
  "prompt": "A cozy campfire at night in the forest",
  "aspect_ratio": "16:9",
  "duration": 8,
  "format": "mp4"
}
```
- **Create Video Response**
```json
201 Created
{
    "job": {
      "id": "local-uuid",
      "prompt": "A cozy campfire...",
      "status": "queued",
      "sora_job_id": "job-abc123"
    }
}
```
- **Job Listing**
```json
GET /api/videos
{
  "jobs": [
    {
      "id": "local-uuid",
      "status": "completed",
      "content_variant": "source",
      "content_ready_at": "2024-03-15T12:34:56Z"
    }
  ]
}
```

## 8. Error Handling & Observability
- Request validation ensures `prompt` is provided; other fields are optional.
- API errors from OpenAI are surfaced as 502 responses with message details.
- Poller logs failures to the console; production deployments can redirect logs to CloudWatch, Datadog, etc.

## 9. Deployment Considerations
- Single container image (Node.js 18) running the Express app is sufficient.
- Mount a persistent volume for `server/data/app.db`.
- Configure environment variables (`OPENAI_API_KEY`, optional overrides for polling interval or API base URL).
- Use a process manager (PM2, systemd) or platform auto-restart to keep the poller alive.

## 10. Roadmap Enhancements
- Replace polling with webhook callbacks if/when OpenAI provides them.
- Add user authentication and per-user job scoping.
- Persist video assets to an external object store and serve signed URLs.
- Add queue workers if polling or downloads become resource-intensive.
- Introduce integration tests using a mocked Videos API.
