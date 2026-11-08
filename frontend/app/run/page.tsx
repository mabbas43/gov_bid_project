"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle, Brain, Check, CheckCircle2, Download, FileDown, FileSearch, FileText, Globe, Loader2,
  Package, PenLine, Play, Scale, Target, Users, Wrench, XCircle,
} from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { useDemo } from "@/components/demo-context";
import { ErrorCard } from "@/components/error-card";
import { API_URL, api, formatDuration, type Run, type RunStep } from "@/lib/api";

const DEFAULT_GOAL = "Find IT tenders we can win this month and prepare a bid for the best one.";

const TOOL_META: Record<string, { label: string; icon: typeof Globe; color: string }> = {
  fetch_tender_listings: { label: "Fetch tender listings", icon: Globe, color: "bg-sky-100 text-sky-700" },
  download_document: { label: "Download document", icon: FileDown, color: "bg-indigo-100 text-indigo-700" },
  extract_text: { label: "Extract text", icon: FileText, color: "bg-violet-100 text-violet-700" },
  analyze_many: { label: "Analyse tenders", icon: Users, color: "bg-amber-100 text-amber-700" },
  generate_bid_pack: { label: "Generate bid pack", icon: Package, color: "bg-emerald-100 text-emerald-700" },
  write_note: { label: "Write note", icon: PenLine, color: "bg-slate-100 text-slate-700" },
};
const SUB_ICONS: Record<string, typeof Globe> = {
  extract_requirements: FileSearch, check_eligibility: Scale, score_fit: Target,
  download_document: FileDown, extract_text: FileText, draft_proposal: PenLine, build_documents: Package,
};
const SUB_LABELS: Record<string, string> = {
  extract_requirements: "Reading requirements", check_eligibility: "Checking eligibility", score_fit: "Scoring fit",
  download_document: "Downloading", extract_text: "Extracting text", draft_proposal: "Drafting proposal", build_documents: "Building documents",
};

