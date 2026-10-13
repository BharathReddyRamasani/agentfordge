import { cn } from "@/lib/utils";

const STYLES: Record<string, string> = {
  completed: "bg-emerald-100 text-emerald-700",
  COMPLETED: "bg-emerald-100 text-emerald-700",
  approved: "bg-emerald-100 text-emerald-700",
  running: "bg-amber-100 text-amber-700",
  pending: "bg-slate-100 text-slate-500",
  failed: "bg-red-100 text-red-700",
  FAILED: "bg-red-100 text-red-700",
  review: "bg-indigo-100 text-indigo-700",
  progress: "bg-amber-100 text-amber-700",
};

export function StatusBadge({ status, label }: { status: string; label?: string }) {
  const key = /progress|running|in progress/i.test(status) ? "progress" : status;
  return (
    <span className={cn("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold", STYLES[status] ?? STYLES[key] ?? "bg-slate-100 text-slate-600")}>
      {label ?? status.replace(/_/g, " ")}
    </span>
  );
}

export function ProgressBar({ value, className }: { value: number; className?: string }) {
  return (
    <div className={cn("h-2 w-full overflow-hidden rounded-full bg-slate-200", className)}>
      <div className="h-full rounded-full bg-indigo-600 transition-all" style={{ width: `${Math.min(100, Math.max(0, value))}%` }} />
    </div>
  );
}

const STEPS = ["Requirements", "Analysis", "Planning", "Prototype", "Review"];

function stepIndex(status: string): number {
  if (!status || status === "CREATED") return 0;
  if (["ANALYZING"].includes(status)) return 1;
  if (["PLANNING", "PLAN_REVISION"].includes(status)) return 2;
  if (["PROTOTYPE_BUILDING", "PROTOTYPE_REBUILDING", "AWAITING_REVIEW", "CHANGES_REQUESTED"].includes(status)) return 3;
  return 4;
}

export function Stepper({ status }: { status: string }) {
  const active = stepIndex(status);
  return (
    <div className="flex items-center gap-1 sm:gap-2">
      {STEPS.map((label, i) => (
        <div key={label} className="flex flex-1 items-center last:flex-none">
          <div className="flex flex-col items-center gap-1">
            <div
              className={cn(
                "flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold",
                i < active && "bg-indigo-600 text-white",
                i === active && "bg-indigo-600 text-white ring-4 ring-indigo-100",
                i > active && "bg-slate-200 text-slate-500"
              )}
            >
              {i < active ? "✓" : i + 1}
            </div>
            <span className={cn("text-[11px] font-medium", i <= active ? "text-indigo-700" : "text-slate-400")}>{label}</span>
          </div>
          {i < STEPS.length - 1 && <div className={cn("mx-1 mb-5 h-0.5 flex-1", i < active ? "bg-indigo-600" : "bg-slate-200")} />}
        </div>
      ))}
    </div>
  );
}
