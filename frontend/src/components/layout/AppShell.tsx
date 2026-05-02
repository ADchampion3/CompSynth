import { Outlet, NavLink } from "react-router-dom";
import { useState, useEffect, useRef, useCallback } from "react";
import { useTheme } from "../../lib/theme";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard" },
  { to: "/inbox", label: "Inbox" },
  { to: "/reports", label: "Reports" },
  { to: "/sources", label: "Sources" },
];

function ThemeToggle() {
  const { resolved, toggle } = useTheme();
  return (
    <button
      onClick={toggle}
      className="p-2.5 rounded-md text-ink-3 hover:text-ink hover:bg-paper-2 transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center"
      aria-label={resolved === "dark" ? "Switch to light mode" : "Switch to dark mode"}
    >
      {resolved === "dark" ? (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
          <circle cx="12" cy="12" r="5" />
          <line x1="12" y1="1" x2="12" y2="3" />
          <line x1="12" y1="21" x2="12" y2="23" />
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
          <line x1="1" y1="12" x2="3" y2="12" />
          <line x1="21" y1="12" x2="23" y2="12" />
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
        </svg>
      ) : (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
        </svg>
      )}
    </button>
  );
}

export default function AppShell() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const drawerRef = useRef<HTMLElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  const closeDrawer = useCallback(() => setMobileOpen(false), []);

  // Focus trap + Escape key for mobile drawer
  useEffect(() => {
    if (!mobileOpen) return;

    const drawer = drawerRef.current;
    if (!drawer) return;

    // Focus the first nav link inside drawer
    const firstLink = drawer.querySelector<HTMLElement>("a, button");
    firstLink?.focus();

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        closeDrawer();
        triggerRef.current?.focus();
        return;
      }
      if (e.key !== "Tab") return;

      const focusable = drawer.querySelectorAll<HTMLElement>(
        'a[href], button, [tabindex]:not([tabindex="-1"])',
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [mobileOpen, closeDrawer]);

  return (
    <div className="flex flex-col h-screen">
      {/* Skip-to-content link */}
      <a href="#main" className="skip-link">
        Skip to content
      </a>

      {/* Top bar */}
      <header className="shrink-0 border-b border-rule bg-paper">
        <div className="flex items-center justify-between px-5 py-3 md:px-8 md:py-4">
          <NavLink
            to="/"
            className="font-display text-xl md:text-2xl font-bold text-ink tracking-tight"
          >
            CompSynth
          </NavLink>

          {/* Desktop nav + theme toggle */}
          <div className="hidden md:flex items-center gap-4">
            <nav className="flex items-baseline gap-6" aria-label="Main navigation">
              {NAV_ITEMS.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  className={({ isActive }) =>
                    `text-[0.8125rem] tracking-wide uppercase ${
                      isActive
                        ? "text-accent font-semibold"
                        : "text-ink-3 font-medium hover:text-ink"
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
            <ThemeToggle />
          </div>

          {/* Mobile: theme toggle + menu button */}
          <div className="flex items-center gap-1 md:hidden">
            <ThemeToggle />
            <button
              ref={triggerRef}
              onClick={() => setMobileOpen(true)}
              className="text-ink-3 p-2.5 min-h-[44px] min-w-[44px] flex items-center justify-center rounded-md hover:bg-paper-2 transition-colors"
              aria-label="Open menu"
            >
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
                <line x1="3" y1="5" x2="17" y2="5" />
                <line x1="3" y1="10" x2="17" y2="10" />
                <line x1="3" y1="15" x2="17" y2="15" />
              </svg>
            </button>
          </div>
        </div>
      </header>

      {/* Mobile drawer — always rendered, animated via CSS */}
      <div
        className={`fixed inset-0 z-50 md:hidden ${
          mobileOpen ? "pointer-events-auto" : "pointer-events-none"
        }`}
        aria-hidden={!mobileOpen}
      >
        <div
          className={`drawer-backdrop absolute inset-0 bg-ink/20 ${
            mobileOpen ? "opacity-100" : "opacity-0"
          }`}
          onClick={closeDrawer}
        />
        <aside
          ref={drawerRef}
          role="dialog"
          aria-modal="true"
          aria-label="Navigation menu"
          className={`drawer-panel absolute right-0 top-0 bottom-0 w-64 bg-paper p-6 shadow-lg ${
            mobileOpen ? "translate-x-0" : "translate-x-full"
          }`}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center justify-between mb-8">
            <span className="font-display text-lg font-bold text-ink">
              CompSynth
            </span>
            <button
              onClick={closeDrawer}
              className="text-ink-3 p-2 min-h-[44px] min-w-[44px] flex items-center justify-center rounded-md hover:bg-paper-2 transition-colors"
              aria-label="Close menu"
              tabIndex={mobileOpen ? 0 : -1}
            >
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5">
                <line x1="3" y1="3" x2="15" y2="15" />
                <line x1="15" y1="3" x2="3" y2="15" />
              </svg>
            </button>
          </div>
          <nav className="flex flex-col gap-4" aria-label="Mobile navigation">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                tabIndex={mobileOpen ? 0 : -1}
                onClick={closeDrawer}
                className={({ isActive }) =>
                  `text-sm tracking-wide uppercase py-2 ${
                    isActive
                      ? "text-accent font-semibold"
                      : "text-ink-3 font-medium hover:text-ink"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </aside>
      </div>

      {/* Main content */}
      <main id="main" className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
