require('dotenv').config();
const express = require('express');
const path = require('path');
const db = require('./db');
const openaiClient = require('./openaiClient');
const { startPolling } = require('./poller');

const app = express();
const port = process.env.PORT || 8000;

app.use(express.json());
app.use(express.static(path.join(__dirname, '..', 'frontend')));

app.get('/api/videos', (req, res) => {
  const jobs = db.listJobs().map(stripSensitiveFields);
  res.json({ jobs });
});

app.get('/api/videos/:id', (req, res) => {
  const job = db.getJob(req.params.id);
  if (!job) {
    res.status(404).json({ error: 'Job not found' });
    return;
  }
  res.json({ job: stripSensitiveFields(job) });
});

app.post('/api/videos', async (req, res) => {
  const { prompt, aspect_ratio, duration, format } = req.body || {};
  if (!prompt || typeof prompt !== 'string') {
    res.status(400).json({ error: 'prompt is required' });
    return;
  }

  try {
    const remoteJob = await openaiClient.createVideoJob({ prompt, aspect_ratio, duration, format });
    if (!remoteJob?.id) {
      throw new Error('Invalid response from OpenAI Videos API');
    }

    const jobRecord = db.insertJob({
      prompt,
      aspect_ratio,
      duration,
      format,
      sora_job_id: remoteJob.id,
      status: remoteJob.status || 'queued',
      content_variant: remoteJob.content_variant || null,
      content_ready_at: remoteJob.status === 'completed' ? new Date().toISOString() : null,
      content_token: remoteJob.content_token || null,
      content_token_expires_at: remoteJob.content_token_expires_at || null,
      error_message: remoteJob.error_message || null,
    });

    res.status(201).json({ job: stripSensitiveFields(jobRecord) });
  } catch (error) {
    console.error('Failed to create video job:', error.message);
    res.status(502).json({ error: error.message });
  }
});

app.get('/api/videos/:id/media', async (req, res) => {
  const job = db.getJob(req.params.id);
  if (!job) {
    res.status(404).json({ error: 'Job not found' });
    return;
  }
  if (job.status !== 'completed') {
    res.status(409).json({ error: 'Video is not ready' });
    return;
  }

  const requestedVariant = req.query.variant;
  const variant = requestedVariant || job.content_variant || 'source';
  try {
    const remoteResponse = await openaiClient.streamVideoContent(job.sora_job_id, {
      variant,
      token: job.content_token,
    });
    res.setHeader('Content-Type', remoteResponse.headers.get('content-type') || 'video/mp4');
    const contentLength = remoteResponse.headers.get('content-length');
    if (contentLength) {
      res.setHeader('Content-Length', contentLength);
    }
    remoteResponse.body.pipe(res);
  } catch (error) {
    console.error('Failed to proxy content:', error.message);
    res.status(502).json({ error: 'Failed to fetch video content' });
  }
});

app.get('/api/videos/:id/stream', (req, res) => {
  res.status(410).json({ error: 'This endpoint has moved to /api/videos/:id/media' });
});

app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, '..', 'frontend', 'index.html'));
});

app.listen(port, () => {
  console.log(`Server listening on http://localhost:${port}`);
});

startPolling({ intervalMs: Number(process.env.POLL_INTERVAL_MS) || 10000 });

function stripSensitiveFields(job) {
  if (!job) return job;
  const { content_token, content_token_expires_at, ...rest } = job;
  return rest;
}
