const API_BASE_URL = process.env.OPENAI_API_BASE_URL || 'https://api.openai.com/v1';

function ensureApiKey() {
  const key = process.env.OPENAI_API_KEY;
  if (!key) {
    throw new Error('OPENAI_API_KEY is not set.');
  }
  return key;
}

function extractContentMetadata(payload = {}) {
  const root = payload.result || payload;
  const variants = Array.isArray(root.content_variants)
    ? root.content_variants
    : Array.isArray(root.variants)
    ? root.variants
    : [];
  const defaultVariant =
    root.default_variant || root.variant || (variants.length ? variants[0] : null);
  return {
    content_variant: defaultVariant || null,
    content_token: root.content_token || root.download_token || null,
    content_token_expires_at:
      root.content_token_expires_at || root.token_expires_at || null,
  };
}

function normalizeJobResponse(payload) {
  if (!payload) return null;
  const metadata = extractContentMetadata(payload);
  return {
    id: payload.id,
    status: payload.status,
    error_message: payload.error?.message || null,
    content_variant: metadata.content_variant,
    content_token: metadata.content_token,
    content_token_expires_at: metadata.content_token_expires_at,
  };
}

async function createVideoJob({ prompt, aspect_ratio, duration, format }) {
  const apiKey = ensureApiKey();
  const body = {
    model: 'gpt-video-1',
    prompt,
    aspect_ratio,
    duration,
    format,
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

async function streamVideoContent(jobId, { variant, token } = {}) {
  const apiKey = ensureApiKey();
  const url = new URL(`${API_BASE_URL}/videos/${jobId}/content`);
  if (variant) {
    url.searchParams.set('variant', variant);
  }
  if (token) {
    url.searchParams.set('token', token);
  }

  const response = await fetch(url, {
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'OpenAI-Beta': 'sora2=v1',
    },
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || `Failed to stream video content (${response.status})`);
  }

  return response;
}

module.exports = {
  createVideoJob,
  retrieveVideoJob,
  streamVideoContent,
};
