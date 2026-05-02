import { Outlet, NavLink } from "react-router-dom";
import { useState } from "react";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard" },
  { to: "/inbox", label: "Inbox" },
  { to: "/reports", label: "Reports" },
  { to: "/sources", label: "Sources" },
];

export default function AppShell() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex flex-col h-screen">
      {/* Top bar */}
      <header className="shrink-0 border-b border-rule bg-paper">
        <div className="flex items-baseline justify-between px-5 py-3 md:px-8 md:py-4">
          <NavLink
            to="/"
            className="font-display text-xl md:text-2xl font-bold text-ink tracking-tight"
          >
            CompSynth
          </NavLink>

          {/* Desktop nav */}
          <nav className="hidden md:flex items-baseline gap-6">
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

          {/* Mobile menu button */}
          <button
            onClick={() => setMobileOpen(true)}
            className="md:hidden text-ink-3 p-1 -mr-1"
            aria-label="Open menu"
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
              <line x1="3" y1="5" x2="17" y2="5" />
              <line x1="3" y1="10" x2="17" y2="10" />
              <line x1="3" y1="15" x2="17" y2="15" />
            </svg>
          </button>
        </div>
      </header>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-50 md:hidden"
          onClick={() => setMobileOpen(false)}
        >
          <div className="absolute inset-0 bg-ink/20" />
          <aside
            className="absolute right-0 top-0 bottom-0 w-64 bg-paper p-6 shadow-lg"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-baseline justify-between mb-8">
              <span className="font-display text-lg font-bold text-ink">
                CompSynth
              </span>
              <button
                onClick={() => setMobileOpen(false)}
                className="text-ink-3 p-1"
                aria-label="Close menu"
              >
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <line x1="3" y1="3" x2="15" y2="15" />
                  <line x1="15" y1="3" x2="3" y2="15" />
                </svg>
              </button>
            </div>
            <nav className="flex flex-col gap-4">
              {NAV_ITEMS.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  onClick={() => setMobileOpen(false)}
                  className={({ isActive }) =>
                    `text-sm tracking-wide uppercase ${
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
      )}

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
