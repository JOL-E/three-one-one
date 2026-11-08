import { useRef, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";

import { useAddComment, useItem, useProjectItems, useProjects, useSetOrder } from "../api/queries";
import type { Activity, Item, ItemDetail, ItemStatus } from "../api/types";
import { day, rank } from "../lib/format";
import { useEdgeSwipeBack, useGoBack } from "../lib/navigation";
import { useIsDesktop } from "../lib/useMediaQuery";
import { BackIcon, MoreIcon } from "./icons";
import { ActionMenu } from "./Menu";
import { DeleteItemSheet, EditItemSheet, MoveSheet, StatusSheet } from "./sheets";
import { Button, ShortId, Stamp } from "./ui";

/** One item: details, what can happen next, its log, and a comment bar. */
export function ItemPane({
  itemId,
  back,
}: {
  itemId: string;
  back: { to: string; label: string };
}) {
  const desktop = useIsDesktop();
  const query = useItem(itemId);
  const goBack = useGoBack(back.to);
  const navigate = useNavigate();
  const screen = useRef<HTMLDivElement>(null);
  useEdgeSwipeBack(screen, goBack, !desktop);

  const [moving, setMoving] = useState(false);
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [statusTo, setStatusTo] = useState<ItemStatus | null>(null);
  const item = query.data;

  return (
    <div
      ref={screen}
      className={`bg-surface flex h-full min-h-0 flex-col ${desktop ? "" : "animate-push-in"}`}
    >
      <div className="pt-edge flex shrink-0 items-center justify-between px-2 lg:px-4 lg:pt-3">
        {desktop ? (
          <span />
        ) : (
          <button
            type="button"
            onClick={goBack}
            className="text-accent inline-flex h-11 items-center gap-1 px-2 text-[17px] active:opacity-50"
          >
            <BackIcon size={20} />
            {back.label}
          </button>
        )}
        {item ? (
          <ActionMenu
            label="More actions"
            className="text-text flex h-11 w-11 items-center justify-center"
            trigger={<MoreIcon />}
            actions={[
              { label: "Edit", onAction: () => setEditing(true) },
              { label: "Move to…", onAction: () => setMoving(true) },
              { label: "Delete", onAction: () => setDeleting(true), danger: true },
            ]}
          />
        ) : null}
      </div>

      {query.isError ? (
        <p className="text-muted px-5 py-10 text-center">This item doesn't exist (any more).</p>
      ) : !item ? (
        <div className="px-5 py-6" aria-hidden="true">
          <div className="bg-hairline animate-shimmer mb-4 h-4 w-16" />
          <div className="bg-hairline animate-shimmer h-7 w-3/4" />
        </div>
      ) : (
        <>
          <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
            <Header item={item} />
            <div className="flex flex-col gap-5 px-5 py-5 lg:px-7">
              <Actions item={item} onStatus={setStatusTo} onMove={() => setMoving(true)} />
              <Priority item={item} />
              <Log activity={item.activity} />
            </div>
          </div>
          <CommentBar itemId={item.id} />
          <MoveSheet item={moving ? item : null} onClose={() => setMoving(false)} />
          <StatusSheet item={item} to={statusTo} onClose={() => setStatusTo(null)} />
          <EditItemSheet
            key={`${item.updated_at}-${editing}`}
            item={item}
            isOpen={editing}
            onClose={() => setEditing(false)}
          />
          <DeleteItemSheet
            item={deleting ? item : null}
            onClose={() => setDeleting(false)}
            onDeleted={() => void navigate(back.to, { replace: true })}
          />
        </>
      )}
    </div>
  );
}

function Header({ item }: { item: ItemDetail }) {
  const projects = useProjects(true);
  const project = projects.data?.find((p) => p.id === item.project_id);
  return (
    <header className="border-rule flex flex-col gap-2.5 border-b-2 px-5 pt-2 pb-4 lg:px-7">
      <div className="flex items-center gap-2.5">
        <ShortId id={item.short_id} />
        <Stamp status={item.status} />
        {item.status === "done" ? <span className="label text-muted">Closed</span> : null}
        <span className="label text-muted ml-auto truncate">
          {project ? (
            <Link to={`/p/${project.id}`} className="hover:text-text">
              {project.name}
            </Link>
          ) : (
            "Inbox"
          )}
        </span>
      </div>
      <h1 className="m-0 text-[26px] leading-tight font-extrabold tracking-[-0.01em] break-words">
        {item.title}
      </h1>
      {item.details ? (
        <p className="text-text-2 m-0 text-[16px] leading-relaxed whitespace-pre-wrap">
          {item.details}
        </p>
      ) : null}
    </header>
  );
}

/** What can happen next depends on where the item is. Status changes ask why. */
function Actions({
  item,
  onStatus,
  onMove,
}: {
  item: Item;
  onStatus: (to: ItemStatus) => void;
  onMove: () => void;
}) {
  if (!item.project_id) {
    return (
      <Button tone="ink" onClick={onMove} className="self-start">
        Move to a project
      </Button>
    );
  }
  const next: { to: ItemStatus; label: string; tone: "ink" | "outline" }[] =
    item.status === "open"
      ? [
          { to: "doing", label: "Start", tone: "ink" },
          { to: "done", label: "Mark done", tone: "outline" },
        ]
      : item.status === "doing"
        ? [
            { to: "done", label: "Mark done", tone: "ink" },
            { to: "open", label: "Back to open", tone: "outline" },
          ]
        : [{ to: "open", label: "Reopen", tone: "outline" }];
  return (
    <div className="flex flex-wrap gap-2">
      {next.map((n) => (
        <Button key={n.to} tone={n.tone} onClick={() => onStatus(n.to)}>
          {n.label}
        </Button>
      ))}
    </div>
  );
}

/** Rank within the project, with buttons: the keyboard-friendly way to reorder (DECISIONS #39). */
function Priority({ item }: { item: Item }) {
  const ranked = item.project_id !== null && item.status !== "done";
  const items = useProjectItems(ranked ? item.project_id : null);
  const setOrder = useSetOrder(item.project_id ?? "");
  if (!ranked || !items.data) return null;
  const order = items.data.filter((i) => i.status !== "done").map((i) => i.id);
  const at = order.indexOf(item.id);
  if (at < 0) return null;
  const moveTo = (to: number) => {
    const next = order.filter((id) => id !== item.id);
    next.splice(Math.max(0, Math.min(to, next.length)), 0, item.id);
    setOrder.mutate(next);
  };
  const small = "h-9 px-3 text-[11px]";
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="label text-muted mr-2">
        Priority <span className="text-text">{rank(at)}</span> / {rank(order.length - 1)}
      </span>
      <Button className={small} disabled={at === 0} onClick={() => moveTo(0)}>
        Top
      </Button>
      <Button className={small} disabled={at === 0} onClick={() => moveTo(at - 1)}>
        Up
      </Button>
      <Button className={small} disabled={at === order.length - 1} onClick={() => moveTo(at + 1)}>
        Down
      </Button>
    </div>
  );
}

