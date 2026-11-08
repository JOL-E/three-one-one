import { Link } from "react-router";

import type { Item } from "../api/types";
import { ago } from "../lib/format";
import { Stamp, ShortId } from "./ui";

/** One item in a list: short id, title, a meta line. Selected = open in the detail pane. */
export function ItemRow({
  item,
  to,
  selected = false,
  meta,
}: {
  item: Item;
  to: string;
  selected?: boolean;
  meta?: string;
}) {
  const done = item.status === "done";
  const who = item.created_by === "claude" ? "Claude" : "me";
  return (
    <Link
      to={to}
      aria-current={selected ? "true" : undefined}
      className={`bg-surface border-hairline flex items-start gap-3.5 border-b px-5 py-3.5 lg:px-7 ${
        selected ? "outline-text outline-2 -outline-offset-2" : ""
      }`}
    >
      <ShortId id={item.short_id} className={`pt-[3px] ${done ? "text-muted" : ""}`} />
      <span className="flex min-w-0 flex-1 flex-col gap-1">
        <span className={`text-[17px] font-medium ${done ? "text-muted line-through" : ""}`}>
          {item.title}
        </span>
        <span className="label text-muted font-normal tracking-[0.06em]">
          {meta ?? (
            <>
              Filed by{" "}
              <span className={item.created_by === "claude" ? "text-accent" : ""}>{who}</span> ·{" "}
              {ago(item.created_at)}
            </>
          )}
        </span>
      </span>
      <Stamp status={item.status} />
    </Link>
  );
}