function SubAgents({ steps }: { steps: RunStep[] }) {
  // One row per tender, updated as its sub-agent moves through its steps.
  const tenders = useMemo(() => {
    const map = new Map<number, { title: string; current: RunStep; score: string | null; failed: boolean }>();
    for (const s of steps) {
      if (s.tender_id === null) continue;
      const prev = map.get(s.tender_id);
      const score = s.tool === "score_fit" && s.status === "done" ? s.output_summary.match(/^(\d+)\/100/)?.[1] ?? null : prev?.score ?? null;
      const title = s.tool === "extract_requirements" ? s.input_summary : prev?.title ?? `Tender ${s.tender_id}`;
      map.set(s.tender_id, { title, current: s, score, failed: (prev?.failed ?? false) || s.status === "error" });
    }
    return [...map.entries()];
  }, [steps]);

  const finished = tenders.filter(([, t]) => t.score !== null || t.failed).length;
  return (
    <div className="mt-3 rounded-lg border bg-muted/30 p-3">
      <div className="mb-2 flex items-center justify-between text-xs font-medium text-muted-foreground">
        <span>Isolated sub-agents</span>
        <span className="tabular-nums">{finished} of {tenders.length} finished</span>
      </div>
      <ul className="grid gap-1.5 lg:grid-cols-2">
        {tenders.map(([id, t]) => {
          const score = t.score === null ? null : Number(t.score);
          const Icon = SUB_ICONS[t.current.tool] ?? Wrench;
          return (
            <li key={id} className="flex min-w-0 items-center gap-2 rounded-md bg-card px-2.5 py-1.5 text-xs shadow-xs animate-in fade-in slide-in-from-bottom-1">
              {t.failed ? (
                <XCircle className="size-3.5 shrink-0 text-red-500" />
              ) : score !== null ? (
                <CheckCircle2 className="size-3.5 shrink-0 text-emerald-600" />
              ) : (
                <Loader2 className="size-3.5 shrink-0 animate-spin text-amber-600" />
              )}
              <span className="min-w-0 flex-1 truncate" title={t.title}>{t.title}</span>
              {score !== null ? (
                <span className={`rounded-full px-2 py-px font-semibold tabular-nums ${score >= 70 ? "bg-emerald-100 text-emerald-800" : score >= 30 ? "bg-amber-100 text-amber-800" : "bg-red-100 text-red-800"}`}>
                  {score}
                </span>
              ) : !t.failed ? (
                <span className="hidden shrink-0 items-center gap-1 text-muted-foreground sm:inline-flex">
                  <Icon className="size-3" /> {SUB_LABELS[t.current.tool] ?? t.current.tool}
                </span>
              ) : null}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function BuildSteps({ steps }: { steps: RunStep[] }) {
  return (
    <ul className="mt-3 space-y-1 rounded-lg border bg-muted/30 p-3 text-xs">
      {steps.map((s) => (
        <li key={s.id} className="flex items-center gap-2">
          {s.status === "running" ? <Loader2 className="size-3.5 animate-spin text-amber-600" /> : s.status === "error" ? <XCircle className="size-3.5 text-red-500" /> : <Check className="size-3.5 text-emerald-600" />}
          <span className="font-medium">{SUB_LABELS[s.tool] ?? s.tool}</span>
          <span className="ml-auto text-muted-foreground tabular-nums">{s.status !== "running" && formatDuration(s.duration_ms)}</span>
        </li>
      ))}
    </ul>
  );
}

function TimelineItem({ step, children, last }: { step: RunStep; children: RunStep[]; last: boolean }) {
  const meta = TOOL_META[step.tool] ?? { label: step.tool, icon: Wrench, color: "bg-slate-100 text-slate-700" };
  const Icon = meta.icon;
  const running = step.status === "running";
  const failed = step.status === "error" || step.output_summary.startsWith("Error");
  return (
    <li className="relative flex gap-3.5 pb-5 animate-in fade-in slide-in-from-bottom-2 duration-300 md:gap-4">
      {!last && <span aria-hidden className="absolute top-10 bottom-0 left-[19px] w-px bg-border" />}
      <span className={`relative z-10 grid size-10 shrink-0 place-items-center rounded-xl ${failed ? "bg-red-100 text-red-700" : meta.color} ${running ? "ring-4 ring-amber-200/60" : ""}`}>
        <Icon className="size-5" />
      </span>
      <Card className="min-w-0 flex-1 gap-0 p-3.5">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
          <span className="text-sm font-semibold">{meta.label}</span>
          <span className="ml-auto flex items-center gap-1.5 text-xs text-muted-foreground tabular-nums">
            {running ? (
              <><Loader2 className="size-3.5 animate-spin" /> Running</>
            ) : failed ? (
              <><XCircle className="size-3.5 text-red-500" /> {formatDuration(step.duration_ms)}</>
            ) : (
              <><CheckCircle2 className="size-3.5 text-emerald-600" /> {formatDuration(step.duration_ms)}</>
            )}
          </span>
        </div>
        {step.thought_summary && (
          <p className="mt-1 flex gap-1.5 text-sm text-muted-foreground">
            <Brain className="mt-0.5 size-3.5 shrink-0 opacity-60" />
            <span className="min-w-0">{step.thought_summary}</span>
          </p>
        )}
        {step.output_summary && !running && (
          <p className={`mt-1.5 break-words text-sm ${failed ? "text-red-700" : ""}`}>{step.output_summary}</p>
        )}
        {step.tool === "analyze_many" && children.length > 0 && <SubAgents steps={children} />}
        {step.tool === "generate_bid_pack" && children.length > 0 && <BuildSteps steps={children} />}
      </Card>
    </li>
  );
}

export default function RunAgentPage() {
  const { demo } = useDemo();
  const [goal, setGoal] = useState(DEFAULT_GOAL);
  const [run, setRun] = useState<Run | null>(null);
  const [steps, setSteps] = useState<Map<number, RunStep>>(new Map());
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const source = useRef<EventSource | null>(null);
  const bottom = useRef<HTMLDivElement | null>(null);
  const startedAt = useRef(0);

  const active = run?.status === "queued" || run?.status === "running";

  const follow = useCallback((id: number) => {
    source.current?.close();
    const es = new EventSource(`${API_URL}/runs/${id}/stream`);
    source.current = es;
    es.addEventListener("step", (e) => {
      const step: RunStep = JSON.parse((e as MessageEvent).data);
      setSteps((prev) => new Map(prev).set(step.id, step));
    });
    es.addEventListener("end", (e) => {
      setRun(JSON.parse((e as MessageEvent).data));
      es.close();
    });
    // EventSource reconnects by itself; steps are keyed by id, so the replay is harmless.
  }, []);

  useEffect(() => {
    // Reopening /run?run=5 restores that run, including one still in progress.
    const id = new URLSearchParams(window.location.search).get("run");
    if (id) {
      api<Run>(`/runs/${id}`).then((r) => {
        setRun(r);
        setGoal(r.goal);
        startedAt.current = Date.now();
        follow(r.id);
      }).catch((e) => setError(e.message));
    }
    return () => source.current?.close();
  }, [follow]);

  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => setElapsed(Date.now() - startedAt.current), 200);
    return () => clearInterval(timer);
  }, [active]);

  const count = steps.size;
  useEffect(() => {
    if (active) bottom.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [count, active]);

  const start = async () => {
    setStarting(true);
    setError(null);
    setSteps(new Map());
    setElapsed(0);
    try {
      const r = await api<Run>("/runs", { method: "POST", body: JSON.stringify({ goal }) });
      setRun(r);
      startedAt.current = Date.now();
      window.history.replaceState(null, "", `/run?run=${r.id}`);
      follow(r.id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setStarting(false);
    }
  };

  // Sub-agent steps always follow the orchestrator step that started them.
  const groups = useMemo(() => {
    const out: { step: RunStep; children: RunStep[] }[] = [];
    for (const s of [...steps.values()].sort((a, b) => a.id - b.id)) {
      if (s.scope === "orchestrator" || out.length === 0) out.push({ step: s, children: [] });
      else out[out.length - 1].children.push(s);
    }
    return out;
  }, [steps]);

  const toolRunning = [...steps.values()].some((s) => s.status === "running");

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Run Agent</h1>
        <p className="text-sm text-muted-foreground">Give the agent a goal and watch it work, step by step.</p>
      </div>

      <Card className="gap-3 p-4">
        <label htmlFor="goal" className="text-sm font-medium">Goal</label>
        <Textarea id="goal" rows={2} value={goal} disabled={active} onChange={(e) => setGoal(e.target.value)} />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
            <span className={`size-2 rounded-full ${demo ? "bg-amber-500" : "bg-emerald-500"}`} />
            {demo === null ? "Connecting…" : demo ? "Demo mode: seed data and a scripted offline agent" : "Live mode: PPRA website and DeepSeek"}
          </span>
          <Button onClick={start} disabled={active || starting || goal.trim().length < 3}>
            {active || starting ? <Loader2 className="size-4 animate-spin" /> : <Play className="size-4" />}
            {active ? "Running…" : "Start"}
          </Button>
        </div>
      </Card>

      {error && <ErrorCard message={error} />}

      {run && (
        <div aria-live="polite">
          <div className="mb-4 flex items-center justify-between text-xs text-muted-foreground">
            <span className="font-medium">Timeline</span>
            <span className="tabular-nums">
              {groups.length} step{groups.length === 1 ? "" : "s"}
              {active && ` · ${(elapsed / 1000).toFixed(1)} s`}
              {!active && run.tokens > 0 && ` · ${run.tokens.toLocaleString()} tokens`}
            </span>
          </div>
          <ol>
            {groups.map(({ step, children }, i) => (
              <TimelineItem key={step.id} step={step} last={i === groups.length - 1 && !active && !run.final_answer && !run.error}>
                {children}
              </TimelineItem>
            ))}
            {active && !toolRunning && (
              <li className="flex items-center gap-4 pb-5 text-sm text-muted-foreground animate-in fade-in">
                <span className="grid size-10 place-items-center rounded-xl bg-muted"><Brain className="size-5 animate-pulse" /></span>
                Deciding what to do next…
              </li>
            )}
          </ol>

          {run.status === "completed" && (
            <Card className="gap-3 border-emerald-200 bg-emerald-50/60 p-5 animate-in fade-in slide-in-from-bottom-2">
              <div className="flex items-center gap-2 font-semibold text-emerald-900">
                <CheckCircle2 className="size-5" /> Goal complete
              </div>
              <p className="text-sm whitespace-pre-wrap">{run.final_answer}</p>
              {run.best_tender_id && (
                <div className="flex flex-wrap gap-2">
                  <a href={`${API_URL}/tenders/${run.best_tender_id}/bidpack/download`} className={buttonVariants()}>
                    <Download className="size-4" /> Download bid pack
                  </a>
                  <Link href={`/tenders/${run.best_tender_id}`} className={buttonVariants({ variant: "outline" })}>
                    View tender
                  </Link>
                </div>
              )}
            </Card>
          )}
          {run.status === "failed" && (
            <Card className="gap-1.5 border-red-200 bg-red-50 p-5">
              <div className="flex items-center gap-2 font-semibold text-red-900">
                <AlertCircle className="size-5" /> The run stopped
              </div>
              <p className="text-sm text-red-800">{run.error}</p>
            </Card>
          )}
          <div ref={bottom} />
        </div>
      )}
    </div>
  );
}
