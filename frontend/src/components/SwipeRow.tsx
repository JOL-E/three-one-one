import { animate, motion, useMotionValue } from "motion/react";
import { useRef, type ReactNode } from "react";

import { useIsDesktop } from "../lib/useMediaQuery";

export type SwipeAction = {
  label: string;
  onPress: () => void;
  tone?: "ink" | "danger";
};

const ACTION_WIDTH = 84;
const spring = { type: "spring", stiffness: 500, damping: 42 } as const;

/** iOS swipe actions: swipe a row left to reveal buttons behind it. Phone only; on
 *  desktop the same actions live in the item's detail pane. */
export function SwipeRow({ actions, children }: { actions: SwipeAction[]; children: ReactNode }) {
  const desktop = useIsDesktop();
  const x = useMotionValue(0);
  const dragged = useRef(false);
  const width = actions.length * ACTION_WIDTH;

  if (desktop || actions.length === 0) return <>{children}</>;

  const close = () => void animate(x, 0, spring);

  return (
    <div className="relative overflow-hidden">
      <div className="absolute inset-y-0 right-0 flex" style={{ width }}>
        {actions.map((a) => (
          <button
            key={a.label}
            type="button"
            tabIndex={-1}
            onClick={() => {
              close();
              a.onPress();
            }}
            className={`label flex flex-1 items-center justify-center text-[12px] ${
              a.tone === "danger" ? "bg-danger text-on-accent" : "bg-text text-ground"
            }`}
          >
            {a.label}
          </button>
        ))}
      </div>
      <motion.div
        drag="x"
        dragDirectionLock
        dragConstraints={{ left: -width, right: 0 }}
        dragElastic={{ left: 0.15, right: 0 }}
        style={{ x }}
        onDragStart={() => {
          dragged.current = true;
        }}
        onDragEnd={(_, info) => {
          const open = info.offset.x < -width / 2 || info.velocity.x < -500;
          void animate(x, open ? -width : 0, spring);
          // Let the click that ends a drag pass without opening the row.
          setTimeout(() => {
            dragged.current = false;
          }, 50);
        }}
        onClickCapture={(e) => {
          if (dragged.current || x.get() < -4) {
            e.preventDefault();
            e.stopPropagation();
            close();
          }
        }}
        className="bg-surface relative"
      >
        {children}
      </motion.div>
    </div>
  );
}
