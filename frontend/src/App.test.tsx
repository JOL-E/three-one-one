import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { App } from "./App";
import { json, mockApi } from "./test/setup";

function renderApp() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

const item = {
  id: "3f9a07e4-0000-4000-8000-000000000001",
  short_id: "3F9A",
  project_id: null,
  title: "Try a synthetic idea",
  details: "",
  status: "open",
  created_by: "claude",
  position: null,
  created_at: "2026-11-08T12:00:00Z",
  updated_at: "2026-11-08T12:00:00Z",
  done_at: null,
};

function loggedIn(inbox: unknown[] = [item]) {
  mockApi("GET /api/me", () => json(200, { username: "owner" }));
  mockApi("GET /api/inbox", () => json(200, inbox));
  mockApi("GET /api/projects", () => json(200, []));
}

describe("App", () => {
  it("offers a login without a session", async () => {
    mockApi("GET /api/me", () => json(401, { detail: "Unauthorized" }));
    renderApp();
    expect(await screen.findByRole("link", { name: "Log in" })).toHaveAttribute(
      "href",
      "/admin/login/?next=/",
    );
  });

  it("shows the inbox with short ids and who filed each item", async () => {
    loggedIn();
    renderApp();
    expect(await screen.findByText("Try a synthetic idea")).toBeInTheDocument();
    expect(screen.getAllByText("#3F9A").length).toBeGreaterThan(0);
    expect(screen.getByText("Claude")).toBeInTheDocument();
  });

  it("captures an idea with an id made on the device", async () => {
    loggedIn([]);
    const inbox: unknown[] = [];
    mockApi("GET /api/inbox", () => json(200, inbox));
    let sent: Record<string, unknown> = {};
    mockApi("POST /api/items", async (request) => {
      sent = (await request.json()) as Record<string, unknown>;
      const created = { ...item, id: sent.id, title: sent.title, created_by: "owner" };
      inbox.unshift(created);
      return json(201, created);
    });
    renderApp();
    const input = await screen.findByLabelText("Capture");
    await userEvent.type(input, "A new synthetic idea{Enter}");
    expect(await screen.findByText("A new synthetic idea")).toBeInTheDocument();
    expect(sent.title).toBe("A new synthetic idea");
    expect(String(sent.id)).toMatch(/^[0-9a-f-]{36}$/);
  });
});
