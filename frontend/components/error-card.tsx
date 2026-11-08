import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";

export function ErrorCard({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex flex-wrap items-center gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
      <AlertTriangle className="size-5 shrink-0" />
      <span className="min-w-0 flex-1">{message}</span>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
