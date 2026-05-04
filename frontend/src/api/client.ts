import type { ErrorDetail } from "./types";

export class ApiError extends Error {
  problem: string;
  cause: string;
  fix: string;

  constructor(detail: ErrorDetail) {
    super(detail.problem);
    this.name = "ApiError";
    this.problem = detail.problem;
    this.cause = detail.cause;
    this.fix = detail.fix;
  }
}

const BASE = "/api";

async function handleResponse<T>(response: Response): Promise<T> {
  if (response.ok) {
    return response.json() as Promise<T>;
  }

  const text = await response.text();
  try {
    const detail = JSON.parse(text) as ErrorDetail;
    throw new ApiError(detail);
  } catch (err) {
    if (err instanceof ApiError) throw err;
    throw new ApiError({
      problem: `Request failed (${response.status})`,
      cause: response.statusText,
      fix: "Please try again later.",
    });
  }
}

export function safeHref(url: string): string {
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      return "#";
    }
    return url;
  } catch {
    return "#";
  }
}

export async function apiGet<T>(
  path: string,
  params?: Record<string, string | number | boolean | undefined>,
): Promise<T> {
  const url = new URL(BASE + path, window.location.origin);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== "") {
        url.searchParams.set(key, String(value));
      }
    }
  }
  const response = await fetch(url);
  return handleResponse<T>(response);
}

export async function apiPatch<T>(
  path: string,
  params: Record<string, string>,
  body: unknown,
): Promise<T> {
  const url = new URL(BASE + path, window.location.origin);
  for (const [key, value] of Object.entries(params)) {
    url.searchParams.set(key, value);
  }
  const response = await fetch(url, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handleResponse<T>(response);
}

export async function apiPatchBody<T>(
  path: string,
  body: unknown,
): Promise<T> {
  const url = new URL(BASE + path, window.location.origin);
  const response = await fetch(url, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handleResponse<T>(response);
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const url = new URL(BASE + path, window.location.origin);
  const response = await fetch(url, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  return handleResponse<T>(response);
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  const url = new URL(BASE + path, window.location.origin);
  const response = await fetch(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handleResponse<T>(response);
}

export async function apiDelete(path: string): Promise<void> {
  const url = new URL(BASE + path, window.location.origin);
  const response = await fetch(url, { method: "DELETE" });
  if (!response.ok) {
    const text = await response.text();
    try {
      const detail = JSON.parse(text) as ErrorDetail;
      throw new ApiError(detail);
    } catch (err) {
      if (err instanceof ApiError) throw err;
      throw new ApiError({
        problem: `Delete failed (${response.status})`,
        cause: response.statusText,
        fix: "Please try again later.",
      });
    }
  }
}
