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

function normalizeVariants(payload) {
  const variants = Array.isArray(payload?.variants)
    ? payload.variants
    : Array.isArray(payload?.available_variants)
    ? payload.available_variants
    : [];

  return variants
    .map((variant) =>
      typeof variant === 'string'
        ? variant
        : variant?.name || variant?.id || null
    )
    .filter(Boolean);
}

function normalizeJobResponse(payload) {
  if (!payload) return null;
  return {
    id: payload.id,
    status: payload.status,
    error_message: payload.error?.message || null,
    seconds: payload.seconds || payload.duration || null,
    size: payload.size || payload.resolution || null,
    variants: normalizeVariants(payload),
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

function buildContentUrl(videoId, variant) {
  const url = new URL(`${API_BASE_URL}/videos/${videoId}/content`);
  if (variant) {
    url.searchParams.set('variant', variant);
  }
  return url.toString();
}

async function streamVideoContent(videoId, variant) {
  const apiKey = ensureApiKey();
  const url = buildContentUrl(videoId, variant);
  const response = await fetch(url, {
    headers: {
      Authorization: `Bearer ${apiKey}`,
      'OpenAI-Beta': 'sora2=v1',
    },
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || `Failed to fetch content for video ${videoId} (${response.status})`);
  }

  return response;
}

module.exports = {
  createVideoJob,
  retrieveVideoJob,
  streamVideoContent,
};
