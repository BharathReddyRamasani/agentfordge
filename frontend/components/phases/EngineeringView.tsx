"use client";

import { useState } from "react";
import { Ban } from "lucide-react";
import { ApiError, api } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { useProject } from "@/store/project";
import { AgentGrid, LogViewer } from "@/components/agents";
import { ProgressBar } from "@/components/ui";
import { Spinner } from "@/components/common";

export function EngineeringView({ projectId }: { projectId: number }) {
  const workflow = useProject((s) => s.workflow);
  const agents = useProject((s) => s.agents);
  const logs = useProject((s) => s.logs);
  const refreshWorkflow = useProject((s) => s.refreshWorkflow);
  const [cancelling, setCancelling] = useState(false);
  const [error, setError] = useState("");

  const cancel = async () => {
    const token = getToken();
    if (!token || !confirm("Cancel the running autonomous workflow?")) return;
    setCancelling(true);
    try {
      await api.cancel(token, projectId);
      await refreshWorkflow(token, projectId);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Cancel failed");
    } finally {
      setCancelling(false);
    }
  };

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-slate-900">Autonomous Engineering in Progress</h2>
          <p className="text-sm text-slate-500">AI agents are building your complete application based on the approved prototype.</p>
        </div>
        <button onClick={() => void cancel()} disabled={cancelling} className="flex items-center gap-2 rounded-lg border border-red-300 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50 disabled:opacity-60">
          {cancelling ? <Spinner /> : <Ban className="h-4 w-4" />} Cancel Execution
        </button>
      </div>
      {error && <p className="mb-3 text-sm text-red-600">{error}</p>}
      <div className="mb-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-2 flex items-center justify-between text-sm">
          <span className="font-medium text-slate-700">
            Live Status · <span className="font-bold text-indigo-700">{workflow?.current_agent ?? workflow?.stage ?? "working"}</span>
          </span>
          <span className="font-bold text-slate-900">{workflow?.progress ?? 0}%</span>
        </div>
        <ProgressBar value={workflow?.progress ?? 0} />
      </div>
      <AgentGrid agents={agents} />
      <p className="mt-2 text-xs text-slate-400">Debugging runs only when tests fail — Pending means no debugging was needed.</p>
      <h3 className="mb-2 mt-5 font-bold text-slate-900">Live Logs</h3>
      <LogViewer logs={logs} maxHeight={300} />
    </div>
  );
}
