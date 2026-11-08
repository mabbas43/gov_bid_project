"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowDown, ArrowUp, Banknote, CalendarClock, FileStack, ScanSearch, Search, Sparkles, Trophy, Zap } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useDemo } from "@/components/demo-context";
import { ErrorCard } from "@/components/error-card";
import { Countdown, FitBadge } from "@/components/fit";
import { api, formatDuration, formatPkr, type Kpis, type TenderSummary } from "@/lib/api";

type SortKey = "fit_score" | "days_to_close" | "estimated_value_pkr" | "agency" | "title";
const FILTERS = [
  { key: "all", label: "All" },
  { key: "strong", label: "Strong" },
  { key: "partial", label: "Partial" },
  { key: "non_fit", label: "Non-fit" },
];

function Kpi({ icon: Icon, label, value, hint, tone }: { icon: typeof Trophy; label: string; value: string; hint?: string; tone: string }) {
  return (
    <Card className="gap-0 p-4">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-muted-foreground">{label}</span>
        <span className={`grid size-7 place-items-center rounded-lg ${tone}`}>
          <Icon className="size-4" />
        </span>
      </div>
      <div className="mt-2 truncate text-2xl font-semibold tabular-nums tracking-tight">{value}</div>
      <div className="mt-0.5 h-4 truncate text-xs text-muted-foreground" title={hint}>
        {hint}
      </div>
    </Card>
  );
}

function compare(a: TenderSummary, b: TenderSummary, key: SortKey, dir: 1 | -1) {
  const x = a[key];
  const y = b[key];
  // Missing values stay last in either direction.
  if (x === null && y === null) return 0;
  if (x === null) return 1;
  if (y === null) return -1;
  if (typeof x === "string") return x.localeCompare(y as string) * dir;
  return ((x as number) - (y as number)) * dir;
}

