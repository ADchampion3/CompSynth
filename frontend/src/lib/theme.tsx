import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";

type ResolvedTheme = "light" | "dark";

const STORAGE_KEY = "compsynth-theme";

function getSystemPreference(): ResolvedTheme {
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

function applyTheme(resolved: ResolvedTheme) {
  const root = document.documentElement;
  root.classList.toggle("dark", resolved === "dark");
  root.classList.toggle("light", resolved === "light");
}

interface ThemeContextValue {
  resolved: ResolvedTheme;
  toggle: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [resolved, setResolved] = useState<ResolvedTheme>(() => {
    const stored = localStorage.getItem(STORAGE_KEY) as ResolvedTheme | null;
    return stored ?? getSystemPreference();
  });

  useEffect(() => {
    applyTheme(resolved);
    localStorage.setItem(STORAGE_KEY, resolved);
  }, [resolved]);

  // Follow system preference changes when no stored override exists
  useEffect(() => {
    if (localStorage.getItem(STORAGE_KEY)) return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => setResolved(getSystemPreference());
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  const toggle = useCallback(
    () => setResolved((prev) => (prev === "dark" ? "light" : "dark")),
    [],
  );

  return (
    <ThemeContext.Provider value={{ resolved, toggle }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}
