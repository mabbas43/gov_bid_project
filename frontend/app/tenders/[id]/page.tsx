"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, Download, ExternalLink, FileSpreadsheet, FileText, Loader2, Package, RefreshCw, ScanSearch, ShieldAlert } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { ErrorCard } from "@/components/error-card";
import { Countdown, FitBadge } from "@/components/fit";
import { API_URL, api, formatDuration, formatPkr, type BidPack, type Check, type TenderDetail } from "@/lib/api";

const STATUS = {
  pass: { emoji: "✅", name: "Met" },
  fail: { emoji: "❌", name: "Not met" },
  unclear: { emoji: "⚠️", name: "Confirm" },
};

function ScoreBar({ label, value, weight }: { label: string; value: number; weight: number }) {
  const points = Math.round(value * weight);
  return (
    <div>
      <div className="mb-1 flex justify-between text-sm">
        <span>{label}</span>
        <span className="tabular-nums text-muted-foreground">{points} / {weight}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full bg-emerald-500 transition-all duration-500" style={{ width: `${Math.round(value * 100)}%` }} />
      </div>
    </div>
  );
}

function CheckRow({ check }: { check: Check }) {
  const s = STATUS[check.status];
  return (
    <li className="flex gap-3 p-4">
      <span aria-label={s.name} role="img" className="text-lg leading-6">{s.emoji}</span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="font-medium">{check.requirement}</span>
          <span className="rounded bg-muted px-1.5 py-px text-[11px] text-muted-foreground">{check.type}</span>
          {!check.mandatory && <span className="rounded bg-sky-100 px-1.5 py-px text-[11px] text-sky-800">preferred</span>}
        </div>
        <p className="mt-1 text-sm text-muted-foreground">{check.reason}</p>
        {check.source_quote && (
          <blockquote className="mt-2 border-l-2 pl-3 text-xs italic text-muted-foreground">“{check.source_quote}”</blockquote>
        )}
      </div>
    </li>
  );
}

