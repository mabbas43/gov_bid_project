import { Clock } from "lucide-react";
import type { FitLabel } from "@/lib/api";

const STYLES: Record<FitLabel, string> = {
  strong: "bg-emerald-100 text-emerald-800 ring-emerald-600/20",
  partial: "bg-amber-100 text-amber-800 ring-amber-600/20",
  non_fit: "bg-red-100 text-red-800 ring-red-600/20",
};
const NAMES: Record<FitLabel, string> = { strong: "Strong", partial: "Partial", non_fit: "Non-fit" };
const STATUS_NAMES: Record<string, string> = {
  new: "Not analysed",
  needs_ocr: "Needs OCR",
  no_document: "No document",
  error: "Error",
};

export function FitBadge({ score, label, status }: { score: number | null; label: FitLabel | null; status?: string }) {
  if (score === null || !label) {
    return (
      <span className="inline-flex whitespace-nowrap rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600 ring-1 ring-inset ring-slate-500/20">
        {STATUS_NAMES[status ?? "new"] ?? status}
      </span>
    );
  }
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${STYLES[label]}`}>
      <span className="tabular-nums">{score}</span>
      <span className="font-medium opacity-80">{NAMES[label]}</span>
    </span>
  );
}

export function Countdown({ days }: { days: number | null }) {
  if (days === null) return <span className="text-muted-foreground">Unknown</span>;
  if (days < 0) return <span className="text-muted-foreground">Closed</span>;
  const urgent = days <= 7;
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap tabular-nums ${urgent ? "font-semibold text-red-600" : ""}`}>
      <Clock className="size-3.5 opacity-60" />
      {days === 0 ? "Today" : `${days} day${days === 1 ? "" : "s"}`}
    </span>
  );
}
