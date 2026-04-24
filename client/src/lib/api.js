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
