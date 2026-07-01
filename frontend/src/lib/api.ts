/**
 * Typed fetch wrapper used by every TanStack Query hook.
 *
 * Reads the API base URL from `VITE_API_BASE_URL`; falls back to "" so the
 * Vite dev-server proxy in `vite.config.ts` handles routing during development.
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, detail: unknown, message?: string) {
    super(message ?? (typeof detail === "string" ? detail : `API error ${status}`));
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  // Skip JSON-encoding when the caller has already serialized the body.
  rawBody?: boolean;
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, rawBody, headers, ...rest } = options;

  const init: RequestInit = {
    ...rest,
    headers: {
      Accept: "application/json",
      ...(body !== undefined && !rawBody ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
    body:
      body === undefined
        ? undefined
        : rawBody
          ? (body as BodyInit)
          : JSON.stringify(body),
  };

  const response = await fetch(`${BASE_URL}${path}`, init);

  if (!response.ok) {
    let detail: unknown = response.statusText;
    try {
      const parsed = await response.json();
      detail = parsed?.detail ?? parsed;
    } catch {
      // Body wasn't JSON — stick with the status text.
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}
