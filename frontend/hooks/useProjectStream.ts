"use client";

import { useEffect, useRef } from "react";
import { api } from "@/lib/api";
import { useProject } from "@/store/project";

const TERMINAL = new Set(["COMPLETED", "FAILED", "CANCELLED"]);

/** Live updates: SSE stream with polling fallback while the workflow is active. */
export function useProjectStream(token: string | null, projectId: number | null) {
  const refreshWorkflow = useProject((s) => s.refreshWorkflow);
  const workflow = useProject((s) => s.workflow);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!token || !projectId) return;
    let es: EventSource | null = null;
    let stopped = false;

    const poll = () => {
      void refreshWorkflow(token, projectId);
    };
    poll();
    timer.current = setInterval(() => {
      const w = useProject.getState().workflow;
      if (!w || TERMINAL.has(w.status)) {
        if (timer.current) clearInterval(timer.current);
        return;
      }
      poll();
    }, 4000);

    try {
      es = new EventSource(api.streamUrl(projectId, token));
      es.onmessage = () => {
        if (!stopped) void refreshWorkflow(token, projectId);
      };
      es.onerror = () => {
        es?.close();
      };
    } catch {
      /* SSE unavailable — polling covers updates */
    }

    return () => {
      stopped = true;
      es?.close();
      if (timer.current) clearInterval(timer.current);
    };
  }, [token, projectId, refreshWorkflow]);

  return { workflow };
}
