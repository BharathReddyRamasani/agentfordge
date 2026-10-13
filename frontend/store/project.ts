"use client";

import { create } from "zustand";
import { api } from "@/lib/api";
import type { AgentStatus, Project, ProjectEvent, PrototypeInfo, TestRun, Workflow } from "@/types";

interface ProjectState {
  project: Project | null;
  workflow: Workflow | null;
  agents: AgentStatus[];
  logs: ProjectEvent[];
  tests: TestRun[];
  prototype: PrototypeInfo | null;
  loading: boolean;
  error: string | null;
  setProject: (p: Project | null) => void;
  refresh: (token: string, id: number) => Promise<void>;
  refreshWorkflow: (token: string, id: number) => Promise<void>;
}

const TERMINAL = new Set(["COMPLETED", "FAILED", "CANCELLED"]);

export const useProject = create<ProjectState>((set, get) => ({
  project: null,
  workflow: null,
  agents: [],
  logs: [],
  tests: [],
  prototype: null,
  loading: true,
  error: null,
  setProject: (p) => set({ project: p }),
  refresh: async (token, id) => {
    try {
      const [project, workflow, agents, logs, tests] = await Promise.all([
        api.getProject(token, id),
        api.getWorkflow(token, id),
        api.getAgents(token, id),
        api.getLogs(token, id),
        api.getTests(token, id),
      ]);
      let prototype: PrototypeInfo | null = get().prototype;
      try {
        prototype = await api.getPrototype(token, id);
      } catch {
        prototype = null;
      }
      set({ project, workflow, agents, logs, tests, prototype, loading: false, error: null });
    } catch (e) {
      set({ loading: false, error: e instanceof Error ? e.message : "Failed to load project" });
    }
  },
  refreshWorkflow: async (token, id) => {
    try {
      const [project, workflow, agents, logs] = await Promise.all([
        api.getProject(token, id),
        api.getWorkflow(token, id),
        api.getAgents(token, id),
        api.getLogs(token, id),
      ]);
      set({ project, workflow, agents, logs });
      if (workflow.status === "AWAITING_REVIEW" || TERMINAL.has(workflow.status)) {
        try {
          const prototype = await api.getPrototype(token, id);
          set({ prototype });
        } catch {
          /* not built yet */
        }
      }
      if (TERMINAL.has(workflow.status)) {
        const tests = await api.getTests(token, id).catch(() => get().tests);
        set({ tests });
      }
    } catch {
      /* transient; next poll retries */
    }
  },
}));
