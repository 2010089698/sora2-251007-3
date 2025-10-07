const API_BASE_URL = process.env.OPENAI_API_BASE_URL || 'https://api.openai.com/v1';
const DEFAULT_VIDEO_MODEL = 'sora-2';
const VIDEO_MODEL = process.env.OPENAI_VIDEO_MODEL || DEFAULT_VIDEO_MODEL;

function ensureApiKey() {
  const key = process.env.OPENAI_API_KEY;
  if (!key) {
    throw new Error('OPENAI_API_KEY is not set.');
  }
  return key;
}

function normalizeAssets(payload) {
  const outputs = Array.isArray(payload?.output)
    ? payload.output
    : Array.isArray(payload?.data)
    ? payload.data
    : Array.isArray(payload?.assets)
    ? payload.assets
    : [];
  return outputs
    .map((item) => {
      const sources = [
        item.preview_url,
        item.streaming_url,
        item.url,
        item.download_url,
      ].filter(Boolean);

      return {
        id: item.id || item.asset_id || item.file_id || null,
        format: item.format || item.mime_type || null,
        preview_url: item.preview_url || item.streaming_url || item.url || null,
        download_url: item.download_url || item.url || null,
        resolution: item.resolution || item.metadata?.resolution || null,
        duration_seconds: item.duration_seconds || item.duration || item.metadata?.duration_seconds || null,
        sources,
      };
    })
    .filter((asset) => asset.preview_url || asset.download_url);
}

function normalizeJobResponse(payload) {
  if (!payload) return null;
  return {
    id: payload.id,
    status: payload.status,
    error_message: payload.error?.message || null,
    seconds: payload.seconds || payload.duration || null,
    size: payload.size || payload.resolution || null,
    assets: normalizeAssets(payload),
  };
}

async function createVideoJob({ prompt, seconds, size }) {
  const apiKey = ensureApiKey();
  const body = {
    model: VIDEO_MODEL,
    prompt,
    seconds,
    size,
  };

  Object.keys(body).forEach((key) => {
    if (body[key] === undefined || body[key] === null) {
      delete body[key];
    }
  });

  const response = await fetch(`${API_BASE_URL}/videos`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
      'OpenAI-Beta': 'sora2=v1',
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || `Failed to create video job (${response.status})`);
  }

  const payload = await response.json();
  return normalizeJobResponse(payload);
}

async function retrieveVideoJob(jobId) {
  const apiKey = ensureApiKey();
  const response = await fetch(`${API_BASE_URL}/videos/${jobId}`, {
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'OpenAI-Beta': 'sora2=v1',
    },
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || `Failed to retrieve video job ${jobId} (${response.status})`);
  }

  const payload = await response.json();
  return normalizeJobResponse(payload);
}

async function fetchAssetStream(url) {
  const apiKey = ensureApiKey();
  const response = await fetch(url, {
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'OpenAI-Beta': 'sora2=v1',
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch asset (${response.status})`);
  }

  return response;
}

module.exports = {
  createVideoJob,
  retrieveVideoJob,
  fetchAssetStream,
};
