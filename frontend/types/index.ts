export interface User {
  id: number;
  email: string;
  name: string;
  created_at?: string;
}

export interface Project {
  id: number;
  name: string;
  description: string;
  status: string;
  current_stage: string;
  progress: number;
  approved_prototype_version: number | null;
  created_at: string;
  updated_at: string;
  owner_id: number;
}

export interface StageState {
  key: string;
  label: string;
  status: "pending" | "running" | "completed" | "failed" | "skipped";
}

export interface Workflow {
  status: string;
  stage: string;
  progress: number;
  current_agent: string | null;
  stages: StageState[];
  last_error: string | null;
  cancel_requested: boolean;
  active_job: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface AgentStatus {
  agent: string;
  stage: string;
  status: string;
  attempts: number;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface ProjectEvent {
  id: number;
  stage: string;
  agent: string;
  event: string;
  message: string;
  status: string;
  progress: number;
  created_at: string;
}

export interface AnalysisObj {
  project_name: string;
  purpose: string;
  target_users: string[];
  user_roles: string[];
  core_value_proposition: string;
  essential_features: { name: string; description: string }[];
  primary_user_flow: string[];
  functional_requirements: { id: string; title: string; description: string }[];
  non_functional_requirements: { id: string; title: string; description: string }[];
  constraints: string[];
  ambiguities: string[];
}

export interface PlanObj {
  summary: string;
  prototype_scope: {
    goal: string;
    screens: { name: string; purpose: string; sections: string[] }[];
    interactions: string[];
    include: string[];
    out_of_scope: string[];
  };
  full_application_plan: {
    phases: { name: string; description: string; tasks: string[] }[];
    stack: { frontend: string; backend: string; database: string };
  };
  feature_priorities: { feature: string; priority: string }[];
  revision_notes: string;
}

export interface PrototypeSpec {
  app_name: string;
  tagline: string;
  theme: { primary_color: string; accent_color: string; background_color: string };
  screens: unknown[];
  navigation: string[];
  user_flow: string[];
  features: string[];
  sample_data: Record<string, unknown>;
}

export interface PrototypeInfo {
  id: number;
  version: number;
  status: string;
  spec: PrototypeSpec;
  created_at: string;
  versions: { version: number; status: string; created_at: string }[];
  validation: { version: number; verdict: string; checks: { name: string; mandatory: boolean; status: string; detail: string }[] } | null;
}

export interface TestRun {
  run_id: string;
  iteration: number;
  total: number;
  passed: number;
  failed: number;
  status: string;
  output: string;
  created_at: string;
}

export interface Artifact {
  id: number;
  artifact_type: string;
  name: string;
  version: number;
  stage: string;
  size: number;
  created_at: string;
}

export interface DownloadPackage {
  kind: string;
  filename: string;
  size: number;
  url: string;
}

export interface StreamMessage {
  event: string;
  event_type: string;
  project_id: number;
  stage: string;
  agent: string;
  message: string;
  status: string;
  progress: number;
  timestamp: string;
}
