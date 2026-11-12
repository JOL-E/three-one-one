/** Every read and write the app makes, as TanStack Query hooks.
 *
 *  Reads are cached by key and shown at once, then refreshed. Writes that should feel
 *  instant (capture, reorder, move, delete) update the cache first ("optimistic") and
 *  roll back if the server refuses; every write ends by refetching what it touched.
 */
import {
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
  type QueryKey,
} from "@tanstack/react-query";

import { shortIdOf } from "../lib/format";
import { flatten } from "../lib/milestones";
import { api, ApiError, unwrap } from "./client";
import type { Connection, Item, ItemStatus, Project, ProjectState } from "./types";

export const keys = {
  me: ["me"] as const,
  projects: (archived: boolean) => ["projects", archived] as const,
  inbox: ["inbox"] as const,
  projectItems: (id: string) => ["project-items", id] as const,
  item: (id: string) => ["item", id] as const,
  search: (q: string) => ["search", q] as const,
  connections: ["connections"] as const,
};

/** After any write: refetch everything except the session. Cheap for one user. */
function refreshAll(qc: QueryClient) {
  return qc.invalidateQueries({ predicate: (q) => q.queryKey[0] !== "me" });
}

/** Snapshot some cached lists, change them, and give back a function that restores them. */
function patchLists(qc: QueryClient, change: (items: Item[]) => Item[], listKeys: QueryKey[]) {
  const saved = listKeys.map((key) => [key, qc.getQueryData<Item[]>(key)] as const);
  for (const [key, items] of saved) if (items) qc.setQueryData(key, change(items));
  return () => saved.forEach(([key, items]) => qc.setQueryData(key, items));
}

type Rollback = { rollback?: () => void };

// --- Reads -------------------------------------------------------------------------

/** The logged-in user, or null when there's no session (401). */
export function useMe() {
  return useQuery({
    queryKey: keys.me,
    queryFn: async () => {
      const result = await api.GET("/api/me");
      if (result.response.status === 401) return null;
      return unwrap(result);
    },
    staleTime: Infinity,
  });
}

export function useProjects(includeArchived = false) {
  return useQuery({
    queryKey: keys.projects(includeArchived),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects", {
          params: { query: { include_archived: includeArchived } },
        }),
      ),
  });
}

export function useInbox() {
  return useQuery({
    queryKey: keys.inbox,
    queryFn: async () => unwrap(await api.GET("/api/inbox")),
  });
}

/** A project's items: ranked (open, doing) top first, then done. Null = don't fetch. */
export function useProjectItems(projectId: string | null) {
  return useQuery({
    queryKey: keys.projectItems(projectId ?? ""),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/projects/{project_id}/items", {
          params: { path: { project_id: projectId ?? "" } },
        }),
      ),
    enabled: projectId !== null,
  });
}

export function useItem(itemId: string) {
  return useQuery({
    queryKey: keys.item(itemId),
    queryFn: async () =>
      unwrap(await api.GET("/api/items/{item_id}", { params: { path: { item_id: itemId } } })),
    retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 1,
  });
}

export function useSearch(q: string) {
  return useQuery({
    queryKey: keys.search(q),
    queryFn: async () =>
      unwrap(await api.GET("/api/items/search", { params: { query: { q, include_done: true } } })),
    enabled: q.trim().length > 0,
    placeholderData: (previous) => previous,
  });
}

// --- Items -------------------------------------------------------------------------

type NewItem = {
  title: string;
  projectId?: string | null;
  type?: Item["type"];
  milestoneId?: string | null; // joins this milestone, in its project
};

/** Capture an idea. The id is made on the device (DECISIONS #10), so the item shows,
 *  and can be opened, before the server answers. */
export function useAddItem() {
  const qc = useQueryClient();
  const mutation = useMutation<Item, Error, NewItem & { id: string }, Rollback>({
    mutationFn: async ({ id, title, projectId, type, milestoneId }) =>
      unwrap(
        await api.POST("/api/items", {
          body: {
            id,
            title,
            details: "",
            project_id: projectId ?? null,
            type: type ?? "task",
            milestone_id: milestoneId ?? null,
          },
        }),
      ),
    onMutate: async ({ id, title, projectId, milestoneId }) => {
      if (projectId || milestoneId) return {};
      await qc.cancelQueries({ queryKey: keys.inbox });
      const now = new Date().toISOString();
      const draft: Item = {
        id,
        short_id: shortIdOf(id),
        project_id: null,
        type: "task",
        milestone_id: null,
        title: title.trim(),
        details: "",
        status: "open",
        created_by: "owner",
        position: null,
        created_at: now,
        updated_at: now,
        done_at: null,
      };
      return { rollback: patchLists(qc, (items) => [draft, ...items], [keys.inbox]) };
    },
    onError: (_e, _v, ctx) => ctx?.rollback?.(),
    onSettled: () => refreshAll(qc),
  });
  return {
    ...mutation,
    add: (item: NewItem) => mutation.mutate({ ...item, id: crypto.randomUUID() }),
  };
}

export function useUpdateItem(itemId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { title?: string; details?: string; type?: Item["type"] }) =>
      unwrap(
        await api.PATCH("/api/items/{item_id}", { params: { path: { item_id: itemId } }, body }),
      ),
    onSettled: () => refreshAll(qc),
  });
}