function BidPackCard({ tender, onGenerated }: { tender: TenderDetail; onGenerated: () => void }) {
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const pack: BidPack | null = tender.bid_pack?.status === "ready" ? tender.bid_pack : null;

  useEffect(() => {
    if (!busy) return;
    const started = Date.now();
    const timer = setInterval(() => setElapsed(Date.now() - started), 100);
    return () => clearInterval(timer);
  }, [busy]);

  const generate = async () => {
    setBusy(true);
    setError(null);
    setElapsed(0);
    try {
      await api(`/tenders/${tender.id}/bidpack`, { method: "POST" });
      onGenerated();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="gap-3 p-5">
      <h2 className="flex items-center gap-2 font-semibold"><Package className="size-4" /> Bid pack</h2>
      {tender.fit_label === "non_fit" && !pack && (
        <p className="flex gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-800">
          <ShieldAlert className="mt-0.5 size-4 shrink-0" />
          This tender has a disqualifying clause. Read the risk register before spending time on it.
        </p>
      )}
      {busy && (
        <div className="space-y-1.5">
          <Progress value={Math.min(95, elapsed / 40)} />
          <p className="text-xs tabular-nums text-muted-foreground" aria-live="polite">Generating… {(elapsed / 1000).toFixed(1)} s</p>
        </div>
      )}
      {error && <ErrorCard message={error} />}
      {pack ? (
        <>
          <p className="text-sm text-muted-foreground">Generated in <span className="font-semibold text-foreground">{formatDuration(pack.generation_ms)}</span>.</p>
          <a href={`${API_URL}/tenders/${tender.id}/bidpack/download`} className={buttonVariants()}>
            <Download className="size-4" /> Download all (.zip)
          </a>
          <ul className="divide-y rounded-lg border text-sm">
            {pack.files.map((f) => (
              <li key={f}>
                <a href={`${API_URL}/tenders/${tender.id}/bidpack/files/${f}`} className="flex items-center gap-2 px-3 py-2 hover:bg-muted/50">
                  {f.endsWith(".docx") ? <FileText className="size-4 text-sky-600" /> : <FileSpreadsheet className="size-4 text-emerald-600" />}
                  <span className="min-w-0 flex-1 truncate">{f}</span>
                  <Download className="size-3.5 text-muted-foreground" />
                </a>
              </li>
            ))}
          </ul>
          <p className="text-xs text-muted-foreground">Costs and the work plan are drafts. Review them before you submit.</p>
          <Button variant="outline" size="sm" onClick={generate} disabled={busy}>
            <RefreshCw className="size-3.5" /> Regenerate
          </Button>
        </>
      ) : (
        <Button onClick={generate} disabled={busy}>
          {busy ? <Loader2 className="size-4 animate-spin" /> : <Package className="size-4" />}
          {busy ? "Generating…" : "Generate Bid Pack"}
        </Button>
      )}
    </Card>
  );
}

export default function TenderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [tender, setTender] = useState<TenderDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [analysing, setAnalysing] = useState(false);

  const load = useCallback(() => {
    setError(null);
    api<TenderDetail>(`/tenders/${id}`).then(setTender).catch((e) => setError(e.message));
  }, [id]);

  useEffect(load, [load]);

  const analyse = async () => {
    setAnalysing(true);
    setError(null);
    try {
      await api(`/tenders/${id}/analyze`, { method: "POST" });
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setAnalysing(false);
    }
  };

  if (error && !tender) return <ErrorCard message={error} onRetry={load} />;
  if (!tender) return <p className="text-sm text-muted-foreground">Loading…</p>;

  const b = tender.score_breakdown;
  const counts = {
    pass: tender.checks.filter((c) => c.status === "pass").length,
    fail: tender.checks.filter((c) => c.status === "fail").length,
    unclear: tender.checks.filter((c) => c.status === "unclear").length,
  };
  // Blockers first because they decide the bid; routine paperwork last.
  const rank = (c: Check) => (c.type === "document" ? 3 : { fail: 0, unclear: 1, pass: 2 }[c.status]);
  const checks = [...tender.checks].sort((x, y) => rank(x) - rank(y) || Number(y.mandatory) - Number(x.mandatory));

  return (
    <div className="space-y-6">
      <Link href="/" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> Dashboard
      </Link>

      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <FitBadge score={tender.fit_score} label={tender.fit_label} status={tender.status} />
          <span className="text-xs text-muted-foreground">{tender.external_id}</span>
        </div>
        <h1 className="text-2xl font-semibold tracking-tight text-balance">{tender.title}</h1>
        <p className="text-sm text-muted-foreground">{tender.agency}</p>
        {tender.fit_reason && <p className="text-sm">{tender.fit_reason}</p>}
      </div>

      {error && <ErrorCard message={error} />}

      {tender.status === "needs_ocr" && (
        <ErrorCard message="This tender's PDF is a scan with no text layer, so it needs OCR before it can be analysed. Read the document yourself or run it through OCR." />
      )}
      {(tender.status === "error" || tender.status === "no_document") && tender.status_detail && <ErrorCard message={tender.status_detail} onRetry={analyse} />}

      <div className="grid items-start gap-6 lg:grid-cols-3">
        <div className="min-w-0 space-y-6 lg:col-span-2">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              ["Value", formatPkr(tender.estimated_value_pkr)],
              ["Closes in", <Countdown key="c" days={tender.days_to_close} />],
              ["Closing date", tender.closing_date ?? "Unknown"],
              ["Bid security", tender.bid_security ?? "Not stated"],
            ].map(([label, value]) => (
              <Card key={label as string} className="gap-0.5 p-3">
                <span className="text-xs text-muted-foreground">{label}</span>
                <span className="text-sm font-semibold">{value}</span>
              </Card>
            ))}
          </div>

          {tender.scope_summary ? (
            <Card className="gap-2 p-5">
              <h2 className="font-semibold">Scope</h2>
              <p className="text-sm leading-relaxed">{tender.scope_summary}</p>
              {tender.document_url?.startsWith("http") && (
                <a href={tender.document_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm text-primary hover:underline">
                  Original document <ExternalLink className="size-3.5" />
                </a>
              )}
            </Card>
          ) : (
            tender.status === "new" && (
              <Card className="items-start gap-3 p-5">
                <p className="text-sm text-muted-foreground">This tender has not been analysed yet.</p>
                <Button onClick={analyse} disabled={analysing}>
                  {analysing ? <Loader2 className="size-4 animate-spin" /> : <ScanSearch className="size-4" />}
                  {analysing ? "Analysing…" : "Analyse now"}
                </Button>
              </Card>
            )
          )}

          {tender.checks.length > 0 && (
            <Card className="gap-0 overflow-hidden p-0">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b p-4">
                <h2 className="font-semibold">Eligibility checklist</h2>
                <span className="text-xs tabular-nums text-muted-foreground">
                  ✅ {counts.pass} &nbsp; ❌ {counts.fail} &nbsp; ⚠️ {counts.unclear}
                </span>
              </div>
              <ul className="divide-y">
                {checks.map((c) => <CheckRow key={c.id} check={c} />)}
              </ul>
            </Card>
          )}
        </div>

        <div className="space-y-6">
          {tender.fit_score !== null && (
            <Card className="gap-4 p-5">
              <h2 className="font-semibold">Score breakdown</h2>
              <div className="text-4xl font-semibold tabular-nums tracking-tight">
                {tender.fit_score}<span className="text-lg text-muted-foreground"> / 100</span>
              </div>
              <ScoreBar label="Capability match" value={b.capability ?? 0} weight={40} />
              <ScoreBar label="Eligibility" value={b.eligibility ?? 0} weight={40} />
              <ScoreBar label="Value and size fit" value={b.value_fit ?? 0} weight={20} />
              {b.capped && (
                <p className="rounded-lg bg-red-50 p-2.5 text-xs text-red-800">
                  A failed mandatory clause caps the score at 20, whatever the parts add up to.
                </p>
              )}
            </Card>
          )}
          {tender.status === "analyzed" && <BidPackCard tender={tender} onGenerated={load} />}
        </div>
      </div>
    </div>
  );
}
