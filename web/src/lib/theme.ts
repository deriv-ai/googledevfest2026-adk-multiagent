import { useCallback, useEffect, useSyncExternalStore } from "react";

export type ThemePref = "light" | "dark" | "system";
const KEY = "nimbus-theme";
const listeners = new Set<() => void>();

function readPref(): ThemePref {
  try {
    const v = localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

function systemDark(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function apply(pref: ThemePref) {
  const dark = pref === "dark" || (pref === "system" && systemDark());
  document.documentElement.classList.toggle("dark", dark);
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  const onSys = () => {
    if (readPref() === "system") apply("system");
    cb();
  };
  mq.addEventListener("change", onSys);
  return () => {
    listeners.delete(cb);
    mq.removeEventListener("change", onSys);
  };
}

const snapshot = () => `${readPref()}:${document.documentElement.classList.contains("dark") ? "dark" : "light"}`;

export function useTheme() {
  const snap = useSyncExternalStore(subscribe, snapshot, () => "system:light");
  const [pref, resolved] = snap.split(":") as [ThemePref, "light" | "dark"];
  useEffect(() => apply(pref), [pref]);
  const setPref = useCallback((p: ThemePref) => {
    try {
      if (p === "system") localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, p);
    } catch {
      /* private mode */
    }
    apply(p);
    listeners.forEach((l) => l());
  }, []);
  return { pref, resolved, setPref };
}
