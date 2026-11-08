import type { Project } from "../api/types";

/** Projects as the sidebar groups them: General first, then by name. */
export function byGroup(projects: Project[]) {
  const sorted = [...projects].sort(
    (a, b) => Number(b.is_general) - Number(a.is_general) || a.name.localeCompare(b.name),
  );
  return {
    active: sorted.filter((p) => p.state === "building" || p.state === "live"),
    ideas: sorted.filter((p) => p.state === "idea"),
    archived: sorted.filter((p) => p.state === "archived"),
  };
}
