"use client";

import { useCallback, useEffect, useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { ApiError, api } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { useProject } from "@/store/project";
import { EmptyState, SectionCard, Spinner, Tabs } from "@/components/common";
import type { PlanObj } from "@/types";

export function PlanView({ projectId }: { projectId: number }) {
  const workflow = useProject((s) => s.workflow);
  const refreshWorkflow = useProject((s) => s.refreshWorkflow);
  const [plan, setPlan] = useState<PlanObj | null>(null);
  const [version, setVersion] = useState(0);
  const [tab, setTab] = useState("Prototype Plan");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const token = getToken();
    if (!token) return;
    try {
      const res = await api.getPlan(token, projectId);
      setPlan(res.plan);
      setVersion(res.version);
    } catch {
      setPlan(null);
    }
  }, [projectId]);

  useEffect(() => {
    void load();
  }, [load, workflow?.status]);

  const planning = workflow?.status === "PLANNING" && !plan;

  const generate = async () => {
    const token = getToken();
    if (!token) return;
    setBusy(true);
    setError("");
    try {
      await api.buildPrototype(token, projectId);
      await refreshWorkflow(token, projectId);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to start prototype build");
    } finally {
      setBusy(false);
    }
  };

  if (planning) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-8">
        <Spinner /> <p className="text-sm text-slate-600">Planning Agent is creating your development plan…</p>
      </div>
    );
  }
  if (!plan) return <EmptyState title="No plan yet" hint="Complete requirement analysis first." />;

  const scope = plan.prototype_scope;
  const full = plan.full_application_plan;

  return (
    <div>
      <h2 className="text-lg font-bold text-slate-900">Development Plan {version > 0 && <span className="text-sm font-medium text-slate-400">v{version}</span>}</h2>
      <p className="mb-4 text-sm text-slate-500">AI has created a detailed plan for your prototype and full application.</p>
      <Tabs tabs={["Prototype Plan", "Full Application Plan"]} active={tab} onChange={setTab} />
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        {tab === "Prototype Plan" && (
          <>
            <SectionCard title="Prototype Scope">
              <p className="mb-3 text-sm text-slate-600">{scope.goal}</p>
              <ul className="space-y-1.5">
                {scope.include.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-sm text-slate-700">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" /> {f}
                  </li>
                ))}
              </ul>
            </SectionCard>
            <SectionCard title={`Prototype Screens (${scope.screens.length})`}>
              <ol className="space-y-2">
                {scope.screens.map((s, i) => (
                  <li key={s.name} className="flex items-start gap-2 text-sm text-slate-700">
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-[10px] font-bold text-white">{i + 1}</span>
                    <span><strong>{s.name}</strong> — {s.purpose}</span>
                  </li>
                ))}
              </ol>
            </SectionCard>
          </>
        )}
        {tab === "Full Application Plan" && (
          <>
            <SectionCard title="Engineering Phases">
              <ul className="space-y-2 text-sm text-slate-700">
                {full.phases.map((p) => (
                  <li key={p.name}><strong>{p.name}</strong> — {p.description}</li>
                ))}
              </ul>
            </SectionCard>
            <SectionCard title="Technology Stack">
              <div className="grid gap-2 text-sm text-slate-700">
                <div className="flex justify-between border-b border-slate-100 py-1.5"><span className="text-slate-500">Frontend</span><span className="font-medium">{full.stack.frontend}</span></div>
                <div className="flex justify-between border-b border-slate-100 py-1.5"><span className="text-slate-500">Backend</span><span className="font-medium">{full.stack.backend}</span></div>
                <div className="flex justify-between py-1.5"><span className="text-slate-500">Database</span><span className="font-medium">{full.stack.database}</span></div>
              </div>
            </SectionCard>
          </>
        )}
      </div>
      {plan.revision_notes && (
        <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700">Revision: {plan.revision_notes}</p>
      )}
      <div className="mt-4 flex items-center justify-end gap-3">
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button onClick={() => void generate()} disabled={busy} className="flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-60">
          {busy && <Spinner className="text-white" />} Generate Prototype →
        </button>
      </div>
    </div>
  );
}
