/**
 * Minimal fetch wrapper for the Sourcebound backend API.
 *
 * Base URL comes from NEXT_PUBLIC_API_URL (see .env.local.example). Parses the
 * backend's standard error envelope { error: { code, message, request_id, details } }
 * into a typed ApiError so callers handle one shape everywhere.
 */

const BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"
).replace(/\/$/, "");

export const API_BASE_URL = BASE_URL;

export class ApiError extends Error {
  constructor(message, { status, code, requestId, details } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.details = details;
  }
}

export async function apiFetch(path, { method = "GET", body, headers, signal } = {}) {
  const url = `${BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;

  const res = await fetch(url, {
    method,
    headers: {
      Accept: "application/json",
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal,
  });

  const isJson = res.headers.get("content-type")?.includes("application/json");
  const payload = isJson ? await res.json().catch(() => null) : await res.text();

  if (!res.ok) {
    const envelope = isJson && payload && typeof payload === "object" ? payload.error : null;
    throw new ApiError(envelope?.message ?? `Request failed (${res.status})`, {
      status: res.status,
      code: envelope?.code,
      requestId: envelope?.request_id,
      details: envelope?.details,
    });
  }

  return payload;
}

/**
 * Multipart upload (FormData). Does NOT set Content-Type — the browser adds the
 * multipart boundary. Parses the same error envelope as apiFetch.
 */
export async function apiUpload(path, formData, { signal } = {}) {
  const url = `${BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { Accept: "application/json" },
    body: formData,
    signal,
  });

  const isJson = res.headers.get("content-type")?.includes("application/json");
  const payload = isJson ? await res.json().catch(() => null) : await res.text();

  if (!res.ok) {
    const envelope = isJson && payload && typeof payload === "object" ? payload.error : null;
    throw new ApiError(envelope?.message ?? `Upload failed (${res.status})`, {
      status: res.status,
      code: envelope?.code,
      requestId: envelope?.request_id,
      details: envelope?.details,
    });
  }
  return payload;
}

export const api = {
  get: (path, opts) => apiFetch(path, { ...opts, method: "GET" }),
  post: (path, body, opts) => apiFetch(path, { ...opts, method: "POST", body }),
  patch: (path, body, opts) => apiFetch(path, { ...opts, method: "PATCH", body }),
  del: (path, opts) => apiFetch(path, { ...opts, method: "DELETE" }),
  upload: (path, formData, opts) => apiUpload(path, formData, opts),
};
