export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

export async function fetchTree() {
  let resp;
  try {
    resp = await fetch('/api/tree');
  } catch {
    throw new ApiError(0, 'Cannot reach the backend. Is the server running?');
  }
  if (!resp.ok) throw new ApiError(resp.status, `Failed to fetch tree: ${resp.status}`);
  return resp.json();
}

export async function fetchClass(courseSlug, moduleSlug, classSlug) {
  let resp;
  try {
    resp = await fetch(`/api/class/${courseSlug}/${moduleSlug}/${classSlug}`);
  } catch {
    throw new ApiError(0, 'Cannot reach the backend. Is the server running?');
  }
  if (resp.status === 404) {
    throw new ApiError(404, 'Lesson not found');
  }
  if (!resp.ok) throw new ApiError(resp.status, `Failed to fetch class: ${resp.status}`);
  return resp.json();
}

export async function prepareStream(mediaUrl, signal) {
  const resp = await fetch('/api/stream/prepare', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ media_url: mediaUrl }),
    signal,
  });
  if (!resp.ok) return null;
  return resp.json();
}

export async function heartbeatStream(id, time) {
  try {
    const resp = await fetch(`/api/stream/${id}/heartbeat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ time }),
    });
    return resp.ok;
  } catch {
    return true; // network error, not a 404 — don't trigger recovery
  }
}

// Backward compatibility aliases
export const prepareHls = prepareStream;
export const heartbeatHls = heartbeatStream;
