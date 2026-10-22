import { Link, Outlet } from "@tanstack/react-router";
import { BarChart3, CalendarDays, Inbox, Moon, Radio, Stethoscope, Sun, Users } from "lucide-react";
import { Suspense, useEffect } from "react";

import { Button } from "@/components/ui/button";
import { Toaster } from "@/components/ui/sonner";
import { useHealth } from "@/features/inbox/hooks";
import { cn } from "@/lib/utils";

import { useUiStore } from "./stores/ui";

const NAV = [
  { to: "/", label: "Live console", icon: Radio },
  { to: "/inbox", label: "Inbox", icon: Inbox },
  { to: "/queues", label: "Staff queues", icon: Users },
  { to: "/schedule", label: "Schedule", icon: CalendarDays },
  { to: "/eval", label: "Evaluation", icon: BarChart3 },
] as const;

function ModelStatus() {
  const health = useHealth();
  if (!health.data) return null;
  const ok = health.data.llm_configured;
  return (
    <p role="status" className="flex items-center gap-2 text-xs text-muted-foreground">
      <span aria-hidden className={cn("size-2 rounded-full", ok ? "bg-success" : "bg-warning")} />
      {ok ? (health.data.model ?? "model") : "No API key: safety floor only"}
    </p>
  );
}

/** RootLayout: sidebar navigation on wide screens, a top bar on phones, then the routed page. */
export function RootLayout() {
  const theme = useUiStore((s) => s.theme);
  const toggleTheme = useUiStore((s) => s.toggleTheme);

  // Synchronise the theme class on <html>, which lives outside React.
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);

  return (
    <div className="min-h-svh bg-background text-foreground md:flex">
      <aside className="border-b bg-sidebar text-sidebar-foreground md:sticky md:top-0 md:flex md:h-svh md:w-60 md:shrink-0 md:flex-col md:border-r md:border-b-0">
        <div className="flex items-center gap-2 px-4 py-4">
          <span className="flex size-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <Stethoscope aria-hidden className="size-4" />
          </span>
          <div className="leading-tight">
            <p className="text-sm font-semibold">Maplewood</p>
            <p className="text-xs text-muted-foreground">Inbox agent console</p>
          </div>
        </div>
        <nav aria-label="Main" className="flex gap-1 overflow-x-auto px-2 pb-2 md:flex-col md:pb-0">
          {NAV.map(({ to, label, icon: Icon }) => (
            <Link
              key={to}
              to={to}
              activeOptions={{ exact: to === "/", includeSearch: false }}
              className="flex shrink-0 items-center gap-2 rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:ring-2 focus-visible:ring-sidebar-ring focus-visible:outline-none data-[status=active]:bg-sidebar-accent data-[status=active]:font-medium data-[status=active]:text-sidebar-accent-foreground"
            >
              <Icon aria-hidden className="size-4" />
              {label}
            </Link>
          ))}
        </nav>
        <div className="hidden space-y-3 border-t px-4 py-4 md:mt-auto md:block">
          <ModelStatus />
          <p className="text-xs text-muted-foreground">
            Clinic today: Mon 9 Nov 2026 (fixed). Synthetic data only.
          </p>
          <Button
            variant="ghost"
            size="sm"
            onClick={toggleTheme}
            aria-label={theme === "light" ? "Switch to dark theme" : "Switch to light theme"}
          >
            {theme === "light" ? <Moon aria-hidden /> : <Sun aria-hidden />}
            {theme === "light" ? "Dark" : "Light"}
          </Button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 px-4 py-6 md:px-8">
        <Suspense
          fallback={
            <p role="status" aria-live="polite" className="text-muted-foreground">
              Loading
            </p>
          }
        >
          <Outlet />
        </Suspense>
      </main>
      <Toaster theme={theme} richColors closeButton />
    </div>
  );
}
