"use client";

import { CheckCircle2, Clock, Loader2, XCircle, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AgentStatus, ProjectEvent } from "@/types";

const AGENT_META: { key: string; label: string }[] = [
  { key: "architecture", label: "Architecture" },
  { key: "frontend", label: "Frontend" },
  { key: "backend", label: "Backend" },
  { key: "database", label: "Database" },
  { key: "integration", label: "Integration" },
  { key: "testing", label: "Testing" },
  { key: "debugging", label: "Debugging" },
  { key: "review", label: "Review" },
  { key: "security", label: "Security" },
  { key: "documentation", label: "Documentation" },
  { key: "deployment", label: "Deployment" },
];

export function agentStageStatus(agents: AgentStatus[], stage: string): string {
  const rows = agents.filter((a) => a.stage === stage);
  if (rows.some((r) => r.status === "running")) return "running";
  if (rows.some((r) => r.status === "failed")) return "failed";
  if (rows.length > 0 && rows.every((r) => r.status === "completed")) return "completed";
  return "pending";
}

export function AgentCard({ label, status }: { label: string; status: string }) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <span
        className={cn(
          "flex h-9 w-9 items-center justify-center rounded-lg",
          status === "completed" && "bg-emerald-100 text-emerald-600",
          status === "running" && "bg-amber-100 text-amber-600",
          status === "failed" && "bg-red-100 text-red-600",
          status === "pending" && "bg-slate-100 text-slate-400"
        )}
      >
        {status === "completed" && <CheckCircle2 className="h-5 w-5" />}
        {status === "running" && <Loader2 className="h-5 w-5 animate-spin" />}
        {status === "failed" && <XCircle className="h-5 w-5" />}
        {status === "pending" && <Clock className="h-5 w-5" />}
      </span>
      <div>
        <p className="text-sm font-semibold text-slate-800">{label}</p>
        <p
          className={cn(
            "text-xs font-medium capitalize",
            status === "completed" && "text-emerald-600",
            status === "running" && "text-amber-600",
            status === "failed" && "text-red-600",
            status === "pending" && "text-slate-400"
          )}
        >
          {status === "running" ? "In Progress" : status}
        </p>
      </div>
    </div>
  );
}

export function AgentGrid({ agents }: { agents: AgentStatus[] }) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {AGENT_META.map((m) => (
        <AgentCard key={m.key} label={m.label} status={agentStageStatus(agents, m.key)} />
      ))}
    </div>
  );
}

export function LogViewer({ logs, maxHeight }: { logs: ProjectEvent[]; maxHeight?: string | number }) {
  return (
    <div
      className="overflow-y-auto rounded-xl bg-slate-950 p-4 font-mono text-xs leading-relaxed text-slate-200"
      style={{ maxHeight: typeof maxHeight === "number" ? `${maxHeight}px` : maxHeight ?? 320 }}
      ref={(el) => {
        if (el) el.scrollTop = el.scrollHeight;
      }}
    >
      {logs.length === 0 && <p className="text-slate-500">Waiting for activity…</p>}
      {logs.map((l) => (
        <div key={l.id} className="flex gap-2">
          <span className="shrink-0 text-slate-500">{new Date(l.created_at).toLocaleTimeString()}</span>
          <span
            className={cn(
              "shrink-0",
              l.status === "error" ? "text-red-400" : l.event.includes("completed") ? "text-emerald-400" : "text-indigo-300"
            )}
          >
            ●
          </span>
          <span className="break-words">
            {l.agent ? `[${l.agent}] ` : ""}
            {l.message}
          </span>
        </div>
      ))}
    </div>
  );
}

export function RetryNote() {
  return (
    <span className="inline-flex items-center gap-1 text-xs text-slate-400">
      <RefreshCw className="h-3 w-3" /> auto-refreshing
    </span>
  );
}
