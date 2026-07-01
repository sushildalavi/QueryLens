import { Link, useLocation } from "react-router-dom";
import { Activity, AlertTriangle, Github, LayoutGrid } from "lucide-react";
import { useEffect, useState } from "react";
import { CommandPalette } from "./CommandPalette";

function LivePulse() {
  return (
    <span className="relative inline-grid place-items-center w-2 h-2">
      <span className="absolute inset-0 rounded-full bg-ok animate-pulse-ring" />
      <span className="relative w-1.5 h-1.5 rounded-full bg-ok" />
    </span>
  );
}

export function Layout({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation();
  const [now, setNow] = useState<string>("");

  useEffect(() => {
    const tick = () => {
      const d = new Date();
      setNow(
        d.toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: false,
        })
      );
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  const isActive = (to: string) =>
    pathname === to || (to !== "/" && pathname.startsWith(to));

  const navItem = (to: string, label: string, Icon: typeof Activity) => (
    <Link
      to={to}
      className={`group inline-flex items-center gap-2 px-3 py-1.5 rounded-md text-sm transition-all duration-200 ${
        isActive(to)
          ? "bg-panel-2 text-primary ring-1 ring-edge"
          : "text-secondary hover:text-primary hover:bg-panel-2/60"
      }`}
    >
      <Icon
        size={14}
        strokeWidth={2}
        className={`transition-colors ${
          isActive(to) ? "text-accent" : "text-muted group-hover:text-secondary"
        }`}
      />
      {label}
    </Link>
  );

  return (
    <div className="min-h-screen flex flex-col">
      <header className="sticky top-0 z-20 glass-header border-b border-edge animate-slide-down">
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center gap-8">
          <Link to="/" className="flex items-center gap-2.5 group">
            <span className="relative grid place-items-center w-7 h-7 rounded-md bg-gradient-to-br from-accent/20 to-accent/0 ring-1 ring-accent/30 transition-all group-hover:ring-accent/60 group-hover:shadow-glow-soft">
              <span className="font-mono font-bold text-accent text-[11px] tracking-tighter">
                PT
              </span>
            </span>
            <span className="font-display text-sm font-semibold text-primary tracking-tightest">
              PlanTrace
            </span>
            <span className="hidden sm:inline-block text-2xs text-muted font-mono uppercase tracking-widest">
              postgres
            </span>
          </Link>
          <nav className="flex gap-1">
            {navItem("/", "Overview", Activity)}
            {navItem("/regressions", "Regressions", AlertTriangle)}
            {navItem("/placement", "Placement", LayoutGrid)}
          </nav>
          <div className="ml-auto hidden sm:flex items-center gap-4 text-2xs text-muted font-mono">
            <CommandPalette />
            <span className="inline-flex items-center gap-2">
              <LivePulse />
              <span>live</span>
            </span>
            <span className="num text-secondary">{now}</span>
            <a
              href="https://github.com/sushildalavi/plantrace"
              target="_blank"
              rel="noreferrer"
              className="grid place-items-center w-7 h-7 rounded-md ring-1 ring-edge hover:ring-edge-bright hover:bg-panel-2 transition-colors"
              aria-label="github"
            >
              <Github size={13} className="text-secondary" />
            </a>
          </div>
        </div>
      </header>
      <main className="flex-1 max-w-7xl mx-auto w-full px-6 py-8 animate-fade-in">
        {children}
      </main>
      <footer className="border-t border-edge text-2xs text-muted py-4 px-6 mt-8">
        <div className="max-w-7xl mx-auto flex items-center justify-between font-mono">
          <span>plantrace · pg_stat_statements + EXPLAIN JSON</span>
          <span className="hidden sm:inline">deterministic regression rules</span>
        </div>
      </footer>
    </div>
  );
}
