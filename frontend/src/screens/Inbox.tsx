import { useState, type FormEvent } from "react";
import { useParams } from "react-router";

import { useAddItem, useInbox } from "../api/queries";
import type { Item } from "../api/types";
import { ItemRow } from "../components/ItemRow";
import { ListDetail } from "../components/ListDetail";
import { DeleteItemSheet, MoveSheet } from "../components/sheets";
import { SwipeRow } from "../components/SwipeRow";
import { Empty, ScreenHeader, SkeletonRows } from "../components/ui";

export function InboxScreen() {
  const { itemId } = useParams();
  return (
    <ListDetail
      itemId={itemId}
      back={{ to: "/inbox", label: "Inbox" }}
      list={<InboxList selectedId={itemId} />}
    />
  );
}

function InboxList({ selectedId }: { selectedId?: string }) {
  const inbox = useInbox();
  const [moving, setMoving] = useState<Item | null>(null);
  const [deleting, setDeleting] = useState<Item | null>(null);
  const items = inbox.data ?? [];

  return (
    <>
      <ScreenHeader title="Inbox" kicker={`311 / Unsorted · ${items.length}`} />
      <CaptureForm />
      {inbox.isPending ? (
        <SkeletonRows />
      ) : items.length === 0 ? (
        <Empty>Nothing to sort. New ideas land here, from you or from Claude.</Empty>
      ) : (
        <ul className="m-0 list-none p-0">
          {items.map((item) => (
            <li key={item.id}>
              <SwipeRow
                actions={[
                  { label: "Move", onPress: () => setMoving(item) },
                  { label: "Delete", onPress: () => setDeleting(item), tone: "danger" },
                ]}
              >
                <ItemRow item={item} to={`/inbox/${item.id}`} selected={item.id === selectedId} />
              </SwipeRow>
            </li>
          ))}
        </ul>
      )}
      <MoveSheet item={moving} onClose={() => setMoving(null)} />
      <DeleteItemSheet item={deleting} onClose={() => setDeleting(null)} />
    </>
  );
}

/** Quick capture: type, hit return, it's in the inbox (shown before the server answers). */
function CaptureForm() {
  const [title, setTitle] = useState("");
  const { add } = useAddItem();
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    add({ title });
    setTitle("");
  };
  return (
    <form
      onSubmit={submit}
      className="border-hairline flex flex-col gap-2 border-b px-5 py-4 lg:px-7"
    >
      <label htmlFor="capture" className="label text-muted text-[12px]">
        Capture
      </label>
      <div className="flex gap-2">
        <input
          id="capture"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="What's the idea?"
          enterKeyHint="send"
          autoComplete="off"
          className="border-rule bg-surface text-text focus:border-accent h-12 min-w-0 flex-1 border-2 px-3.5 text-[17px] outline-none"
        />
        <button
          type="submit"
          disabled={!title.trim()}
          className="bg-accent text-on-accent h-12 px-4 text-[16px] font-semibold active:opacity-60 disabled:opacity-40"
        >
          File it
        </button>
      </div>
    </form>
  );
}
