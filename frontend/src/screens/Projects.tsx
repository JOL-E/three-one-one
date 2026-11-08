import { useState } from "react";
import { Link } from "react-router";

import { useProjects } from "../api/queries";
import type { Project } from "../api/types";
import { ChevronIcon, GearIcon, PlusIcon } from "../components/icons";
import { ProjectSheet, SettingsSheet } from "../components/sheets";
import { Button, IconButton, ScreenHeader, SkeletonRows } from "../components/ui";
import { byGroup } from "../lib/projects";

/** Every project by state. The phone's Projects tab; "All projects" on desktop. */
export function ProjectsScreen() {
  const [showArchived, setShowArchived] = useState(false);
  const projects = useProjects(showArchived);
  const [creating, setCreating] = useState(false);
  const [settings, setSettings] = useState(false);
  const groups = byGroup(projects.data ?? []);

  return (
    <div className="flex h-full min-w-0 flex-1 flex-col overflow-y-auto overscroll-contain">
      <ScreenHeader
        title="Projects"
        actions={
          <>
            <IconButton label="New project" onClick={() => setCreating(true)}>
              <PlusIcon />
            </IconButton>
            <IconButton label="Settings" onClick={() => setSettings(true)} className="lg:hidden">
              <GearIcon />
            </IconButton>
          </>
        }
      />
      {projects.isPending ? (
        <SkeletonRows />
      ) : (
        <>
          <Group title="Building & live" projects={groups.active} />
          <Group title="Ideas" projects={groups.ideas} />
          {showArchived ? <Group title="Archived" projects={groups.archived} /> : null}
          <div className="px-5 py-6 lg:px-7">
            <Button onClick={() => setShowArchived(!showArchived)}>
              {showArchived ? "Hide archived" : "Show archived"}
            </Button>
          </div>
        </>
      )}
      <ProjectSheet key={String(creating)} isOpen={creating} onClose={() => setCreating(false)} />
      <SettingsSheet isOpen={settings} onClose={() => setSettings(false)} />
    </div>
  );
}

function Group({ title, projects }: { title: string; projects: Project[] }) {
  if (projects.length === 0) return null;
  return (
    <section>
      <h2 className="label text-muted m-0 px-5 pt-5 pb-2 lg:px-7">{title}</h2>
      <ul className="border-hairline m-0 list-none border-t p-0">
        {projects.map((p) => (
          <li key={p.id}>
            <Link
              to={`/p/${p.id}`}
              className="bg-surface border-hairline flex h-14 items-center gap-3 border-b px-5 lg:px-7"
            >
              <span className="flex-1 truncate text-[17px] font-medium">{p.name}</span>
              <span className="text-muted font-mono text-[13px]">{p.open_items || ""}</span>
              <ChevronIcon size={16} className="text-muted" />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
