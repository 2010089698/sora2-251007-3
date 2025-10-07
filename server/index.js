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
  const jobs = db.listJobs();
  res.json({ jobs });
});

app.get('/api/videos/:id', (req, res) => {
  const job = db.getJob(req.params.id);
  if (!job) {
    res.status(404).json({ error: 'Job not found' });
    return;
  }
  res.json({ job });
});

app.post('/api/videos', async (req, res) => {
  const { prompt, seconds, size } = req.body || {};
  if (!prompt || typeof prompt !== 'string') {
    res.status(400).json({ error: 'prompt is required' });
    return;
  }

  try {
    const remoteJob = await openaiClient.createVideoJob({ prompt, seconds, size });
    if (!remoteJob?.id) {
      throw new Error('Invalid response from OpenAI Videos API');
    }

    const parsedSeconds = Number(seconds);
    const sanitizedSeconds = Number.isFinite(parsedSeconds) ? parsedSeconds : null;
    const remoteSeconds = Number(remoteJob.seconds);
    const remoteSecondsValue = Number.isFinite(remoteSeconds) ? remoteSeconds : null;
    const resolvedSeconds = sanitizedSeconds || remoteSecondsValue;
    const resolvedSize = size || remoteJob.size || null;

    const jobRecord = db.insertJob({
      prompt,
      seconds: resolvedSeconds,
      size: resolvedSize,
      sora_job_id: remoteJob.id,
      status: remoteJob.status || 'queued',
      variants: remoteJob.variants || [],
      error_message: remoteJob.error_message || null,
    });

    res.status(201).json({ job: jobRecord });
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

  const variants = Array.isArray(job.variants) ? job.variants : [];
  const requestedVariant = typeof req.query.variant === 'string' ? req.query.variant : undefined;
  const variantToUse = requestedVariant || variants[0];

  if (!variantToUse) {
    res.status(404).json({ error: 'Variant not available yet' });
    return;
  }

  try {
    const upstream = await openaiClient.streamVideoContent(job.sora_job_id, variantToUse);
    const contentType = upstream.headers.get('content-type') || 'application/octet-stream';
    res.setHeader('Content-Type', contentType);

    const contentDisposition = upstream.headers.get('content-disposition');
    if (contentDisposition) {
      res.setHeader('Content-Disposition', contentDisposition);
    }

    const contentLength = upstream.headers.get('content-length');
    if (contentLength) {
      res.setHeader('Content-Length', contentLength);
    }

    upstream.body.pipe(res);
  } catch (error) {
    console.error('Failed to proxy video content:', error.message);
    res.status(502).json({ error: 'Failed to fetch video content' });
  }
});

app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, '..', 'frontend', 'index.html'));
});

app.listen(port, () => {
  console.log(`Server listening on http://localhost:${port}`);
});

startPolling({ intervalMs: Number(process.env.POLL_INTERVAL_MS) || 10000 });
