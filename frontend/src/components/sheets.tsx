import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";

import {
  useCreateProject,
  useDeleteItem,
  useDeleteProject,
  useMoveItem,
  useProjects,
  useSetProjectState,
  useSetStatus,
  useUpdateItem,
  useUpdateProject,
} from "../api/queries";
import type { Item, ItemStatus, Project, ProjectState } from "../api/types";
import { setPref, useThemePref, type ThemePref } from "../lib/theme";
import { byGroup } from "../lib/projects";
import { Sheet } from "./Sheet";
import { Button, Field, ShortId } from "./ui";

/** Sort an item into a project, or back to the inbox (open items only). */
export function MoveSheet({ item, onClose }: { item: Item | null; onClose: () => void }) {
  const projects = useProjects();
  const move = useMoveItem();
  const groups = byGroup(projects.data ?? []);
  const choose = (projectId: string | null) => {
    if (!item) return;
    move.mutate({ item, projectId });
    onClose();
  };
  const row = (id: string | null, name: string) => {
    const current = item?.project_id === id;
    return (
      <li key={id ?? "inbox"}>
        <button
          type="button"
          disabled={current}
          onClick={() => choose(id)}
          className="border-hairline flex h-12 w-full items-center justify-between border-b text-left text-[17px] active:opacity-50 disabled:opacity-50"
        >
          {name}
          {current ? <span className="label text-muted">Current</span> : null}
        </button>
      </li>
    );
  };
  return (
    <Sheet
      isOpen={item !== null}
      onClose={onClose}
      title={item ? `Move #${item.short_id}` : "Move"}
    >
      <ul className="m-0 list-none p-0">
        {[...groups.active, ...groups.ideas].map((p) => row(p.id, p.name))}
        {item?.project_id && item.status === "open" ? row(null, "Back to the inbox") : null}
      </ul>
    </Sheet>
  );
}

const statusVerb: Record<ItemStatus, string> = {
  open: "Back to open",
  doing: "Start",
  done: "Mark done",
};

/** A status change needs a comment saying why (DECISIONS #5); the server checks too. */
export function StatusSheet({
  item,
  to,
  onClose,
}: {
  item: Item;
  to: ItemStatus | null;
  onClose: () => void;
}) {
  const [why, setWhy] = useState("");
  const setStatus = useSetStatus(item.id);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!to) return;
    setStatus.mutate(
      { status: to, comment: why },
      {
        onSuccess: () => {
          setWhy("");
          onClose();
        },
      },
    );
  };
  return (
    <Sheet isOpen={to !== null} onClose={onClose} title={to ? `${statusVerb[to]} · why?` : ""}>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <Field
          label="Why"
          value={why}
          onChange={setWhy}
          multiline
          autoFocus
          placeholder="Goes into the log"
        />
        <Button type="submit" tone="accent" disabled={!why.trim() || setStatus.isPending}>
          {to ? statusVerb[to] : "Save"}
        </Button>
      </form>
    </Sheet>
  );
}

export function EditItemSheet({
  item,
  isOpen,
  onClose,
}: {
  item: Item;
  isOpen: boolean;
  onClose: () => void;
}) {
  const [title, setTitle] = useState(item.title);
  const [details, setDetails] = useState(item.details);
  const update = useUpdateItem(item.id);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    update.mutate({ title, details }, { onSuccess: onClose });
  };
  return (
    <Sheet isOpen={isOpen} onClose={onClose} title={`Edit #${item.short_id}`}>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <Field label="Title" value={title} onChange={setTitle} />
        <Field label="Details" value={details} onChange={setDetails} multiline />
        <Button type="submit" tone="accent" disabled={!title.trim() || update.isPending}>
          Save
        </Button>
      </form>
    </Sheet>
  );
}

