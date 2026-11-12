import { useRef, useState, type FormEvent, type ReactNode } from "react";
import { useParams } from "react-router";

import { useAddItem, useProjectItems, useProjects } from "../api/queries";
import type { Item, Project } from "../api/types";
import { ChevronIcon } from "../components/icons";
import { ItemRow } from "../components/ItemRow";
import { ListDetail } from "../components/ListDetail";
import { ProjectTree } from "../components/ProjectTree";
import { ProjectSheet } from "../components/sheets";
import { Button, Empty, ScreenHeader, SkeletonRows } from "../components/ui";
import { day } from "../lib/format";
import { tasksLabel } from "../lib/milestones";
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
            {ranked.length > 1 ? <span>{desktop ? "Drag" : "Hold"} to move</span> : null}
          </div>
          {ranked.length === 0 ? (
            <Empty>Nothing open here.</Empty>
          ) : (
            <ProjectTree project={project} items={items.data ?? []} selectedId={selectedId} />
          )}
          <AddToProject project={project} />
          {done.length > 0 ? (
            <Closed project={project} items={items.data ?? []} selectedId={selectedId} />
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

/** Done items (DECISIONS #83): a done milestone is one row that opens to its tasks; a
 *  done task of a milestone still open names it. */
function Closed({
  project,
  items,
  selectedId,
}: {
  project: Project;
  items: Item[];
  selectedId?: string;
}) {
  const done = items.filter((i) => i.status === "done");
  const titleOf = new Map(items.map((i) => [i.id, i.title]));
  const doneMilestones = new Set(done.filter((i) => i.type === "milestone").map((i) => i.id));
  const inDoneMilestone = (i: Item) =>
    i.milestone_id !== null && doneMilestones.has(i.milestone_id);
  const row = (item: Item, meta?: string) => (
    <ItemRow
      item={item}
      to={`/p/${project.id}/${item.id}`}
      selected={item.id === selectedId}
      meta={[item.done_at ? `Done ${day(item.done_at)}` : "Done", meta].filter(Boolean).join(" · ")}
    />
  );
  return (
    <section>
      <h2 className="label text-muted m-0 px-5 pt-5 pb-2 lg:px-7">Closed · {done.length}</h2>
      <ul className="border-hairline m-0 list-none border-t p-0">
        {done
          .filter((i) => !inDoneMilestone(i))
          .map((item) => (
            <li key={item.id}>
              {item.type === "milestone" ? (
                <ClosedMilestone tasks={done.filter((i) => i.milestone_id === item.id)} row={row}>
                  {row(item, "Milestone")}
                </ClosedMilestone>
              ) : (
                row(item, item.milestone_id ? titleOf.get(item.milestone_id) : undefined)
              )}
            </li>
          ))}
      </ul>
    </section>
  );
}

function ClosedMilestone({
  tasks,
  row,
  children,
}: {
  tasks: Item[];
  row: (item: Item) => ReactNode;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      {children}
      {tasks.length > 0 ? (
        <button
          type="button"
          aria-expanded={open}
          onClick={() => setOpen(!open)}
          className="label text-muted border-hairline flex h-11 w-full items-center gap-2 border-b pl-12 text-left tracking-[0.06em] lg:pl-14"
        >
          <ChevronIcon size={14} className={`transition-transform ${open ? "rotate-90" : ""}`} />
          {tasksLabel({ done: tasks.length, total: tasks.length })}
        </button>
      ) : null}
      {open ? (
        <ul className="m-0 list-none p-0 pl-7">
          {tasks.map((task) => (
            <li key={task.id}>{row(task)}</li>
          ))}
        </ul>
      ) : null}
    </>
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
