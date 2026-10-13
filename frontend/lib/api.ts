import type {
  AgentStatus,
  AnalysisObj,
  Artifact,
  DownloadPackage,
  PlanObj,
  Project,
  ProjectEvent,
  PrototypeInfo,
  TestRun,
  User,
  Workflow,
} from "@/types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function apiUrl(path: string, token?: string): string {
  const sep = path.includes("?") ? "&" : "?";
  return token ? `${API_URL}${path}${sep}token=${encodeURIComponent(token)}` : `${API_URL}${path}`;
}

export class ApiError extends Error {
  code: string;
  status: number;
  constructor(code: string, status: number, message: string) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

async function request<T>(path: string, token: string | null, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_URL}${path}`, { ...init, headers: { ...headers, ...(init?.headers as Record<string, string>) } });
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (body?.error) throw new ApiError(body.error.code ?? "ERROR", res.status, body.error.message ?? "Request failed");
    throw new ApiError("ERROR", res.status, `Request failed (${res.status})`);
  }
  return body as T;
}

const get = <T>(path: string, token: string | null) => request<T>(path, token);
const post = <T>(path: string, token: string | null, data?: unknown) =>
  request<T>(path, token, { method: "POST", body: data === undefined ? undefined : JSON.stringify(data) });
const del_ = <T>(path: string, token: string | null) => request<T>(path, token, { method: "DELETE" });

export const api = {
  register: (email: string, name: string, password: string) =>
    post<{ access_token: string; user: User }>("/api/auth/register", null, { email, name, password }),
  login: (email: string, password: string) =>
    post<{ access_token: string; user: User }>("/api/auth/login", null, { email, password }),
  me: (token: string) => get<User>("/api/auth/me", token),
  logout: (token: string) => post<{ status: string }>("/api/auth/logout", token),

  createProject: (token: string, name: string, description: string) =>
    post<Project>("/api/projects", token, { name, description }),
  listProjects: (token: string) =>
    get<{ items: Project[]; total: number }>(`/api/projects?limit=200`, token),
  getProject: (token: string, id: number) => get<Project>(`/api/projects/${id}`, token),
  deleteProject: (token: string, id: number) => del_(`/api/projects/${id}`, token),

  submitRequirement: (token: string, id: number, description: string) =>
    post(`/api/projects/${id}/requirements`, token, { description }),
  analyze: (token: string, id: number) => post(`/api/projects/${id}/requirements/analyze`, token),
  getAnalysis: (token: string, id: number) =>
    get<{ version: number; analysis: AnalysisObj }>(`/api/projects/${id}/analysis`, token),

  startPlanning: (token: string, id: number) => post(`/api/projects/${id}/planning`, token),
  getPlan: (token: string, id: number) =>
    get<{ version: number; plan: PlanObj }>(`/api/projects/${id}/plan`, token),

  buildPrototype: (token: string, id: number) => post(`/api/projects/${id}/prototype/generate`, token),
  getPrototype: (token: string, id: number) => get<PrototypeInfo>(`/api/projects/${id}/prototype`, token),
  submitFeedback: (token: string, id: number, feedback: string) =>
    post(`/api/projects/${id}/prototype/feedback`, token, { feedback }),
  approve: (token: string, id: number, comment?: string, version?: number) =>
    post(`/api/projects/${id}/prototype/approve`, token, { comment: comment ?? "", prototype_version: version ?? null }),
  previewUrl: (id: number, token: string, version?: number) =>
    apiUrl(`/api/projects/${id}/prototype/preview${version ? `?version=${version}` : ""}`, token),
  applicationPreviewUrl: (id: number, token: string) =>
    apiUrl(`/api/projects/${id}/application/preview`, token),

  startEngineering: (token: string, id: number) => post(`/api/projects/${id}/engineering/start`, token),
  cancel: (token: string, id: number) => post(`/api/projects/${id}/cancel`, token),
  retry: (token: string, id: number) => post(`/api/projects/${id}/retry`, token),

  getWorkflow: (token: string, id: number) => get<Workflow>(`/api/projects/${id}/workflow`, token),
  getAgents: (token: string, id: number) => get<AgentStatus[]>(`/api/projects/${id}/agents`, token),
  getLogs: (token: string, id: number) => get<ProjectEvent[]>(`/api/projects/${id}/logs?limit=300`, token),
  getTests: (token: string, id: number) => get<TestRun[]>(`/api/projects/${id}/testing`, token),
  getArtifacts: (token: string, id: number) => get<Artifact[]>(`/api/projects/${id}/artifacts`, token),
  getDownloads: (token: string, id: number) => get<DownloadPackage[]>(`/api/projects/${id}/downloads`, token),
  downloadUrl: (id: number, kind: string, token: string) =>
    apiUrl(`/api/projects/${id}/download?type=${kind}`, token),
  streamUrl: (id: number, token: string) => apiUrl(`/api/projects/${id}/events/stream`, token),
};