export function useSetStatus(itemId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { status: ItemStatus; comment: string }) =>
      unwrap(
        await api.POST("/api/items/{item_id}/status", {
          params: { path: { item_id: itemId } },
          body,
        }),
      ),
    onSettled: () => refreshAll(qc),
  });
}

export function useAddComment(itemId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (text: string) =>
      unwrap(
        await api.POST("/api/items/{item_id}/comments", {
          params: { path: { item_id: itemId } },
          body: { text },
        }),
      ),
    onSettled: () => qc.invalidateQueries({ queryKey: keys.item(itemId) }),
  });
}

/** Lists an item may be showing in (inbox and its project), for optimistic removal. */
function listsOf(item: Pick<Item, "project_id">): QueryKey[] {
  return item.project_id ? [keys.inbox, keys.projectItems(item.project_id)] : [keys.inbox];
}

export function useMoveItem() {
  const qc = useQueryClient();
  return useMutation<Item, Error, { item: Item; projectId: string | null }, Rollback>({
    mutationFn: async ({ item, projectId }) =>
      unwrap(
        await api.POST("/api/items/{item_id}/move", {
          params: { path: { item_id: item.id } },
          body: { project_id: projectId },
        }),
      ),
    onMutate: ({ item }) => ({
      rollback: patchLists(qc, (items) => items.filter((i) => i.id !== item.id), listsOf(item)),
    }),
    onError: (_e, _v, ctx) => ctx?.rollback?.(),
    onSettled: () => refreshAll(qc),
  });
}

export function useDeleteItem() {
  const qc = useQueryClient();
  return useMutation<void, Error, Item, Rollback>({
    mutationFn: async (item) => {
      unwrap(await api.DELETE("/api/items/{item_id}", { params: { path: { item_id: item.id } } }));
    },
    onMutate: (item) => ({
      rollback: patchLists(qc, (items) => items.filter((i) => i.id !== item.id), listsOf(item)),
    }),
    onError: (_e, _v, ctx) => ctx?.rollback?.(),
    onSettled: (_d, _e, item) => {
      qc.removeQueries({ queryKey: keys.item(item.id) });
      return refreshAll(qc);
    },
  });
}

/** A drop in a project's list (DECISIONS #75): into or out of a milestone if the
 *  level changes, then the new order of the level the item landed in. Two requests;
 *  if the second fails, the item is in the right place, just at the bottom. */
export function usePlaceItem(projectId: string) {
  const qc = useQueryClient();
  type Placement = { item: Item; milestoneId: string | null; order: string[] };
  return useMutation<void, Error, Placement, Rollback>({
    mutationFn: async ({ item, milestoneId, order }) => {
      if (item.milestone_id !== milestoneId) {
        unwrap(
          await api.POST("/api/items/{item_id}/move", {
            params: { path: { item_id: item.id } },
            body: { project_id: projectId, milestone_id: milestoneId },
          }),
        );
      }
      if (order.length > 1) {
        unwrap(
          await api.PUT("/api/projects/{project_id}/order", {
            params: { path: { project_id: projectId } },
            body: { item_ids: order, milestone_id: milestoneId },
          }),
        );
      }
    },
    onMutate: async ({ item, milestoneId, order }) => {
      await qc.cancelQueries({ queryKey: keys.projectItems(projectId) });
      const place = (items: Item[]) =>
        flatten(
          items.map((i) => {
            const at = order.indexOf(i.id);
            const moved = i.id === item.id ? { ...i, milestone_id: milestoneId } : i;
            return at === -1 ? moved : { ...moved, position: at };
          }),
        );
      return { rollback: patchLists(qc, place, [keys.projectItems(projectId)]) };
    },
    onError: (_e, _v, ctx) => ctx?.rollback?.(),
    onSettled: () => refreshAll(qc),
  });
}

// --- Projects ----------------------------------------------------------------------

export type ProjectFields = { name: string; description: string; repo_url: string };

export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: ProjectFields) => unwrap(await api.POST("/api/projects", { body })),
    onSettled: () => refreshAll(qc),
  });
}

export function useUpdateProject(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: Partial<ProjectFields>) =>
      unwrap(
        await api.PATCH("/api/projects/{project_id}", {
          params: { path: { project_id: projectId } },
          body,
        }),
      ),
    onSettled: () => refreshAll(qc),
  });
}

export function useSetProjectState(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (state: ProjectState) =>
      unwrap(
        await api.PUT("/api/projects/{project_id}/state", {
          params: { path: { project_id: projectId } },
          body: { state },
        }),
      ),
    onSettled: () => refreshAll(qc),
  });
}

export function useDeleteProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (project: Project) => {
      unwrap(
        await api.DELETE("/api/projects/{project_id}", {
          params: { path: { project_id: project.id } },
        }),
      );
    },
    onSettled: () => refreshAll(qc),
  });
}

// --- Connected apps (MCP clients with access) ------------------------------------

/** The MCP clients that hold a working token, and the URL to connect a new one. */
export function useConnections(enabled = true) {
  return useQuery({
    queryKey: keys.connections,
    queryFn: async () => unwrap(await api.GET("/api/connections")),
    enabled,
  });
}

/** Take a client's access away at once. Not optimistic: it's rare, and the list
 *  should show what the server actually did. */
export function useDisconnect() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (app: Connection) => {
      unwrap(
        await api.DELETE("/api/connections/{app_id}", { params: { path: { app_id: app.id } } }),
      );
    },
    onSettled: () => qc.invalidateQueries({ queryKey: keys.connections }),
  });
}
