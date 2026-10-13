"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, ChevronDown, Send, ThumbsUp, XCircle } from "lucide-react";
import { ApiError, api } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { useProject } from "@/store/project";
import { ConfirmDialog, EmptyState, Spinner } from "@/components/common";
import { cn } from "@/lib/utils";

interface ValCheck {
  name: string;
  mandatory: boolean;
  status: "pass" | "fail" | "skip";
  detail: string;
}

function ValidationReport({ validation }: { validation: { verdict: string; checks: ValCheck[] } | null | undefined }) {
  const [open, setOpen] = useState(false);
  if (!validation) return null;
  const failed = validation.checks.filter((c) => c.mandatory && c.status === "fail");
  const passed = validation.checks.filter((c) => c.status === "pass").length;
  return (
    <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
      <button onClick={() => setOpen(!open)} className="flex w-full items-center justify-between text-sm font-semibold text-slate-700">
        <span className="flex items-center gap-2">
          {validation.verdict === "pass" ? (
            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
          ) : (
            <XCircle className="h-4 w-4 text-red-500" />
          )}
          Validation: {validation.verdict === "pass" ? `${passed} checks passed` : `${failed.length} mandatory check${failed.length === 1 ? "" : "s"} failed`}
        </span>
        <ChevronDown className={cn("h-4 w-4 transition", open && "rotate-180")} />
      </button>
      {open && (
        <ul className="mt-2 space-y-1">
          {validation.checks.map((c) => (
            <li key={c.name} className="flex items-start gap-2 text-xs">
              <span
                className={cn(
                  "mt-0.5 inline-block h-2 w-2 shrink-0 rounded-full",
                  c.status === "pass" && "bg-emerald-500",
                  c.status === "fail" && "bg-red-500",
                  c.status === "skip" && "bg-slate-300"
                )}
              />
              <span className="text-slate-600">
                <strong className="font-mono">{c.name}</strong>
                {!c.mandatory && <span className="text-slate-400"> (optional)</span>} — {c.status}
                {c.detail ? `: ${c.detail}` : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function PrototypeView({ projectId }: { projectId: number }) {
  const workflow = useProject((s) => s.workflow);
  const prototype = useProject((s) => s.prototype);
  const refreshWorkflow = useProject((s) => s.refreshWorkflow);
  const [feedback, setFeedback] = useState("");
  const [busy, setBusy] = useState<"changes" | "approve" | "start" | null>(null);
  const [error, setError] = useState("");
  const [confirmApprove, setConfirmApprove] = useState(false);
  const [version, setVersion] = useState<number | undefined>(undefined);

  const token = getToken();
  const building = ["PROTOTYPE_BUILDING", "PROTOTYPE_REBUILDING", "PLAN_REVISION"].includes(workflow?.status ?? "");
  const inReview = ["AWAITING_REVIEW", "CHANGES_REQUESTED"].includes(workflow?.status ?? "");
  const approved = workflow?.status === "APPROVED";
  const selectedVersion = version ?? prototype?.version;
  const ready = prototype?.status === "ready";
  const needsAttention = prototype?.status === "needs_attention";
  const eligible = inReview && ready;

  useEffect(() => {
    setVersion(undefined);
  }, [prototype?.version]);

  const act = async (kind: "changes" | "approve" | "start") => {
    if (!token) return;
    setBusy(kind);
    setError("");
    try {
      if (kind === "changes") {
        await api.submitFeedback(token, projectId, feedback);
        setFeedback("");
      } else if (kind === "approve") {
        await api.approve(token, projectId, "Approved via web review", selectedVersion);
      } else {
        await api.startEngineering(token, projectId);
      }
      await refreshWorkflow(token, projectId);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Action failed");
    } finally {
      setBusy(null);
      setConfirmApprove(false);
    }
  };

  if (building || (!prototype && !inReview && !approved)) {
    return (
      <div>
        <div className="flex items-center gap-3 rounded-xl border border-indigo-200 bg-indigo-50 p-5">
          <Spinner />
          <div>
            <p className="text-sm font-semibold text-indigo-900">Prototype {workflow?.status === "PROTOTYPE_REBUILDING" || workflow?.status === "PLAN_REVISION" ? "is being rebuilt" : "is being generated"}…</p>
            <p className="text-xs text-indigo-700">Stages: build → render → automated validation. Review actions unlock only when validation passes.</p>
          </div>
        </div>
      </div>
    );
  }
  if (!prototype) return <EmptyState title="No prototype yet" />;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-bold text-slate-900">Prototype (Version {prototype.version})</h2>
          <p className="text-sm text-slate-500">Interact with the preview and provide your feedback.</p>
        </div>
        <select
          value={selectedVersion}
          onChange={(e) => setVersion(Number(e.target.value))}
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm"
        >
          {prototype.versions.map((v) => (
            <option key={v.version} value={v.version}>Version History — v{v.version} ({v.status})</option>
          ))}
        </select>
      </div>

      {needsAttention && (
        <div className="mb-4 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-red-500" />
          <div className="text-sm text-red-700">
            <strong>This prototype version failed automated validation</strong> and cannot be approved.
            Review the failed checks below, then request changes to rebuild it — or pick another version.
          </div>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm lg:col-span-2">
          <iframe
            key={selectedVersion}
            title="Prototype preview"
            src={token ? api.previewUrl(projectId, token, version) : ""}
            sandbox="allow-scripts allow-forms"
            className="h-[520px] w-full bg-white"
          />
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="font-bold text-slate-900">Feedback</h3>
          {approved ? (
            <div>
              <p className="mt-2 rounded-lg bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-700">
                Prototype v{prototype.version} approved — ready for autonomous engineering.
              </p>
              <button onClick={() => void act("start")} disabled={busy !== null} className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60">
                {busy === "start" && <Spinner className="text-white" />} Start Autonomous Engineering
              </button>
            </div>
          ) : (
            <div>
              <div className={cn("rounded-lg px-3 py-2 text-xs font-medium", eligible ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500")}>
                {eligible
                  ? `Prototype v${prototype.version} passed validation — ready for your review.`
                  : building
                    ? "Agents are building and validating — review actions unlock on success."
                    : needsAttention
                      ? "This version failed validation — approval is disabled."
                      : "Review actions unlock when the prototype passes validation."}
              </div>
              <textarea
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                rows={5}
                placeholder="Describe the changes you want…"
                disabled={!inReview}
                className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:cursor-not-allowed disabled:bg-slate-50"
              />
              <button onClick={() => void act("changes")} disabled={busy !== null || !inReview || feedback.trim().length < 3} title={inReview ? "Send feedback to revise the plan and rebuild" : "Available while a prototype awaits review"} className="mt-2 flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50">
                {busy === "changes" ? <Spinner className="text-white" /> : <Send className="h-4 w-4" />} Request Changes
              </button>
              <button onClick={() => setConfirmApprove(true)} disabled={busy !== null || !eligible} title={eligible ? `Approve prototype v${selectedVersion}` : "Approval requires a validated prototype awaiting review"} className="mt-2 flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50">
                <ThumbsUp className="h-4 w-4" /> Approve Prototype{selectedVersion ? ` v${selectedVersion}` : ""}
              </button>
            </div>
          )}
          {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
          <ValidationReport validation={prototype.validation as { verdict: string; checks: ValCheck[] } | null} />
          <div className="mt-4 border-t border-slate-100 pt-3 text-xs text-slate-500">
            <p className="font-semibold text-slate-600">Flow demonstrated</p>
            <p className="mt-1">{prototype.spec.user_flow.join(" → ")}</p>
          </div>
        </div>
      </div>

      {confirmApprove && (
        <ConfirmDialog
          title={`Approve prototype v${selectedVersion}?`}
          body="Approval locks this exact version as the source of truth and starts full-scale autonomous engineering. Continue?"
          confirmLabel="Approve Prototype"
          onCancel={() => setConfirmApprove(false)}
          onConfirm={() => void act("approve")}
        />
      )}
    </div>
  );
}
