import { useCallback } from "react";
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