export function DeleteItemSheet({
  item,
  onClose,
  onDeleted,
}: {
  item: Item | null;
  onClose: () => void;
  onDeleted?: () => void;
}) {
  const remove = useDeleteItem();
  return (
    <Sheet isOpen={item !== null} onClose={onClose} title="Delete">
      {item ? (
        <div className="flex flex-col gap-4">
          <p className="m-0 text-[17px]">
            Delete <ShortId id={item.short_id} /> {item.title}? Its log goes with it.
          </p>
          <Button
            tone="danger"
            onClick={() => {
              remove.mutate(item);
              onClose();
              onDeleted?.();
            }}
          >
            Delete
          </Button>
        </div>
      ) : null}
    </Sheet>
  );
}

const states: ProjectState[] = ["idea", "building", "live", "archived"];

/** Create a project (always an idea), or edit one: details, state, delete. */
export function ProjectSheet({
  project,
  isOpen,
  onClose,
}: {
  project?: Project;
  isOpen: boolean;
  onClose: () => void;
}) {
  const [name, setName] = useState(project?.name ?? "");
  const [description, setDescription] = useState(project?.description ?? "");
  const [repoUrl, setRepoUrl] = useState(project?.repo_url ?? "");
  const create = useCreateProject();
  const update = useUpdateProject(project?.id ?? "");
  const setState = useSetProjectState(project?.id ?? "");
  const remove = useDeleteProject();
  const navigate = useNavigate();

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const fields = { name, description, repo_url: repoUrl };
    if (project) {
      update.mutate(fields, { onSuccess: onClose });
    } else {
      create.mutate(fields, {
        onSuccess: (created) => {
          setName("");
          setDescription("");
          setRepoUrl("");
          onClose();
          void navigate(`/p/${created.id}`);
        },
      });
    }
  };

  return (
    <Sheet
      isOpen={isOpen}
      onClose={onClose}
      title={project ? `Edit ${project.name}` : "New project"}
    >
      <form onSubmit={submit} className="flex flex-col gap-4">
        <Field label="Name" value={name} onChange={setName} autoFocus={!project} />
        <Field label="Description" value={description} onChange={setDescription} multiline />
        <Field
          label="Repo link"
          value={repoUrl}
          onChange={setRepoUrl}
          type="url"
          placeholder="https://…"
        />
        <Button type="submit" tone="accent" disabled={!name.trim()}>
          {project ? "Save" : "Create"}
        </Button>
      </form>
      {project && !project.is_general ? (
        <div className="border-hairline mt-6 flex flex-col gap-4 border-t pt-5">
          <div className="flex flex-col gap-2">
            <span className="label text-muted">State</span>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {states.map((s) => (
                <Button
                  key={s}
                  tone={project.state === s ? "ink" : "outline"}
                  aria-pressed={project.state === s}
                  onClick={() => setState.mutate(s)}
                >
                  {s}
                </Button>
              ))}
            </div>
          </div>
          <Button
            tone="danger"
            onClick={() =>
              remove.mutate(project, {
                onSuccess: () => {
                  onClose();
                  void navigate("/projects", { replace: true });
                },
              })
            }
          >
            Delete project
          </Button>
          <p className="text-muted m-0 text-[13px]">
            Only empty projects can be deleted. Archiving keeps everything.
          </p>
        </div>
      ) : null}
    </Sheet>
  );
}

const themes: { value: ThemePref; label: string }[] = [
  { value: "dark", label: "Dark" },
  { value: "light", label: "Light" },
  { value: "system", label: "Follow phone" },
];

export function SettingsSheet({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const pref = useThemePref();
  return (
    <Sheet isOpen={isOpen} onClose={onClose} title="Settings">
      <div className="flex flex-col gap-2">
        <span className="label text-muted">Theme</span>
        <div className="grid grid-cols-3 gap-2">
          {themes.map((t) => (
            <Button
              key={t.value}
              tone={pref === t.value ? "ink" : "outline"}
              aria-pressed={pref === t.value}
              onClick={() => setPref(t.value)}
            >
              {t.label}
            </Button>
          ))}
        </div>
      </div>
    </Sheet>
  );
}
