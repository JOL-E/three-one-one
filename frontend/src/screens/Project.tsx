import { Reorder, useDragControls } from "motion/react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router";

import { useAddItem, useProjectItems, useProjects, useSetOrder } from "../api/queries";
import type { Item, Project } from "../api/types";
import { GripIcon } from "../components/icons";
import { ItemRow } from "../components/ItemRow";
import { ListDetail } from "../components/ListDetail";
import { ProjectSheet } from "../components/sheets";
import { Button, Empty, ScreenHeader, ShortId, SkeletonRows, Stamp } from "../components/ui";
import { day } from "../lib/format";
import { useEdgeSwipeBack, useGoBack } from "../lib/navigation";
import { useIsDesktop } from "../lib/useMediaQuery";

export function ProjectScreen() {
  const { projectId = "", itemId } = useParams();
  const projects = useProjects(true);
  const project = projects.data?.find((p) => p.id === projectId);
  if (projects.isPending) return <SkeletonRows />;
  if (!project) return <Empty>This project doesn't exist (any more).</Empty>;
  return (
    <ListDetail
      itemId={itemId}
      back={{ to: `/p/${project.id}`, label: project.name }}
      list={<ProjectList key={project.id} project={project} selectedId={itemId} />}
    />
  );
}

function ProjectList({ project, selectedId }: { project: Project; selectedId?: string }) {
  const desktop = useIsDesktop();
  const items = useProjectItems(project.id);
  const [editing, setEditing] = useState(false);
  const goBack = useGoBack("/projects");
  const screen = useRef<HTMLDivElement>(null);
  useEdgeSwipeBack(screen, goBack, !desktop && !selectedId);

  const ranked = (items.data ?? []).filter((i) => i.status !== "done");
  const done = (items.data ?? []).filter((i) => i.status === "done");

  return (
    <div ref={screen} className={desktop ? "" : "animate-push-in bg-ground min-h-full"}>
      <ScreenHeader
        title={project.name}
        back={{ to: "/projects", label: "Projects" }}
        actions={
          <Button className="h-8 px-2.5 text-[11px]" onClick={() => setEditing(true)}>
            {project.state} · Edit
          </Button>
        }
      >
        {project.description || project.repo_url ? (
          <div className="text-muted flex flex-wrap gap-x-4 gap-y-1 text-[14px]">
            {project.description ? (
              <span className="whitespace-pre-wrap">{project.description}</span>
            ) : null}
            {project.repo_url ? (
              <a
                href={project.repo_url}
                target="_blank"
                rel="noreferrer"
                className="text-accent hover:text-accent-hover"
              >
                {project.repo_url.replace(/^https?:\/\//, "")}
              </a>
            ) : null}
          </div>
        ) : null}
      </ScreenHeader>

      {items.isPending ? (
        <SkeletonRows />
      ) : (
        <>
          <div className="label text-muted flex justify-between px-5 pt-3 pb-1.5 lg:px-7">
            <span>Priority</span>
            {ranked.length > 1 ? <span>Drag ≡ to reorder</span> : null}
          </div>
          {ranked.length === 0 ? (
            <Empty>Nothing open here.</Empty>
          ) : (
            <RankedList project={project} items={ranked} selectedId={selectedId} />
          )}
          <AddToProject project={project} />
          {done.length > 0 ? (
            <section>
              <h2 className="label text-muted m-0 px-5 pt-5 pb-2 lg:px-7">
                Closed · {done.length}
              </h2>
              <ul className="border-hairline m-0 list-none border-t p-0">
                {done.map((item) => (
                  <li key={item.id}>
                    <ItemRow
                      item={item}
                      to={`/p/${project.id}/${item.id}`}
                      selected={item.id === selectedId}
                      meta={item.done_at ? `Done ${day(item.done_at)}` : "Done"}
                    />
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </>
      )}
      <ProjectSheet
        key={`${project.id}-${project.name}-${editing}`}
        project={project}
        isOpen={editing}
        onClose={() => setEditing(false)}
      />
    </div>
  );
}

/** Drag-to-sort (DECISIONS #39): the order is local while dragging and sent on drop. */
function RankedList({
  project,
  items,
  selectedId,
}: {
  project: Project;
  items: Item[];
  selectedId?: string;
}) {
  const [order, setOrder] = useState(items);
  const setServerOrder = useSetOrder(project.id);

  // Follow the server whenever its list changes (new item, status change, refetch):
  // React's "adjust state while rendering" pattern, no effect needed.
  const serverKey = items.map((i) => `${i.id}:${i.status}:${i.title}`).join(",");
  const [seenKey, setSeenKey] = useState(serverKey);
  if (serverKey !== seenKey) {
    setSeenKey(serverKey);
    setOrder(items);
  }

  // motion keeps the drop handler from when the drag started, so the handler reads the
  // latest order from a ref (kept current by an effect) rather than from its closure.
  const latest = useRef({ order, items });
  useEffect(() => {
    latest.current = { order, items };
  }, [order, items]);
  const commit = () => {
    const ids = latest.current.order.map((i) => i.id);
    if (ids.join() !== latest.current.items.map((i) => i.id).join()) setServerOrder.mutate(ids);
  };

  return (
    <Reorder.Group
      as="ol"
      axis="y"
      values={order}
      onReorder={setOrder}
      className="border-hairline m-0 list-none border-t p-0"
    >
      {order.map((item) => (
        <RankedRow
          key={item.id}
          item={item}
          to={`/p/${project.id}/${item.id}`}
          selected={item.id === selectedId}
          onDrop={commit}
        />
      ))}
    </Reorder.Group>
  );
}

function RankedRow({
  item,
  to,
  selected,
  onDrop,
}: {
  item: Item;
  to: string;
  selected: boolean;
  onDrop: () => void;
}) {
  // Only the handle starts a drag, so the rest of the row still scrolls the list.
  const controls = useDragControls();
  return (
    <Reorder.Item
      value={item}
      dragListener={false}
      dragControls={controls}
      onDragEnd={onDrop}
      className={`bg-surface border-hairline relative flex h-14 items-center gap-3.5 border-b pr-1 pl-5 lg:pl-7 ${
        selected ? "outline-text outline-2 -outline-offset-2" : ""
      }`}
    >
      <ShortId id={item.short_id} className="shrink-0" />
      <Link
        to={to}
        className={`min-w-0 flex-1 truncate text-[16px] ${item.status === "doing" ? "font-semibold" : ""}`}
      >
        {item.title}
      </Link>
      <Stamp status={item.status} />
      <button
        type="button"
        aria-label={`Drag to reorder ${item.title}`}
        onPointerDown={(e) => controls.start(e)}
        className="text-muted flex h-11 w-11 shrink-0 cursor-grab touch-none items-center justify-center"
      >
        <GripIcon size={20} />
      </button>
    </Reorder.Item>
  );
}

function AddToProject({ project }: { project: Project }) {
  const [title, setTitle] = useState("");
  const { add } = useAddItem();
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    add({ title, projectId: project.id });
    setTitle("");
  };
  return (
    <form onSubmit={submit} className="px-5 py-3 lg:px-7">
      <label htmlFor="add-to-project" className="sr-only">
        Add an item to {project.name}
      </label>
      <input
        id="add-to-project"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder={`+ Add to ${project.name}`}
        enterKeyHint="done"
        autoComplete="off"
        className="border-dash text-text focus:border-accent h-11 w-full border border-dashed bg-transparent px-3 text-[16px] outline-none focus:border-solid"
      />
    </form>
  );
}
