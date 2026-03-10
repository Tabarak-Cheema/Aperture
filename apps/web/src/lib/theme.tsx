import { createContext, useContext, useEffect, useMemo, useState } from "react";

export type ThemeMode = "light" | "dark" | "system";
export type Density = "comfortable" | "compact";

const THEME_KEY = "aperture.theme";
const DENSITY_KEY = "aperture.density";

interface ThemeCtx {
  mode: ThemeMode;
  effective: "light" | "dark";
  density: Density;
  setMode: (m: ThemeMode) => void;
  setDensity: (d: Density) => void;
}

const Ctx = createContext<ThemeCtx | null>(null);

function systemPrefersDark(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setModeRaw] = useState<ThemeMode>(() => {
    const stored = typeof localStorage !== "undefined" ? localStorage.getItem(THEME_KEY) : null;
    return (stored as ThemeMode) ?? "system";
  });
  const [density, setDensityRaw] = useState<Density>(() => {
    const stored = typeof localStorage !== "undefined" ? localStorage.getItem(DENSITY_KEY) : null;
    return (stored as Density) ?? "comfortable";
  });
  const [systemDark, setSystemDark] = useState(systemPrefersDark);

  // React to OS-level theme changes while mode === "system"
  useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = (e: MediaQueryListEvent) => setSystemDark(e.matches);
    mq.addEventListener?.("change", handler);
    return () => mq.removeEventListener?.("change", handler);
  }, []);

  const effective: "light" | "dark" = mode === "system" ? (systemDark ? "dark" : "light") : mode;

  useEffect(() => {
    document.documentElement.dataset.theme = effective;
    document.documentElement.dataset.density = density;
  }, [effective, density]);

  const setMode = (m: ThemeMode) => {
    setModeRaw(m);
    localStorage.setItem(THEME_KEY, m);
  };
  const setDensity = (d: Density) => {
    setDensityRaw(d);
    localStorage.setItem(DENSITY_KEY, d);
  };

  const value = useMemo<ThemeCtx>(
    () => ({ mode, effective, density, setMode, setDensity }),
    [mode, effective, density]
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useTheme(): ThemeCtx {
  const v = useContext(Ctx);
  if (!v) throw new Error("useTheme outside ThemeProvider");
  return v;
}
