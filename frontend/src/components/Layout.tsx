import { NavLink, Outlet } from "react-router-dom";
import clsx from "clsx";

const navItems = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/groups", label: "Groups" },
  { to: "/analytics", label: "Analytics" },
  { to: "/import", label: "Import" },
];

export default function Layout() {
  return (
    <div className="noise-bg min-h-screen flex flex-col relative">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[100] focus:p-2 focus:bg-accent focus:text-white focus:rounded-md focus:text-sm"
      >
        Skip to main content
      </a>

      <header className="sticky top-0 z-40 border-b border-[--color-border] bg-[--color-bg-surface]/80 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14">
            <NavLink
              to="/"
              className="font-display text-xl text-[--color-text-primary] tracking-tight focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-[--color-bg-surface] focus-visible:outline-none rounded"
            >
              Trading Records
            </NavLink>
            <nav className="flex items-center gap-1">
              {navItems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    clsx(
                      "px-3 py-1.5 rounded-md text-sm font-medium transition-all duration-200 focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none",
                      isActive
                        ? "bg-accent/15 text-accent-hover"
                        : "text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-bg-hover]"
                    )
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
          </div>
        </div>
      </header>

      <main id="main-content" className="relative z-10 flex-1 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 w-full">
        <Outlet />
      </main>

      <footer className="relative z-10 border-t border-[--color-border] py-3 text-center text-xs text-[--color-text-muted]">
        Trading Records v0.1.0
      </footer>
    </div>
  );
}
