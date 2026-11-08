import { useEffect, useSyncExternalStore } from "react";

/** The theme setting (STYLE_GUIDE.md): dark by default, whatever the phone says. */
export type ThemePref = "dark" | "light" | "system";

const KEY = "311-theme"; // also read by the inline script in index.html
const GROUND = { dark: "#141413", light: "#F2F1EC" };
const LIGHT_QUERY = "(prefers-color-scheme: light)";
const listeners = new Set<() => void>();

export function readPref(): ThemePref {
  try {
    const value = localStorage.getItem(KEY);
    return value === "light" || value === "system" ? value : "dark";
  } catch {
    return "dark"; // storage blocked (private mode): the default
  }
}

export function resolve(pref: ThemePref, phonePrefersLight: boolean): "dark" | "light" {
  if (pref === "system") return phonePrefersLight ? "light" : "dark";
  return pref;
}

function apply(pref: ThemePref) {
  const theme = resolve(pref, window.matchMedia(LIGHT_QUERY).matches);
  document.documentElement.dataset.theme = theme;
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", GROUND[theme]);
}

export function setPref(pref: ThemePref) {
  try {
    localStorage.setItem(KEY, pref);
  } catch {
    // Not saved, but still applied for this visit.
  }
  apply(pref);
  listeners.forEach((l) => l());
}

/** The current setting; while it's "system", follows the phone as it changes. */
export function useThemePref(): ThemePref {
  const pref = useSyncExternalStore(
    (onChange) => {
      listeners.add(onChange);
      return () => listeners.delete(onChange);
    },
    readPref,
    () => "dark" as const,
  );
  useEffect(() => {
    if (pref !== "system") return;
    const list = window.matchMedia(LIGHT_QUERY);
    const follow = () => apply("system");
    list.addEventListener("change", follow);
    return () => list.removeEventListener("change", follow);
  }, [pref]);
  return pref;
}
