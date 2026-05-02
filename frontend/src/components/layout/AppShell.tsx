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
    <div className="flex h-screen overflow-hidden">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex md:w-48 md:flex-col md:border-r md:border-gray-200 md:bg-gray-50">
        <div className="p-4 text-lg font-bold">CompSynth</div>
        <nav className="flex flex-col gap-1 px-2">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `rounded px-3 py-2 text-sm ${
                  isActive
                    ? "bg-gray-200 font-medium"
                    : "text-gray-700 hover:bg-gray-100"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      {/* Mobile top bar */}
      <div className="flex md:hidden fixed top-0 inset-x-0 z-30 border-b border-gray-200 bg-white px-4 py-3">
        <button
          onClick={() => setMobileOpen(true)}
          className="text-gray-700"
          aria-label="Open menu"
        >
          ☰
        </button>
        <span className="ml-3 font-bold">CompSynth</span>
      </div>

      {/* Mobile drawer overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 md:hidden"
          onClick={() => setMobileOpen(false)}
        >
          <div className="absolute inset-0 bg-black/30" />
          <aside
            className="relative w-56 bg-white p-4 shadow-lg"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 text-lg font-bold">CompSynth</div>
            <nav className="flex flex-col gap-1">
              {NAV_ITEMS.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  onClick={() => setMobileOpen(false)}
                  className={({ isActive }) =>
                    `rounded px-3 py-2 text-sm ${
                      isActive
                        ? "bg-gray-200 font-medium"
                        : "text-gray-700 hover:bg-gray-100"
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
      <main className="flex-1 overflow-auto pt-14 md:pt-0">
        <Outlet />
      </main>
    </div>
  );
}
