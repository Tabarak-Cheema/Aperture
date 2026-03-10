import { useTheme } from "../lib/theme";

const next: Record<string, "light" | "dark" | "system"> = {
  light: "dark",
  dark: "system",
  system: "light",
};

const label = { light: "Light", dark: "Dark", system: "Auto" } as const;

export default function ThemeToggle() {
  const { mode, setMode } = useTheme();
  return (
    <button
      className="icon-btn"
      onClick={() => setMode(next[mode])}
      aria-label={`Theme: ${label[mode]}. Click to change.`}
      title={`Theme: ${label[mode]}`}
    >
      {mode === "light" && <IconSun />}
      {mode === "dark" && <IconMoon />}
      {mode === "system" && <IconMonitor />}
    </button>
  );
}

function IconSun() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden>
      <circle cx="12" cy="12" r="4" fill="currentColor" />
      <g stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <line x1="12" y1="2" x2="12" y2="5" />
        <line x1="12" y1="19" x2="12" y2="22" />
        <line x1="2" y1="12" x2="5" y2="12" />
        <line x1="19" y1="12" x2="22" y2="12" />
        <line x1="4.9" y1="4.9" x2="7" y2="7" />
        <line x1="17" y1="17" x2="19.1" y2="19.1" />
        <line x1="4.9" y1="19.1" x2="7" y2="17" />
        <line x1="17" y1="7" x2="19.1" y2="4.9" />
      </g>
    </svg>
  );
}
function IconMoon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden>
      <path fill="currentColor" d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
    </svg>
  );
}
function IconMonitor() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden>
      <rect x="2" y="4" width="20" height="13" rx="2" fill="none" stroke="currentColor" strokeWidth="2" />
      <path d="M8 21h8M12 17v4" stroke="currentColor" strokeWidth="2" />
    </svg>
  );
}
