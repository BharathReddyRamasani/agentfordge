"use client";

import { use, useEffect, useState } from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";
import { ApiError, api } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { useProject } from "@/store/project";
import { useProjectStream } from "@/hooks/useProjectStream";
import { Stepper } from "@/components/ui";
import { Tabs } from "@/components/common";
import { AnalysisView } from "@/components/phases/AnalysisView";
import { PlanView } from "@/components/phases/PlanView";
import { PrototypeView } from "@/components/phases/PrototypeView";
import { EngineeringView } from "@/components/phases/EngineeringView";
import { ResultView } from "@/components/phases/ResultView";
import { LoadingView, ProjectTabs } from "@/components/phases/ProjectTabs";
import { Spinner } from "@/components/common";

const PHASES = ["Requirements", "Planning", "Prototype", "Engineering", "Result"];

function phaseFor(status: string): string {
  if (["CREATED", "ANALYZING"].includes(status)) return "Requirements";
  if (["PLANNING", "PLAN_REVISION"].includes(status)) return "Planning";
  if (["PROTOTYPE_BUILDING", "PROTOTYPE_REBUILDING", "AWAITING_REVIEW", "CHANGES_REQUESTED", "APPROVED"].includes(status)) return "Prototype";
  if (status === "COMPLETED") return "Result";
  if (status === "FAILED" || status === "CANCELLED") return "Engineering";
  return "Engineering";
}

export default function ProjectPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const projectId = Number(id);
  const token = getToken();
  const project = useProject((s) => s.project);
  const workflow = useProject((s) => s.workflow);
  const loading = useProject((s) => s.loading);
  const error = useProject((s) => s.error);
  const refresh = useProject((s) => s.refresh);
  const refreshWorkflow = useProject((s) => s.refreshWorkflow);
  const [phase, setPhase] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);

  useProjectStream(token, Number.isFinite(projectId) ? projectId : null);

  useEffect(() => {
    if (token && Number.isFinite(projectId)) void refresh(token, projectId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  useEffect(() => {
    if (workflow && phase === null) setPhase(phaseFor(workflow.status));
  }, [workflow, phase]);

  if (!token) return <LoadingView />;
  if (loading) return <LoadingView />;
  if (error || !project) {
    return <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-sm text-red-700">{error ?? "Project not found."}</div>;
  }

  const active = phase ?? phaseFor(workflow?.status ?? "CREATED");
  const failed = workflow?.status === "FAILED" || workflow?.status === "CANCELLED";
  // Interrupted (not failed, not running, not legitimately waiting): worker died or
  // server restarted mid-job. Safe to resume — regeneration is idempotent.
  const WAITING = new Set(["CREATED", "PLANNING", "AWAITING_REVIEW", "APPROVED", "COMPLETED"]);
  const stuck =
    !!workflow &&
    !failed &&
    !WAITING.has(workflow.status) &&
    !workflow.active_job;

  const retry = async () => {
    if (!token) return;
    setRetrying(true);
    try {
      await api.retry(token, projectId);
      await refreshWorkflow(token, projectId);
    } catch (e) {
      alert(e instanceof ApiError ? e.message : "Retry failed");
    } finally {
      setRetrying(false);
    }
  };

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-xl font-bold text-slate-900">{project.name}</h1>
        <p className="text-sm text-slate-500">
          Status: <strong>{workflow?.status.replace(/_/g, " ")}</strong> · {workflow?.progress ?? 0}% · Prototype v{project.approved_prototype_version ?? prototypeVersionHint()}
        </p>
      </div>

      <Stepper status={workflow?.status ?? "CREATED"} />

      {stuck && (
        <div className="mt-4 flex flex-wrap items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4">
          <AlertTriangle className="h-5 w-5 text-amber-500" />
          <p className="flex-1 text-sm text-amber-800">
            This workflow was interrupted (no active job, status {workflow?.status.replace(/_/g, " ")}).
            It is safe to resume — generation is deterministic and idempotent.
          </p>
          <button onClick={() => void retry()} disabled={retrying} className="flex items-center gap-2 rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-60">
            {retrying ? <Spinner className="text-white" /> : <RotateCcw className="h-4 w-4" />} Resume Workflow
          </button>
        </div>
      )}

      {failed && (
        <div className="mt-4 flex flex-wrap items-center gap-3 rounded-xl border border-red-200 bg-red-50 p-4">
          <AlertTriangle className="h-5 w-5 text-red-500" />
          <p className="flex-1 text-sm text-red-700">{workflow?.last_error ?? "Workflow failed."}</p>
          <button onClick={() => void retry()} disabled={retrying} className="flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-60">
            {retrying ? <Spinner className="text-white" /> : <RotateCcw className="h-4 w-4" />} Retry Workflow
          </button>
        </div>
      )}

      <div className="mt-5">
        <Tabs tabs={PHASES} active={active} onChange={setPhase} />
        <div className="mt-4">
          {active === "Requirements" && <AnalysisView projectId={projectId} />}
          {active === "Planning" && <PlanView projectId={projectId} />}
          {active === "Prototype" && <PrototypeView projectId={projectId} />}
          {active === "Engineering" && <EngineeringView projectId={projectId} />}
          {active === "Result" && (workflow?.status === "COMPLETED" ? <ResultView projectId={projectId} /> : <EngineeringView projectId={projectId} />)}
        </div>
      </div>

      <ProjectTabs projectId={projectId} />
    </div>
  );

  function prototypeVersionHint() {
    return "—";
  }
}
