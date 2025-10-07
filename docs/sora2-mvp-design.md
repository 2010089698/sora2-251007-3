# Sora2 Video Generation & Playback MVP Design

## 1. Goal & Scope
- Provide a browser-based MVP that lets users describe a video, submit the prompt to OpenAI's Sora2 video generation API, monitor job status, and play the resulting video once ready.
- Support authenticated access, job persistence, and minimal observability to debug failures.
- Optimize for rapid prototyping while keeping the architecture extensible for future features (prompt templates, collaboration, etc.).

## 2. User Stories
1. **Prompt Submission:** As an authenticated creator, I want to describe the desired video and trigger generation so that I can produce new content with Sora2.
2. **Generation Status:** As a creator, I want to see the progress and any errors from the Sora2 job so that I know when the video is ready or needs attention.
3. **Playback & Download:** As a creator, I want to stream or download the generated video so that I can review and share it.
4. **Prompt History (Stretch):** As a creator, I want to revisit my recent prompts and outputs to reuse or iterate on them.

## 3. High-Level Architecture
```
+-----------------+        +---------------------+        +---------------------+
|  React SPA (UI) | <----> |  BFF / API Gateway  | <----> |  Worker & Sora2 API |
+-----------------+        +---------------------+        +---------------------+
        |                           |                              |
        | 1. Prompt submission      | 2. Queue job + persist       | 3. Poll Sora2 jobs
        | 4. Playback request       | 5. Serve signed URLs         | 6. Store video in object store
```

### 3.1 Frontend (React + Vite or Next.js CSR)
- Components: PromptForm, JobStatusList, VideoPlayer.
- Uses REST endpoints exposed by the backend to create jobs, poll job status, and fetch signed playback URLs.
- Minimal state management with React Query for data fetching + caching.

### 3.2 Backend (Node.js / Express BFF)
- Handles authentication (OpenID Connect via Auth0/Clerk) and issues session JWT cookies.
- Provides REST endpoints:
  - `POST /api/videos`: create generation job by forwarding prompt to OpenAI Videos API.
  - `GET /api/videos/:jobId`: returns job metadata and latest status (cached in DB).
  - `GET /api/videos/:jobId/media`: returns signed URL for playback from object storage (Cloudflare R2/S3).
- Stores job records and prompt metadata in PostgreSQL via Prisma ORM.
- Pushes long-running processing to a lightweight queue (BullMQ + Redis) to poll Sora2 job status asynchronously.

### 3.3 Worker Service
- Dequeues pending jobs, calls Sora2 status endpoint, updates DB, and downloads completed assets to object storage.
- Cleans up failed jobs and surfaces errors to the UI.

### 3.4 Storage
- PostgreSQL: jobs table, assets table, users table.
- Object storage (S3-compatible) for raw video and thumbnail files.

## 4. Integration with OpenAI Videos API

### 4.1 Video Creation
- Use `POST https://api.openai.com/v1/videos` with model `"gpt-4.1-preview"` or `"gpt-4o-mini-translation"` (replace with relevant Sora2 model once published).
- Payload structure:
```json
{
  "model": "sora-1.0",
  "prompt": "Detailed natural language description of the video",
  "size": "1920x1080",
  "duration": 8,
  "format": "mp4"
}
```
- Backend sets `Authorization: Bearer <OPENAI_API_KEY>` and optionally `OpenAI-Beta: video-generation=2` headers per docs.
- Response includes a job `id` and initial `status` (e.g., `queued`). Persist this `id` to track the job.

### 4.2 Job Polling
- Worker repeatedly calls `GET /v1/videos/{job_id}` to retrieve updated status (`queued`, `processing`, `completed`, `failed`).
- When `status === "completed"`, response contains media asset URLs (e.g., `result.assets[0].download_url`).
- Worker downloads the file, stores it in object storage, and records the storage key + metadata (duration, resolution, size).

### 4.3 Streaming
- For immediate playback without downloading, use the streaming URL returned by OpenAI if available, or serve the file via signed S3 URL.
- The backend endpoint `/api/videos/:jobId/media` generates a signed URL that the frontend uses in the `<video>` tag.

### 4.4 Error Handling
- If status is `failed`, the worker updates job record with `error_message` from the API response.
- Frontend displays user-friendly error with option to retry.

## 5. Data Model (Simplified)
| Table | Fields |
|-------|--------|
| `users` | `id`, `auth_provider_id`, `email`, `created_at` |
| `video_jobs` | `id`, `user_id`, `prompt`, `sora_job_id`, `status`, `error_message`, `created_at`, `updated_at` |
| `video_assets` | `id`, `job_id`, `storage_key`, `playback_url`, `duration`, `resolution`, `file_size`, `created_at` |

## 6. API Surface (Backend)
- `POST /api/videos`
  - Body: `{ prompt: string, size?: string, duration?: number, format?: string }`
  - Response: `{ jobId: string, status: 'queued' }`
- `GET /api/videos`
  - Query: pagination options; returns list of jobs for current user.
- `GET /api/videos/:jobId`
  - Response: `{ jobId, prompt, status, errorMessage?, asset?: {...} }`
- `GET /api/videos/:jobId/media`
  - Response: `{ url: string, expiresAt: ISODate }`
- `POST /api/videos/:jobId/retry`
  - Re-enqueues a failed job.

## 7. Frontend UX Flow
1. User logs in via Auth0; frontend receives session cookie.
2. PromptForm collects text prompt + optional duration/resolution.
3. On submit, call `POST /api/videos` and show optimistic job card (status `queued`).
4. React Query polls `GET /api/videos/:jobId` every few seconds until status is `completed` or `failed`.
5. When completed, VideoPlayer component displays `<video src={signedUrl} controls />` fetched from `/api/videos/:jobId/media`.
6. Allow download via `<a href={signedUrl} download>`.

## 8. Security & Compliance
- Store OpenAI API key in server-side secrets manager (e.g., Doppler, AWS Secrets Manager).
- Enforce per-user access controls; ensure jobs/assets are scoped by `user_id`.
- Generate short-lived signed URLs to prevent unauthorized sharing.
- Log requests and responses (excluding sensitive data) for monitoring.
- Rate-limit prompt submissions to prevent abuse.

## 9. Observability & Operations
- Centralized logging (Winston + Datadog).
- Metrics: job counts by status, average time-to-complete, API error rates.
- Alerts on high failure rates or long queue times.
- Feature flags for experimental prompt templates or model parameters.

## 10. Future Enhancements
- Collaborative projects with shared job lists.
- Prompt presets and AI-assisted prompt refinement.
- Webhooks from OpenAI Videos API (if available) to replace polling.
- Integration with editing tools for trimming or captioning.

## 11. Development Plan
1. Scaffold frontend (React + Vite) and backend (Express) with basic auth stub.
2. Implement `POST /api/videos` calling Sora2 API and persisting job.
3. Add worker polling + storage integration.
4. Build frontend job list & video playback UI.
5. Harden security, logging, and add retry flows.

## 12. Testing Strategy
- Unit tests for API client wrappers (mock OpenAI responses).
- Integration tests for backend endpoints using Supertest with mocked queue/storage.
- Cypress E2E test that submits a prompt and simulates job completion.

## 13. Deployment
- Host frontend on Vercel/Netlify; backend + worker on Fly.io or Render.
- Use managed PostgreSQL (Neon/Supabase) and Redis (Upstash) for simplicity.
- Configure CI/CD pipeline (GitHub Actions) with lint/test workflows.

