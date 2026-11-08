import { useCallback, useEffect, type RefObject } from "react";
import { useNavigate } from "react-router";

/** iOS back: return to the previous screen, or to `fallback` when the app was opened
 *  right on this screen (nothing to go back to). */
export function useGoBack(fallback: string) {
  const navigate = useNavigate();
  return useCallback(() => {
    const idx = (window.history.state as { idx?: number } | null)?.idx ?? 0;
    if (idx > 0) void navigate(-1);
    else void navigate(fallback, { replace: true });
  }, [navigate, fallback]);
}

const EDGE = 24; // px from the left edge where the gesture may start
const THRESHOLD = 0.3; // share of the screen width that commits the swipe

/** Swipe from the left edge to go back. iOS doesn't provide this in installed web
 *  apps, so we do: the screen follows the finger and slides away past ~30%. */
export function useEdgeSwipeBack(
  screen: RefObject<HTMLElement | null>,
  onBack: () => void,
  enabled: boolean,
) {
  useEffect(() => {
    if (!enabled) return;
    let tracking = false;
    let startX = 0;
    let startY = 0;
    let dx = 0;

    const style = (transform: string, transition = "none") => {
      const node = screen.current;
      if (!node) return;
      node.style.transition = transition;
      node.style.transform = transform;
    };

    function start(e: TouchEvent) {
      const t = e.touches[0];
      if (!t || t.clientX > EDGE) return;
      tracking = true;
      startX = t.clientX;
      startY = t.clientY;
      dx = 0;
    }
    function move(e: TouchEvent) {
      const t = e.touches[0];
      if (!tracking || !t) return;
      dx = Math.max(0, t.clientX - startX);
      // Mostly vertical: it's a scroll, not a back swipe.
      if (dx < 16 && Math.abs(t.clientY - startY) > 24) {
        tracking = false;
        style("");
        return;
      }
      style(`translateX(${dx}px)`);
    }
    function end() {
      if (!tracking) return;
      tracking = false;
      if (dx > window.innerWidth * THRESHOLD) {
        style("translateX(100%)", "transform 180ms ease-out");
        setTimeout(() => {
          onBack();
          style("");
        }, 170);
      } else {
        style("", "transform 220ms cubic-bezier(0.32, 0.72, 0, 1)");
      }
    }

    window.addEventListener("touchstart", start, { passive: true });
    window.addEventListener("touchmove", move, { passive: true });
    window.addEventListener("touchend", end);
    window.addEventListener("touchcancel", end);
    return () => {
      window.removeEventListener("touchstart", start);
      window.removeEventListener("touchmove", move);
      window.removeEventListener("touchend", end);
      window.removeEventListener("touchcancel", end);
    };
  }, [screen, onBack, enabled]);
}
