import createClient, { type Middleware } from "openapi-fetch";

import type { paths } from "./schema";

/** Typed API client generated from the backend's OpenAPI schema (`npm run gen:api`).
 *  Paths, parameters and responses are type-checked against the real API. */
export const api = createClient<paths>({
  // Same origin as the app (Vite proxies /api to Django in development).
  baseUrl: window.location.origin,
  credentials: "same-origin",
});

function csrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match?.[1] ? decodeURIComponent(match[1]) : "";
}

// Django requires the CSRF token as a header on every write (DECISIONS #36).
const csrf: Middleware = {
  onRequest({ request }) {
    if (!["GET", "HEAD", "OPTIONS"].includes(request.method)) {
      request.headers.set("X-CSRFToken", csrfToken());
    }
    return request;
  },
};
api.use(csrf);

/** Make sure the CSRF cookie exists (once, at startup). */
export async function ensureCsrfCookie(): Promise<void> {
  if (!csrfToken()) await api.GET("/api/auth/csrf");
}

/** End the session and go to the login page. Logout is a server page (DECISIONS #47)
 *  that only takes POST, with the CSRF token like any other write. Throws if the
 *  session may still be alive: the login page would send us straight back in. */
export async function logOut(): Promise<void> {
  await ensureCsrfCookie();
  const res = await fetch("/logout/", {
    method: "POST",
    headers: { "X-CSRFToken": csrfToken() },
    credentials: "same-origin",
    redirect: "manual", // the server answers with a redirect; we navigate ourselves
  });
  // With redirect: "manual", the redirect arrives as an empty "opaqueredirect" response.
  if (res.type !== "opaqueredirect" && !res.ok) throw new Error(`Logout failed (${res.status})`);
  window.location.assign("/login/");
}

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/** Unwrap an openapi-fetch result: return the data or throw the server's message. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined || (result.data === undefined && result.response.status !== 204)) {
    const detail =
      typeof result.error === "object" && result.error !== null && "detail" in result.error
        ? String((result.error as { detail: unknown }).detail)
        : `Request failed (${result.response.status})`;
    throw new ApiError(result.response.status, detail);
  }
  return result.data as T;
}
