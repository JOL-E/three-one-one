import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

type Handler = (request: Request) => Response | Promise<Response>;
const routes = new Map<string, Handler>();

/** Fake backend for tests: mockApi("GET /api/me", () => json(401, {...})). */
export function mockApi(route: string, handler: Handler) {
  routes.set(route, handler);
}

export function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

// Installed before any module creates the API client.
vi.stubGlobal(
  "fetch",
  vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const request =
      input instanceof Request
        ? input
        : new Request(new URL(String(input), "http://localhost"), init);
    const key = `${request.method} ${new URL(request.url).pathname}`;
    const handler = routes.get(key);
    if (!handler) throw new Error(`No mock for ${key}`);
    return handler(request);
  }),
);

// Layout switch for tests: desktop (default) or phone.
let desktop = true;
export function setViewport(viewport: "desktop" | "phone") {
  desktop = viewport === "desktop";
}
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: query.includes("min-width: 1024px") ? desktop : false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  }),
});

afterEach(() => {
  cleanup();
  routes.clear();
  desktop = true;
});

// Node 26 has its own (disabled) localStorage global, which hides jsdom's. An in-memory one.
const store = new Map<string, string>();
vi.stubGlobal("localStorage", {
  getItem: (k: string) => store.get(k) ?? null,
  setItem: (k: string, v: string) => void store.set(k, String(v)),
  removeItem: (k: string) => void store.delete(k),
  clear: () => store.clear(),
  key: (n: number) => [...store.keys()][n] ?? null,
  get length() {
    return store.size;
  },
});
