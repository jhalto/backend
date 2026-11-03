export async function request(path, { token, ...options } = {}) {
  const headers = {
    ...(options.body ? { 'Content-Type': 'application/json' } : {}),
    ...(token ? { Authorization: `Token ${token}` } : {}),
    ...(options.headers || {}),
  };
  const response = await fetch(path, { ...options, headers });
  const body = response.status === 204 ? null : await response.json().catch(() => ({}));
  if (!response.ok) {
    const messages = Object.values(body || {}).flatMap(value => Array.isArray(value) ? value : [value]);
    const error = new Error(body?.detail || messages.join(' ') || 'Something went wrong.');
    error.status = response.status;
    throw error;
  }
  return body;
}
