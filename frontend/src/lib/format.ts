/** A new item's short id before the server has computed the real one (DECISIONS #40).
 *  Usually identical; the server's answer replaces it either way. */
export function shortIdOf(id: string): string {
  return id.replaceAll("-", "").slice(0, 4).toUpperCase();
}

/** Priority rank as shown: 0 → "01". */
export function rank(position: number): string {
  return String(position + 1).padStart(2, "0");
}

const DAY = 24 * 60 * 60 * 1000;

/** "just now", "2h ago", "yesterday", "3d ago", then a date ("Nov 2"). Labels upper-case it. */
export function ago(iso: string, now: Date = new Date()): string {
  const then = new Date(iso);
  const ms = now.getTime() - then.getTime();
  if (ms < 60_000) return "just now";
  if (ms < 60 * 60_000) return `${Math.floor(ms / 60_000)}m ago`;
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  if (then.getTime() >= startOfToday) return `${Math.floor(ms / (60 * 60_000))}h ago`;
  if (then.getTime() >= startOfToday - DAY) return "yesterday";
  const days = Math.ceil((startOfToday - then.getTime()) / DAY);
  if (days < 7) return `${days}d ago`;
  return day(iso);
}

/** "Nov 06", the log's date column. */
export function day(iso: string): string {
  const d = new Date(iso);
  const month = d.toLocaleString("en-US", { month: "short" });
  return `${month} ${String(d.getDate()).padStart(2, "0")}`;
}
