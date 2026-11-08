import type { ReactNode } from "react";

import { useIsDesktop } from "../lib/useMediaQuery";
import { ItemPane } from "./ItemPane";

/** Phone: the list, or the open item full screen (pushed). Desktop: list and item side
 *  by side. The URL decides which item is open, so both layouts share it. */
export function ListDetail({
  list,
  itemId,
  back,
}: {
  list: ReactNode;
  itemId?: string;
  back: { to: string; label: string };
}) {
  const desktop = useIsDesktop();
  if (!desktop) {
    if (itemId) return <ItemPane key={itemId} itemId={itemId} back={back} />;
    return (
      <div className="flex h-full flex-col overflow-x-hidden overflow-y-auto overscroll-contain">
        {list}
      </div>
    );
  }
  return (
    <div className="flex min-w-0 flex-1">
      <section className="border-hairline flex min-w-0 flex-[1_1_440px] flex-col overflow-y-auto border-r">
        {list}
      </section>
      <section className="bg-surface flex min-w-0 flex-[1_1_400px] flex-col">
        {itemId ? (
          <ItemPane key={itemId} itemId={itemId} back={back} />
        ) : (
          <p className="text-muted m-auto px-8 text-center text-[15px]">
            Pick an item to see its details and log.
          </p>
        )}
      </section>
    </div>
  );
}