export default function DashboardPage() {
  const { demo } = useDemo();
  const [rows, setRows] = useState<TenderSummary[] | null>(null);
  const [kpis, setKpis] = useState<Kpis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "fit_score", dir: -1 });

  const load = useCallback(() => {
    setError(null);
    Promise.all([api<TenderSummary[]>("/tenders"), api<Kpis>("/dashboard")])
      .then(([t, k]) => {
        setRows(t);
        setKpis(k);
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(load, [load, demo]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (rows ?? [])
      .filter((t) => filter === "all" || t.fit_label === filter)
      .filter((t) => !q || t.title.toLowerCase().includes(q) || t.agency.toLowerCase().includes(q))
      .sort((a, b) => compare(a, b, sort.key, sort.dir));
  }, [rows, query, filter, sort]);

  const toggleSort = (key: SortKey) =>
    setSort((s) => (s.key === key ? { key, dir: s.dir === 1 ? -1 : 1 } : { key, dir: key === "days_to_close" || key === "agency" || key === "title" ? 1 : -1 }));

  const Th = ({ k, children, className = "" }: { k: SortKey; children: React.ReactNode; className?: string }) => (
    <th className={`px-4 py-3 font-medium ${className}`} aria-sort={sort.key === k ? (sort.dir === 1 ? "ascending" : "descending") : "none"}>
      <button onClick={() => toggleSort(k)} className="inline-flex items-center gap-1 hover:text-foreground">
        {children}
        {sort.key === k && (sort.dir === 1 ? <ArrowUp className="size-3" /> : <ArrowDown className="size-3" />)}
      </button>
    </th>
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            {demo ? "Sample tenders in demo mode." : "Tenders collected from PPRA."}
          </p>
        </div>
        <Link href="/run" className={buttonVariants()}>
          <Sparkles className="size-4" /> Run Agent
        </Link>
      </div>

      {error && <ErrorCard message={error} onRetry={load} />}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Kpi icon={ScanSearch} label="Tenders scanned" value={kpis ? String(kpis.tenders_scanned) : "–"} hint={kpis ? `of ${kpis.tenders_total} collected` : ""} tone="bg-sky-100 text-sky-700" />
        <Kpi icon={Trophy} label="Strong fits (70+)" value={kpis ? String(kpis.strong_fits) : "–"} tone="bg-emerald-100 text-emerald-700" />
        <Kpi icon={Banknote} label="Value of strong fits" value={kpis ? formatPkr(kpis.total_fit_value_pkr) : "–"} tone="bg-violet-100 text-violet-700" />
        <Kpi
          icon={CalendarClock}
          label="Nearest deadline"
          value={kpis?.nearest_deadline ? `${kpis.nearest_deadline.days_to_close} days` : "–"}
          hint={kpis?.nearest_deadline?.title}
          tone="bg-amber-100 text-amber-700"
        />
        <Kpi icon={Zap} label="Avg time to bid pack" value={kpis?.avg_bidpack_ms != null ? formatDuration(kpis.avg_bidpack_ms) : "–"} hint={kpis?.avg_bidpack_ms == null ? "No bid packs yet" : ""} tone="bg-rose-100 text-rose-700" />
      </div>

      <Card className="gap-0 overflow-hidden p-0">
        <div className="flex flex-wrap items-center gap-3 border-b p-3">
          <div className="relative min-w-48 flex-1">
            <Search className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input aria-label="Search tenders" placeholder="Search title or agency" value={query} onChange={(e) => setQuery(e.target.value)} className="pl-8" />
          </div>
          <div className="flex rounded-lg bg-muted p-0.5" role="group" aria-label="Filter by fit">
            {FILTERS.map((f) => (
              <button
                key={f.key}
                aria-pressed={filter === f.key}
                onClick={() => setFilter(f.key)}
                className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${filter === f.key ? "bg-card shadow-sm" : "text-muted-foreground hover:text-foreground"}`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {/* Table on desktop */}
        <div className="hidden overflow-x-auto md:block">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/40 text-left text-xs text-muted-foreground">
              <tr>
                <Th k="fit_score">Fit</Th>
                <Th k="title">Tender</Th>
                <Th k="agency">Agency</Th>
                <Th k="estimated_value_pkr">Value</Th>
                <Th k="days_to_close">Closes in</Th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {visible.map((t) => (
                <tr key={t.id} className="relative transition-colors hover:bg-muted/40">
                  <td className="px-4 py-3">
                    <FitBadge score={t.fit_score} label={t.fit_label} status={t.status} />
                  </td>
                  <td className="max-w-md px-4 py-3">
                    <Link href={`/tenders/${t.id}`} className="font-medium after:absolute after:inset-0 hover:underline">
                      {t.title}
                    </Link>
                    {t.fit_reason && <div className="mt-0.5 truncate text-xs text-muted-foreground">{t.fit_reason}</div>}
                  </td>
                  <td className="max-w-56 truncate px-4 py-3 text-muted-foreground">{t.agency}</td>
                  <td className="whitespace-nowrap px-4 py-3 tabular-nums">{formatPkr(t.estimated_value_pkr)}</td>
                  <td className="px-4 py-3">
                    <Countdown days={t.days_to_close} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Cards on phones */}
        <div className="divide-y md:hidden">
          {visible.map((t) => (
            <Link key={t.id} href={`/tenders/${t.id}`} className="block space-y-1.5 p-4 active:bg-muted/50">
              <div className="flex items-start justify-between gap-3">
                <span className="font-medium">{t.title}</span>
                <FitBadge score={t.fit_score} label={t.fit_label} status={t.status} />
              </div>
              <div className="text-xs text-muted-foreground">{t.agency}</div>
              <div className="flex justify-between text-xs">
                <span className="tabular-nums">{formatPkr(t.estimated_value_pkr)}</span>
                <Countdown days={t.days_to_close} />
              </div>
            </Link>
          ))}
        </div>

        {rows && visible.length === 0 && (
          <div className="flex flex-col items-center gap-2 p-10 text-center text-sm text-muted-foreground">
            <FileStack className="size-8 opacity-40" />
            {rows.length === 0 ? "No tenders yet. Run the agent to collect some." : "No tenders match these filters."}
          </div>
        )}
        {!rows && !error && <div className="p-10 text-center text-sm text-muted-foreground">Loading tenders…</div>}
      </Card>
    </div>
  );
}
