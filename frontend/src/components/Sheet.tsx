import { motion, useDragControls } from "motion/react";
import type { ReactNode } from "react";
import { Dialog, Heading, Modal, ModalOverlay } from "react-aria-components";

import { useIsDesktop } from "../lib/useMediaQuery";

/** Phone: a bottom sheet that slides up; drag the top bar down or tap outside to close.
 *  Desktop: a centered dialog. Square, set apart by a strong rule (STYLE_GUIDE.md).
 *  React Aria handles focus trapping, Escape and screen readers. */
export function Sheet({
  isOpen,
  onClose,
  title,
  children,
}: {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  const desktop = useIsDesktop();
  // Only the top bar drags the sheet, so lists inside it still scroll on touch.
  const drag = useDragControls();
  const body = (
    <Dialog className="flex max-h-[inherit] flex-col outline-none">
      <div
        onPointerDown={desktop ? undefined : (e) => drag.start(e)}
        className="border-hairline flex shrink-0 touch-none items-center justify-between border-b px-5 pt-4 pb-3"
      >
        <Heading slot="title" className="label text-muted m-0">
          {title}
        </Heading>
        <button
          type="button"
          onClick={onClose}
          className="label text-text -mr-3 px-3 py-2 active:opacity-50"
        >
          Close
        </button>
      </div>
      <div className="overflow-y-auto overscroll-contain px-5 pt-4 pb-6">{children}</div>
    </Dialog>
  );

  return (
    <ModalOverlay
      isOpen={isOpen}
      onOpenChange={(open) => !open && onClose()}
      isDismissable
      className="data-[entering]:animate-fade-in data-[exiting]:animate-fade-out fixed inset-0 z-50 h-[var(--visual-viewport-height,100%)] bg-black/50 lg:flex lg:items-center lg:justify-center"
    >
      {desktop ? (
        <Modal className="data-[entering]:animate-fade-in bg-ground border-rule max-h-[85vh] w-full max-w-lg overflow-hidden border-2 outline-none">
          {body}
        </Modal>
      ) : (
        <Modal className="data-[entering]:animate-sheet-in data-[exiting]:animate-sheet-out absolute inset-x-0 bottom-0 outline-none">
          <motion.div
            drag="y"
            dragControls={drag}
            dragListener={false}
            dragConstraints={{ top: 0, bottom: 0 }}
            dragElastic={{ top: 0, bottom: 0.7 }}
            onDragEnd={(_, info) => {
              if (info.offset.y > 120 || info.velocity.y > 600) onClose();
            }}
            className="bg-ground border-rule pb-safe flex max-h-[calc(var(--visual-viewport-height,100vh)*0.92)] flex-col border-t-2"
          >
            {body}
          </motion.div>
        </Modal>
      )}
    </ModalOverlay>
  );
}
