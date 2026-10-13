"use client";

import { useProject } from "@/store/project";
import { AgentGrid, LogViewer } from "@/components/agents";
import { StatusBadge } from "@/components/ui";
import { EmptyState, SectionCard, Spinner, Tabs } from "@/components/common";
import { useState } from "react";
import { api } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { Artifact } from "@/types";

function AgentsTab() {
  const agents = useProject((s) => s.agents);
  if (agents.length === 0) return <EmptyState title="No agent activity yet" />;
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-100 text-xs uppercase text-slate-400">
            <th className="px-4 py-2">Agent</th>
            <th className="px-4 py-2">Stage</th>
            <th className="px-4 py-2">Status</th>
            <th className="px-4 py-2">Attempts</th>
            <th className="px-4 py-2">Error</th>
          </tr>
        </thead>
        <tbody>
          {agents.map((a, i) => (
            <tr key={i} className="border-b border-slate-50 last:border-0">
              <td className="px-4 py-2 font-medium">{a.agent}</td>
              <td className="px-4 py-2 text-slate-500">{a.stage}</td>
              <td className="px-4 py-2"><StatusBadge status={a.status} /></td>
              <td className="px-4 py-2">{a.attempts}</td>
              <td className="max-w-xs truncate px-4 py-2 text-xs text-red-500">{a.error ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TestsTab() {
  const tests = useProject((s) => s.tests);
  const [open, setOpen] = useState<string | null>(null);
  if (tests.length === 0) return <EmptyState title="No test runs yet" hint="Tests execute during autonomous engineering." />;
  return (
    <div className="space-y-3">
      {tests.map((t) => (
        <div key={`${t.run_id}-${t.iteration}`} className="rounded-xl border border-slate-200 bg-white p-4">
          <button className="flex w-full items-center justify-between" onClick={() => setOpen(open === t.run_id ? null : t.run_id)}>
            <span className="text-sm font-semibold">Run {t.run_id} · iteration {t.iteration}</span>
            <StatusBadge status={t.status} label={`${t.passed}/${t.total} passed`} />
          </button>
          {open === t.run_id && <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-950 p-3 font-mono text-xs text-slate-200">{t.output.slice(-4000)}</pre>}
        </div>
      ))}
    </div>
  );
}

function ArtifactsTab({ projectId }: { projectId: number }) {
  const [items, setItems] = useState<Artifact[]>([]);
  const [loaded, setLoaded] = useState(false);
  const token = getToken();
  if (!loaded && token) {
    setLoaded(true);
    api.getArtifacts(token, projectId).then(setItems).catch(() => {});
  }
  if (items.length === 0) return <EmptyState title="No artifacts yet" />;
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-100 text-xs uppercase text-slate-400">
            <th className="px-4 py-2">Type</th>
            <th className="px-4 py-2">Name</th>
            <th className="px-4 py-2">Version</th>
            <th className="px-4 py-2">Stage</th>
            <th className="px-4 py-2">Size</th>
          </tr>
        </thead>
        <tbody>
          {items.map((a) => (
            <tr key={a.id} className="border-b border-slate-50 last:border-0">
              <td className="px-4 py-2"><StatusBadge status="pending" label={a.artifact_type} /></td>
              <td className="px-4 py-2 font-mono text-xs">{a.name}</td>
              <td className="px-4 py-2">v{a.version}</td>
              <td className="px-4 py-2 text-slate-500">{a.stage}</td>
              <td className="px-4 py-2 text-slate-500">{(a.size / 1024).toFixed(1)} KB</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ProjectTabs({ projectId }: { projectId: number }) {
  const [tab, setTab] = useState("Agents");
  const logs = useProject((s) => s.logs);
  return (
    <div className="mt-6">
      <Tabs tabs={["Agents", "Logs", "Tests", "Artifacts"]} active={tab} onChange={setTab} />
      <div className="mt-4">
        {tab === "Agents" && <AgentsTab />}
        {tab === "Logs" && (
          <SectionCard title="Workflow Logs">
            <LogViewer logs={logs} maxHeight={420} />
          </SectionCard>
        )}
        {tab === "Tests" && <TestsTab />}
        {tab === "Artifacts" && <ArtifactsTab projectId={projectId} />}
      </div>
    </div>
  );
}

export function LoadingView() {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-10">
      <Spinner /> <p className="text-sm text-slate-600">Loading project…</p>
    </div>
  );
}
