import { describe, expect, it } from "vitest";

import type { Item } from "../api/types";
import { flatten, openTree, placement, progress } from "./milestones";

let n = 0;
function item(fields: Partial<Item> & { id: string }): Item {
  n += 1;
  return {
    short_id: fields.id.toUpperCase(),
    project_id: "p",
    type: "task",
    milestone_id: null,
    title: fields.id,
    details: "",
    status: "open",
    created_by: "owner",
    position: n,
    created_at: "2026-11-12T00:00:00Z",
    updated_at: "2026-11-12T00:00:00Z",
    done_at: null,
    ...fields,
  };
}

// Top level: m1 (a, b), loose, m2 (empty). Done: c in m1.
const items = [
  item({ id: "m1", type: "milestone", position: 0 }),
  item({ id: "a", milestone_id: "m1", position: 0 }),
  item({ id: "b", milestone_id: "m1", position: 1 }),
  item({ id: "loose", position: 1 }),
  item({ id: "m2", type: "milestone", position: 2 }),
  item({ id: "c", milestone_id: "m1", status: "done", position: null }),
];
const tree = openTree(items);
const open = () => true;
const shut = () => false;

describe("milestones", () => {
  it("builds the tree and flattens it back in the server's order", () => {
    expect(tree.map((n) => [n.id, n.children.map((c) => c.id)])).toEqual([
      ["m1", ["a", "b"]],
      ["loose", []],
      ["m2", []],
    ]);
    expect(flatten([...items].reverse()).map((i) => i.id)).toEqual([
      "m1",
      "a",
      "b",
      "loose",
      "m2",
      "c",
    ]);
  });

  it("counts a milestone's done tasks too", () => {
    expect(progress(items, "m1")).toEqual({ done: 1, total: 3 });
  });

  it("drops on a milestone: a task joins at its bottom", () => {
    expect(placement(tree, "loose", { key: "m1", position: "on" }, open)).toEqual({
      milestoneId: "m1",
      order: ["a", "b", "loose"],
    });
    expect(placement(tree, "a", { key: "m2", position: "on" }, open)).toEqual({
      milestoneId: "m2",
      order: ["a"],
    });
  });

  it("refuses drops that change nothing or break a rule", () => {
    expect(placement(tree, "a", { key: "m1", position: "on" }, open)).toBeNull(); // already in it
    expect(placement(tree, "m2", { key: "m1", position: "on" }, open)).toBeNull(); // milestone in milestone
    expect(placement(tree, "m2", { key: "a", position: "before" }, open)).toBeNull(); // between tasks
    expect(placement(tree, "loose", { key: "loose", position: "before" }, open)).toBeNull();
    expect(placement(tree, "b", { key: "a", position: "after" }, open)).toBeNull(); // same spot
  });

  it("drops between tasks: joins that milestone at that spot", () => {
    expect(placement(tree, "loose", { key: "b", position: "before" }, open)).toEqual({
      milestoneId: "m1",
      order: ["a", "loose", "b"],
    });
    expect(placement(tree, "b", { key: "a", position: "before" }, open)).toEqual({
      milestoneId: "m1",
      order: ["b", "a"],
    });
  });

  it("drops between top-level rows: leaves the milestone", () => {
    expect(placement(tree, "a", { key: "m2", position: "after" }, open)).toEqual({
      milestoneId: null,
      order: ["m1", "loose", "m2", "a"],
    });
  });

  it("after an open milestone means first inside it; after a closed one, next to it", () => {
    expect(placement(tree, "loose", { key: "m1", position: "after" }, open)).toEqual({
      milestoneId: "m1",
      order: ["loose", "a", "b"],
    });
    expect(placement(tree, "m2", { key: "m1", position: "after" }, shut)).toEqual({
      milestoneId: null,
      order: ["m1", "m2", "loose"],
    });
  });
});
