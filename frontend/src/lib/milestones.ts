import type { Item } from "../api/types";

/** A project's open list as a tree (DECISIONS #73): the top level holds milestones
 *  and loose tasks, each milestone its open and doing tasks. */
export type Node = { id: string; item: Item; children: Node[] };

const byPosition = (a: Item, b: Item) => (a.position ?? 0) - (b.position ?? 0);
const leaf = (item: Item): Node => ({ id: item.id, item, children: [] });

export function openTree(items: Item[]): Node[] {
  const ranked = items.filter((i) => i.status !== "done").sort(byPosition);
  const tasksOf = (id: string) => ranked.filter((i) => i.milestone_id === id).map(leaf);
  return ranked
    .filter((i) => i.milestone_id === null)
    .map((i) => ({ ...leaf(i), children: i.type === "milestone" ? tasksOf(i.id) : [] }));
}

/** The flat list the server sends: the tree top to bottom, then done items as they were. */
export function flatten(items: Item[]): Item[] {
  const open = openTree(items).flatMap((n) => [n.item, ...n.children.map((c) => c.item)]);
  return [...open, ...items.filter((i) => i.status === "done")];
}

/** A milestone's tasks, done ones included ("3 of 5"). */
export function progress(items: Item[], milestoneId: string) {
  const tasks = items.filter((i) => i.milestone_id === milestoneId);
  return { done: tasks.filter((i) => i.status === "done").length, total: tasks.length };
}

/** "3 tasks · 1 done", the line under a milestone. */
export function tasksLabel({ done, total }: { done: number; total: number }) {
  if (total === 0) return "No tasks yet";
  return `${total} ${total === 1 ? "task" : "tasks"}${done ? ` · ${done} done` : ""}`;
}

export type Drop = { key: string; position: "before" | "after" | "on" };

/** Where a drop puts the dragged item (DECISIONS #75): the milestone it ends up in
 *  (null = the top level) and that level's new order. Null if it can't go there or
 *  nothing would change.
 *
 *  - On a milestone: a task joins it at the bottom.
 *  - Before or after a row: the item joins that row's level at that spot. "After" an
 *    open milestone with tasks means first in that milestone, which is where it shows.
 *  - Milestones stay on the top level.
 */
export function placement(
  tree: Node[],
  draggedId: string,
  drop: Drop,
  isExpanded: (id: string) => boolean,
): { milestoneId: string | null; order: string[] } | null {
  const parentOf = new Map<string, Node | null>();
  const nodes = new Map<string, Node>();
  for (const top of tree) {
    nodes.set(top.id, top);
    parentOf.set(top.id, null);
    for (const child of top.children) {
      nodes.set(child.id, child);
      parentOf.set(child.id, top);
    }
  }
  const dragged = nodes.get(draggedId)?.item;
  let target = nodes.get(drop.key);
  if (!dragged || !target || target.id === dragged.id) return null;

  if (drop.position === "on") {
    const ok = target.item.type === "milestone" && dragged.type === "task";
    if (!ok || dragged.milestone_id === target.id) return null;
    const ids = target.children.map((c) => c.id).filter((id) => id !== dragged.id);
    return { milestoneId: target.id, order: [...ids, dragged.id] };
  }

  let position = drop.position;
  const first = target.children[0];
  if (position === "after" && first && isExpanded(target.id)) {
    if (first.id === dragged.id) return null;
    [target, position] = [first, "before"];
  }
  const parent = parentOf.get(target.id) ?? null;
  if (dragged.type === "milestone" && parent !== null) return null;

  const level = (parent ? parent.children : tree).map((n) => n.id);
  const ids = level.filter((id) => id !== dragged.id);
  ids.splice(ids.indexOf(target.id) + (position === "after" ? 1 : 0), 0, dragged.id);
  const milestoneId = parent ? parent.id : null;
  if (milestoneId === dragged.milestone_id && ids.join() === level.join()) return null;
  return { milestoneId, order: ids };
}
