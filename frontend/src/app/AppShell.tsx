import { useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router";

import { useInbox, useProjects } from "../api/queries";
import { FolderIcon, GearIcon, InboxIcon, PlusIcon, SearchIcon } from "../components/icons";
import { ProjectSheet, SettingsSheet } from "../components/sheets";
import { byGroup } from "../lib/projects";
import { useIsDesktop } from "../lib/useMediaQuery";

/** Phone: the screen + a tab bar. Desktop (lg+): sidebar + the screen. */
export function AppShell() {
  const desktop = useIsDesktop();
  const { pathname } = useLocation();
  // An open item is a pushed screen on the phone: it has its own bottom bar.
  const itemOpen = /^\/(inbox|search|p\/[^/]+)\/[^/]+/.test(pathname);

  if (desktop) {
    return (
      <div className="flex h-full">
        <Sidebar />
        <main className="flex min-w-0 flex-1">
          <Outlet />
        </main>
      </div>
    );
  }
  return (
    <div className="flex h-full flex-col">
      <main className="min-h-0 flex-1">
        <Outlet />
      </main>
      {itemOpen ? null : <TabBar />}
    </div>
  );
}

const tabs = [
  { to: "/inbox", label: "Inbox", icon: InboxIcon, also: /^\/inbox/ },
  { to: "/projects", label: "Projects", icon: FolderIcon, also: /^\/(projects|p\/)/ },
  { to: "/search", label: "Search", icon: SearchIcon, also: /^\/search/ },
];

function TabBar() {
  const { pathname } = useLocation();
  return (
    <nav
      aria-label="Main"
      className="border-rule bg-ground pb-safe grid shrink-0 grid-cols-3 border-t-2"
    >
      {tabs.map(({ to, label, icon: Icon, also }) => {
        const active = also.test(pathname);
        return (
          <Link
            key={to}
            to={to}
            aria-current={active ? "page" : undefined}
            className={`label -mt-[2px] flex h-[58px] flex-col items-center justify-center gap-1 border-t-4 ${
              active ? "border-accent text-text" : "text-muted border-transparent"
            }`}
          >
            <Icon />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}

function SideLink({
  to,
  children,
  count,
}: {
  to: string;
  children: React.ReactNode;
  count?: number;
}) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `flex items-center justify-between gap-2 py-2 pr-5 text-[15px] ${
          isActive ? "border-accent bg-surface border-l-4 pl-4 font-semibold" : "pl-5"
        }`
      }
    >
      <span className="truncate">{children}</span>
      {count ? <span className="text-muted font-mono text-[12px]">{count}</span> : null}
    </NavLink>
  );
}

function Sidebar() {
  const inbox = useInbox();
  const projects = useProjects();
  const groups = byGroup(projects.data ?? []);
  const [creating, setCreating] = useState(false);
  const [settings, setSettings] = useState(false);
  const unsorted = inbox.data?.length ?? 0;

  return (
    <nav
      aria-label="Projects"
      className="border-rule flex w-60 shrink-0 flex-col overflow-y-auto border-r-2 py-6"
    >
      <div className="px-5 pb-5 text-[30px] font-extrabold tracking-[-0.03em]">311</div>
      <NavLink
        to="/inbox"
        className={({ isActive }) =>
          `flex items-center justify-between py-2.5 pr-5 font-semibold ${
            isActive ? "border-accent bg-surface border-l-4 pl-4" : "pl-5"
          }`
        }
      >
        Inbox
        {unsorted ? (
          <span className="bg-accent text-on-accent px-[7px] py-[2px] font-mono text-[12px]">
            {unsorted}
          </span>
        ) : null}
      </NavLink>
      <SideLink to="/search">Search</SideLink>

      <div className="label text-muted px-5 pt-5 pb-1.5">Projects</div>
      {groups.active.map((p) => (
        <SideLink key={p.id} to={`/p/${p.id}`} count={p.open_items}>
          {p.name}
        </SideLink>
      ))}
      {groups.ideas.length ? <div className="label text-muted px-5 pt-4 pb-1.5">Ideas</div> : null}
      {groups.ideas.map((p) => (
        <SideLink key={p.id} to={`/p/${p.id}`} count={p.open_items}>
          {p.name}
        </SideLink>
      ))}

      <div className="mt-auto flex flex-col pt-6">
        <SideLink to="/projects">All projects</SideLink>
        <button
          type="button"
          onClick={() => setCreating(true)}
          className="text-muted hover:text-text flex items-center gap-2 px-5 py-2 text-left text-[15px]"
        >
          <PlusIcon size={16} /> New project
        </button>
        <button
          type="button"
          onClick={() => setSettings(true)}
          className="text-muted hover:text-text flex items-center gap-2 px-5 py-2 text-left text-[15px]"
        >
          <GearIcon size={16} /> Settings
        </button>
      </div>
      <ProjectSheet isOpen={creating} onClose={() => setCreating(false)} />
      <SettingsSheet isOpen={settings} onClose={() => setSettings(false)} />
    </nav>
  );
}
