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
      "/login/?next=%2F",
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

  it("shows milestones with their tasks, open and closed (DECISIONS #81–83)", async () => {
    loggedIn([]);
    const project = {
      id: "9e8654c3-0000-4000-8000-000000000001",
      name: "Synthetic project",
      description: "",
      repo_url: "",
      state: "building",
      is_general: false,
      open_items: 2,
    };
    const at = (n: number) => `3f9a07e4-0000-4000-8000-00000000001${n}`;
    const row = (n: number, fields: Record<string, unknown>) => ({
      ...item,
      id: at(n),
      short_id: `AB0${n}`,
      project_id: project.id,
      type: "task",
      milestone_id: null,
      ...fields,
    });
    const done = { status: "done", position: null, done_at: "2026-11-09T12:00:00Z" };
    mockApi("GET /api/projects", () => json(200, [project]));
    mockApi(`GET /api/projects/${project.id}/items`, () =>
      json(200, [
        row(1, { title: "M8: Synthetic", type: "milestone", position: 0 }),
        row(2, { title: "Open task", milestone_id: at(1), position: 0 }),
        row(3, { title: "Loose task", position: 1 }),
        row(4, { title: "Finished task", milestone_id: at(1), ...done }),
        row(5, { title: "M7: Shipped", type: "milestone", ...done }),
        row(6, { title: "Shipped task", milestone_id: at(5), ...done }),
      ]),
    );
    window.history.pushState({}, "", `/p/${project.id}`);
    renderApp();

    expect(await screen.findByText("M8: Synthetic")).toBeInTheDocument();
    expect(screen.getByText("Open task")).toBeInTheDocument();
    // The open milestone counts its done task; that task stays in Closed, naming it.
    await userEvent.click(screen.getByRole("button", { name: /^Collapse/ }));
    expect(screen.queryByText("Open task")).not.toBeInTheDocument();
    expect(screen.getByText(/Done Nov 09 · M8: Synthetic/)).toBeInTheDocument();
    // A done milestone is one closed row; its tasks open below it.
    expect(screen.queryByText("Shipped task")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /1 task · 1 done/ }));
    expect(screen.getByText("Shipped task")).toBeInTheDocument();
    window.history.pushState({}, "", "/");
  });

  it("lists connected apps and disconnects one", async () => {
    loggedIn([]);
    let apps = [
      {
        id: 7,
        name: "Synthetic client",
        host: "client.example",
        last_active: "2026-11-08T12:00:00Z",
      },
    ];
    mockApi("GET /api/connections", () =>
      json(200, { mcp_url: "https://311.example.com/mcp", apps }),
    );
    mockApi("GET /api/auth/csrf", () => new Response(null, { status: 204 }));
    let deleted = "";
    mockApi("DELETE /api/connections/7", (request) => {
      deleted = new URL(request.url).pathname;
      apps = [];
      return new Response(null, { status: 204 });
    });
    renderApp();
    await userEvent.click(await screen.findByRole("button", { name: /Settings/ }));
    expect(await screen.findByText("Synthetic client")).toBeInTheDocument();
    expect(screen.getByText("https://311.example.com/mcp")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Disconnect" }));
    expect(await screen.findByText(/Nothing connected yet/)).toBeInTheDocument();
    expect(deleted).toBe("/api/connections/7");
  });
});
