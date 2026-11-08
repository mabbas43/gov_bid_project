"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Building2, LayoutDashboard, Radar, Sparkles } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { DemoProvider, useDemo } from "@/components/demo-context";

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/run", label: "Run Agent", icon: Sparkles },
  { href: "/profile", label: "Company Profile", icon: Building2 },
];

function DemoToggle({ compact = false }: { compact?: boolean }) {
  const { demo, setDemo } = useDemo();
  return (
    <label className="flex cursor-pointer items-center gap-2 text-sm">
      <Switch
        checked={demo ?? false}
        disabled={demo === null}
        onCheckedChange={(v) => setDemo(v)}
        aria-label="Demo mode"
      />
      <span>
        <span className="font-medium text-white">Demo mode</span>
        {!compact && (
          <span className="block text-xs text-sidebar-foreground/70">
            {demo ? "Seed data, no network" : "Live PPRA and DeepSeek"}
          </span>
        )}
      </span>
    </label>
  );
}

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" || pathname.startsWith("/tenders") : pathname.startsWith(href);
}

function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { error } = useDemo();
  return (
    <div className="flex min-h-dvh">
      <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col bg-sidebar p-4 text-sidebar-foreground md:flex">
        <Link href="/" className="mb-7 flex items-center gap-2.5 px-2 pt-1">
          <span className="grid size-8 place-items-center rounded-lg bg-emerald-500 text-white">
            <Radar className="size-5" />
          </span>
          <span className="text-lg font-semibold tracking-tight text-white">TenderScout</span>
        </Link>
        <nav className="flex flex-col gap-1">
          {NAV.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                isActive(pathname, href) ? "bg-sidebar-accent text-white" : "hover:bg-sidebar-accent/60 hover:text-white"
              }`}
            >
              <Icon className="size-4" />
              {label}
            </Link>
          ))}
        </nav>
        <div className="mt-auto border-t border-sidebar-border pt-4">
          <DemoToggle />
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 bg-sidebar text-sidebar-foreground md:hidden">
          <div className="flex items-center justify-between px-4 py-2.5">
            <Link href="/" className="flex items-center gap-2 font-semibold text-white">
              <Radar className="size-5 text-emerald-400" /> TenderScout
            </Link>
            <DemoToggle compact />
          </div>
          <nav className="flex border-t border-sidebar-border">
            {NAV.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                className={`flex flex-1 items-center justify-center gap-1.5 py-2.5 text-xs font-medium ${
                  isActive(pathname, href) ? "bg-sidebar-accent text-white" : ""
                }`}
              >
                <Icon className="size-3.5" />
                {label.replace("Company ", "")}
              </Link>
            ))}
          </nav>
        </header>
        {error && (
          <div role="alert" className="bg-red-600 px-4 py-2 text-sm text-white">
            {error}
          </div>
        )}
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 md:px-8 md:py-8">{children}</main>
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <DemoProvider>
      <Shell>{children}</Shell>
    </DemoProvider>
  );
}
