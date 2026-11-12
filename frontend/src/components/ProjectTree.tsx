import { useRef, useState } from "react";
import {
  Button as AriaButton,
  Collection,
  DropIndicator,
  Tree,
  TreeItem,
  TreeItemContent,
  useDragAndDrop,
  type Key,
} from "react-aria-components";
import { useNavigate } from "react-router";

import { usePlaceItem } from "../api/queries";
import type { Item, Project } from "../api/types";
import { openTree, placement, progress, tasksLabel, type Drop, type Node } from "../lib/milestones";
import { ChevronIcon } from "./icons";
import { ShortId, Stamp } from "./ui";

const DRAG_TYPE = "application/x-311-item";
const COLLAPSED_KEY = "311-collapsed-milestones"; // per device (DECISIONS #81)

function readCollapsed(): Set<string> {
  try {
    return new Set(JSON.parse(localStorage.getItem(COLLAPSED_KEY) ?? "[]") as string[]);
  } catch {
    return new Set(); // storage blocked: everything expanded
  }
}

function saveCollapsed(ids: Set<string>) {
  try {
    localStorage.setItem(COLLAPSED_KEY, JSON.stringify([...ids]));
  } catch {
    // Not remembered, still applied for this visit.
  }
}

/** A project's open items: milestones with their tasks, and loose tasks (DECISIONS
 *  #73, #75). Long-press (touch) or drag (mouse) a row to move it: onto a milestone
 *  to join it, between rows to place it there. React Aria's Tree uses the browser's
 *  own drag and drop, plus keyboard and screen-reader dragging. */
export function ProjectTree({
  project,
  items,
  selectedId,
}: {
  project: Project;
  items: Item[];
  selectedId?: string;
}) {
  const navigate = useNavigate();
  const place = usePlaceItem(project.id);
  const tree = openTree(items);
  const byId = new Map(items.map((i) => [i.id, i]));

  const milestones = tree.filter((n) => n.item.type === "milestone").map((n) => n.id);
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const expanded = new Set(milestones.filter((id) => !collapsed.has(id)));
  const onExpandedChange = (keys: Set<Key>) => {
    const next = new Set(collapsed);
    for (const id of milestones) {
      if (keys.has(id)) next.delete(id);
      else next.add(id);
    }
    setCollapsed(next);
    saveCollapsed(next);
  };

  // The browser's drag events don't say what is being dragged until the drop, so the
  // key is kept from the drag's start to decide which rows accept it.
  const dragging = useRef<string | null>(null);
  const where = (key: Key, position: Drop["position"]) =>
    dragging.current
      ? placement(tree, dragging.current, { key: String(key), position }, (id) => expanded.has(id))
      : null;

  const { dragAndDropHooks } = useDragAndDrop<Node>({
    getItems: (keys) =>
      [...keys].map((key) => ({
        [DRAG_TYPE]: String(key),
        "text/plain": byId.get(String(key))?.title ?? "",
      })),
    acceptedDragTypes: [DRAG_TYPE],
    getAllowedDropOperations: () => ["move"],
    onDragStart: (e) => {
      dragging.current = String([...e.keys][0]);
    },
    onDragEnd: () => {
      dragging.current = null;
    },
    getDropOperation: (target) =>
      target.type === "item" && where(target.key, target.dropPosition) ? "move" : "cancel",
    // Fires for every drop inside the tree: on a row and between rows.
    onMove: (e) => {
      const item = dragging.current ? byId.get(dragging.current) : undefined;
      const to = where(e.target.key, e.target.dropPosition);
      if (item && to) place.mutate({ item, ...to });
    },
    renderDropIndicator: (target) => (
      <DropIndicator
        target={target}
        className={({ isDropTarget }) => (isDropTarget ? "bg-accent h-0.5" : "")}
      />
    ),
  });

  const row = (node: Node) => {
    const { item } = node;
    const milestone = item.type === "milestone";
    const counts = milestone ? progress(items, item.id) : null;
    return (
      <TreeItem
        key={node.id}
        id={node.id}
        textValue={item.title}
        onAction={() => void navigate(`/p/${project.id}/${item.id}`)}
        className={({ isDropTarget, isDragging, isFocusVisible, isPressed, level }) =>
          [
            "border-hairline relative flex cursor-default border-b outline-none select-none",
            // Held: the row sinks over about the time iOS takes to lift it into a drag,
            // so you see it coming (like Reminders). Let go early: it springs back fast.
            "transition-[scale,background-color] ease-out",
            isPressed
              ? "bg-hairline duration-500 motion-safe:scale-[0.97]"
              : "bg-surface duration-150",
            milestone
              ? "flex-col"
              : `h-14 items-center gap-3 pr-4 ${level > 1 ? "pl-12 lg:pl-14" : "pl-5 lg:pl-7"}`,
            item.id === selectedId || isFocusVisible
              ? "outline-text outline-2 -outline-offset-2"
              : "",
            isDropTarget ? "outline-accent outline-2 -outline-offset-2" : "",
            isDragging ? "opacity-40" : "",
            "[-webkit-touch-callout:none]",
          ].join(" ")
        }
      >
        <TreeItemContent>
          {({ isExpanded }) => {
            const line = (
              <>
                <ShortId id={item.short_id} className="shrink-0" />
                <span
                  className={`min-w-0 flex-1 truncate ${
                    milestone ? "text-[17px] font-bold" : "text-[16px]"
                  } ${item.status === "doing" ? "font-semibold" : ""}`}
                >
                  {item.title}
                </span>
                <Stamp status={item.status} />
              </>
            );
            if (!counts) return line;
            // A milestone: lined up with loose tasks, its tasks toggle on a line of
            // its own below, at their indent (same as in the closed list).
            const toggle =
              "label text-muted flex h-11 items-center gap-2 pl-12 tracking-[0.06em] lg:pl-14";
            return (
              <>
                <div className="border-hairline flex h-14 items-center gap-3 border-b pr-4 pl-5 lg:pl-7">
                  {line}
                </div>
                {node.children.length > 0 ? (
                  <AriaButton slot="chevron" className={`${toggle} w-full text-left outline-none`}>
                    <ChevronIcon
                      size={14}
                      className={`transition-transform ${isExpanded ? "rotate-90" : ""}`}
                    />
                    {tasksLabel(counts)}
                  </AriaButton>
                ) : (
                  <span className={toggle}>{tasksLabel(counts)}</span>
                )}
              </>
            );
          }}
        </TreeItemContent>
        {node.children.length > 0 ? <Collection items={node.children}>{row}</Collection> : null}
      </TreeItem>
    );
  };

  return (
    <Tree
      aria-label={`Open items in ${project.name}`}
      items={tree}
      expandedKeys={expanded}
      onExpandedChange={onExpandedChange}
      dragAndDropHooks={dragAndDropHooks}
      className="border-hairline border-t outline-none"
    >
      {row}
    </Tree>
  );
}
