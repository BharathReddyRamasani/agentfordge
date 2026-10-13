"use client";

import { useCallback, useEffect, useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { ApiError, api } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { useProject } from "@/store/project";
import { EmptyState, SectionCard, Spinner, Tabs } from "@/components/common";
import type { AnalysisObj } from "@/types";

function List({ items }: { items: string[] }) {
  return (
    <ul className="space-y-1.5">
      {items.map((x, i) => (
        <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" /> {x}
        </li>
      ))}
    </ul>
  );
}

export function AnalysisView({ projectId }: { projectId: number }) {
  const workflow = useProject((s) => s.workflow);
  const refreshWorkflow = useProject((s) => s.refreshWorkflow);
  const [analysis, setAnalysis] = useState<AnalysisObj | null>(null);
  const [tab, setTab] = useState("Overview");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const token = getToken();
    if (!token) return;
    try {
      const res = await api.getAnalysis(token, projectId);
      setAnalysis(res.analysis);
    } catch {
      setAnalysis(null);
    }
  }, [projectId]);

  useEffect(() => {
    void load();
  }, [load, workflow?.status]);

  const analyzing = workflow?.status === "ANALYZING" && !analysis;

  const proceed = async () => {
    const token = getToken();
    if (!token) return;
    setBusy(true);
    setError("");
    try {
      await api.startPlanning(token, projectId);
      await refreshWorkflow(token, projectId);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to start planning");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <h2 className="text-lg font-bold text-slate-900">Requirement Analysis</h2>
      <p className="mb-4 text-sm text-slate-500">AI has analyzed your requirements and extracted key information.</p>
      {analyzing || (!analysis && ["ANALYZING", "CREATED"].includes(workflow?.status ?? "")) ? (
        <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-8">
          <Spinner /> <p className="text-sm text-slate-600">AI agents are analyzing your requirements…</p>
        </div>
      ) : !analysis ? (
        <EmptyState title="No analysis yet" />
      ) : (
        <div>
          <Tabs tabs={["Overview", "User Roles", "Features", "User Flow", "Technical"]} active={tab} onChange={setTab} />
          <div className="mt-4 grid gap-4">
            {tab === "Overview" && (
              <>
                <SectionCard title="Project Overview"><p className="text-sm text-slate-700">{analysis.purpose}</p></SectionCard>
                <SectionCard title="Core Value Proposition"><p className="text-sm text-slate-700">{analysis.core_value_proposition}</p></SectionCard>
              </>
            )}
            {tab === "User Roles" && (
              <SectionCard title={`Target Users & Roles (${analysis.user_roles.length})`}>
                <List items={[...analysis.target_users.map((t) => `User group: ${t}`), ...analysis.user_roles.map((r) => `Role: ${r}`)]} />
              </SectionCard>
            )}
            {tab === "Features" && (
              <SectionCard title={`Key Features (${analysis.essential_features.length})`}>
                <ul className="space-y-2">
                  {analysis.essential_features.map((f) => (
                    <li key={f.name} className="flex items-start gap-2 text-sm text-slate-700">
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
                      <span><strong>{f.name}</strong>{f.description ? ` — ${f.description}` : ""}</span>
                    </li>
                  ))}
                </ul>
              </SectionCard>
            )}
            {tab === "User Flow" && (
              <SectionCard title="Primary User Flow">
                <ol className="space-y-2">
                  {analysis.primary_user_flow.map((s, i) => (
                    <li key={i} className="flex items-center gap-3 text-sm text-slate-700">
                      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-xs font-bold text-white">{i + 1}</span> {s}
                    </li>
                  ))}
                </ol>
              </SectionCard>
            )}
            {tab === "Technical" && (
              <>
                <SectionCard title="Functional Requirements">
                  <ul className="space-y-1.5 text-sm text-slate-700">
                    {analysis.functional_requirements.map((r) => <li key={r.id}><strong>{r.id}</strong> — {r.title}: {r.description}</li>)}
                  </ul>
                </SectionCard>
                <SectionCard title="Non-Functional Requirements">
                  <ul className="space-y-1.5 text-sm text-slate-700">
                    {analysis.non_functional_requirements.map((r) => <li key={r.id}><strong>{r.id}</strong> — {r.title}: {r.description}</li>)}
                  </ul>
                </SectionCard>
                <SectionCard title="Constraints & Ambiguities">
                  <List items={[...analysis.constraints, ...analysis.ambiguities.map((a) => `Open: ${a}`)]} />
                </SectionCard>
              </>
            )}
          </div>
          <div className="mt-4 flex items-center justify-end gap-3">
            {error && <p className="text-sm text-red-600">{error}</p>}
            <button onClick={() => void proceed()} disabled={busy} className="flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-60">
              {busy && <Spinner className="text-white" />} Proceed to Planning →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