function what(a: Activity): string {
  switch (a.kind) {
    case "created":
      return "Filed";
    case "comment":
      return "Comment";
    case "status":
    case "moved":
      return `${a.old_value} → ${a.new_value}`;
  }
}

/** The activity log, newest first: date, who · what, and the comment. */
function Log({ activity }: { activity: Activity[] }) {
  return (
    <section className="flex flex-col">
      <h2 className="label text-muted m-0 mb-2">Log</h2>
      <ol className="m-0 list-none p-0">
        {[...activity].reverse().map((a) => (
          <li
            key={a.id}
            className="border-hairline grid grid-cols-[64px_minmax(0,1fr)] gap-x-3 border-t py-2.5"
          >
            <time dateTime={a.created_at} className="text-muted font-mono text-[12px] uppercase">
              {day(a.created_at)}
            </time>
            <div className="flex min-w-0 flex-col gap-1">
              <span className="label tracking-[0.06em]">
                <span className={a.author === "claude" ? "text-accent" : ""}>
                  {a.author === "claude" ? "Claude" : "Me"}
                </span>{" "}
                · {what(a)}
              </span>
              {a.text ? (
                <span className="text-[15px] leading-snug whitespace-pre-wrap">{a.text}</span>
              ) : null}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

function CommentBar({ itemId }: { itemId: string }) {
  const [text, setText] = useState("");
  const comment = useAddComment(itemId);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    comment.mutate(text, { onSuccess: () => setText("") });
  };
  return (
    <form onSubmit={submit} className="border-rule bg-ground pb-safe shrink-0 border-t-2">
      <div className="flex gap-2 px-5 pt-3 pb-3 lg:px-7">
        <label htmlFor={`comment-${itemId}`} className="sr-only">
          Comment
        </label>
        <input
          id={`comment-${itemId}`}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Add to the log…"
          className="border-rule bg-surface text-text focus:border-accent h-11 min-w-0 flex-1 border-2 px-3 outline-none"
        />
        <Button type="submit" tone="ink" disabled={!text.trim() || comment.isPending}>
          Log
        </Button>
      </div>
    </form>
  );
}
