"""Frontend Agent codegen: generates a REAL React 18 + Vite + TypeScript + Tailwind
application (dynamic SPA consuming the generated FastAPI backend). Materialized into
the project workspace, built with Vite during engineering, and served as the live
full-scale application preview.

React engineering principles applied: component composition, hooks-based state,
context for auth, protected routing, typed API layer, reusable UI primitives."""

import json

from app.services.codegen.entities import normalize_entities


def _label(name: str) -> str:
    return "".join(" " + c if c.isupper() else c for c in name).strip()


def _pkg_name(app_name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in app_name.lower()).strip("-") or "generated-app"


def _entity_configs(entities: list[dict]) -> list[dict]:
    """Public entity config consumed by the generic EntityPage (fields are user-editable)."""
    out = []
    for e in entities:
        fields = []
        for fname, ftype in e.get("fields", []):
            if fname in ("password_hash", "password", "id") or fname.endswith("_id"):
                continue
            ui_type = {"integer": "number", "float": "number", "date": "date", "datetime": "date", "text": "textarea", "boolean": "text"}.get(ftype, "text")
            fields.append({"name": fname, "label": _label(fname) or fname.title(), "type": ui_type})
        out.append(
            {
                "key": e["name"].lower(),
                "plural": (e.get("table") or e["name"].lower() + "s"),
                "label": _label(e["name"]) or e["name"],
                "fields": fields,
            }
        )
    return out


def generate_package_json(entities: list[dict], app_name: str) -> str:
    pkg = {
        "name": _pkg_name(app_name),
        "private": True,
        "version": "1.0.0",
        "type": "module",
        "scripts": {"dev": "vite", "build": "vite build", "preview": "vite preview"},
        "dependencies": {
            "react": "^18.3.1",
            "react-dom": "^18.3.1",
            "react-router-dom": "^6.28.0",
            "lucide-react": "^0.469.0",
        },
        "devDependencies": {
            "@types/react": "^18.3.12",
            "@types/react-dom": "^18.3.1",
            "@vitejs/plugin-react": "^4.3.4",
            "autoprefixer": "^10.4.20",
            "postcss": "^8.4.49",
            "tailwindcss": "^3.4.17",
            "typescript": "^5.6.3",
            "vite": "^5.4.11",
        },
    }
    return json.dumps(pkg, indent=2) + "\n"


def generate_vite_config() -> str:
    return """import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://localhost:8001", changeOrigin: true } },
  },
  build: { outDir: "dist", sourcemap: false },
});
"""


def generate_tsconfig() -> str:
    return json.dumps(
        {
            "compilerOptions": {
                "target": "ES2020",
                "lib": ["ES2020", "DOM", "DOM.Iterable"],
                "module": "ESNext",
                "skipLibCheck": True,
                "moduleResolution": "bundler",
                "resolveJsonModule": True,
                "isolatedModules": True,
                "noEmit": True,
                "jsx": "react-jsx",
                "strict": True,
            },
            "include": ["src"],
        },
        indent=2,
    ) + "\n"


def generate_tailwind_config() -> str:
    return """/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: { extend: { fontFamily: { sans: ["Inter", "system-ui", "sans-serif"] } } },
  plugins: [],
};
"""


def generate_postcss_config() -> str:
    return """export default {
  plugins: { tailwindcss: {}, autoprefixer: {} },
};
"""


def generate_index_html(app_name: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
    <title>{app_name}</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
"""


def generate_main_tsx() -> str:
    return """import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AuthProvider } from "./context/AuthContext";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>
);
"""


def _sanitize_hex(value: str, fallback: str) -> str:
    import re

    return value if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value) else fallback


def generate_index_css(theme: dict | None = None) -> str:
    theme = theme or {}
    brand = _sanitize_hex(theme.get("primary_color", ""), "#4f46e5")
    brand_dark = _sanitize_hex(theme.get("accent_color", ""), "#312e81")
    return f""":root {{
  --brand: {brand};
  --brand-dark: {brand_dark};
}}

@tailwind base;
@tailwind components;
@tailwind utilities;

body {{
  @apply bg-slate-50 text-slate-900 antialiased;
}}

/* Brand identity derived from the approved prototype theme */
.brand-gradient {{
  background-image: linear-gradient(135deg, var(--brand), var(--brand-dark));
}}
.brand-bg {{
  background-color: var(--brand);
}}
.brand-text {{
  color: var(--brand);
}}
.btn-brand {{
  background-color: var(--brand);
  color: #fff;
}}
.btn-brand:hover {{
  filter: brightness(0.92);
}}

::-webkit-scrollbar {{
  width: 8px;
  height: 8px;
}}
::-webkit-scrollbar-thumb {{
  @apply bg-slate-300 rounded-full;
}}

@keyframes fadeUp {{
  from {{
    opacity: 0;
    transform: translateY(6px);
  }}
  to {{
    opacity: 1;
    transform: none;
  }}
}}

.animate-fade-up {{
  animation: fadeUp 0.3s ease both;
}}
"""


def generate_config_ts() -> str:
    return """// Base URL of the generated backend API.
// Same-origin when the built app is served by the backend; override for dev deployments.
export const API_BASE: string = (window as any).__API_BASE__ ?? "";
"""


def generate_types_ts(entities: list[dict]) -> str:
    configs = _entity_configs(entities)
    return f"""export type FieldType = "text" | "number" | "date" | "textarea";

export interface EntityField {{
  name: string;
  label: string;
  type: FieldType;
}}

export interface EntityConfig {{
  key: string;
  plural: string;
  label: string;
  fields: EntityField[];
}}

export type Row = Record<string, any>;

export const ENTITIES: EntityConfig[] = {json.dumps(configs, indent=2)};

export function entityByKey(key: string | undefined): EntityConfig | undefined {{
  return ENTITIES.find((e) => e.key === key);
}}
"""


def generate_api_client_ts() -> str:
    return """import { API_BASE } from "../config";

const TOKEN_KEY = "app_token";

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) ?? "";
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function apiFetch<T = any>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json", ...((options.headers as any) ?? {}) };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, (data as any).detail ?? `Request failed (${res.status})`);
  return data as T;
}

export const api = {
  register: (name: string, email: string, password: string) =>
    apiFetch<{ id: number }>("/api/auth/register", { method: "POST", body: JSON.stringify({ name, email, password }) }),
  login: (email: string, password: string) =>
    apiFetch<{ access_token: string; user: { id: number; email: string; name: string } }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => apiFetch<{ id: number; email: string; name: string }>("/api/auth/me"),
  list: (plural: string) => apiFetch<Row[]>(`/api/${plural}`),
  create: (plural: string, body: Row) => apiFetch<Row>(`/api/${plural}`, { method: "POST", body: JSON.stringify(body) }),
  update: (plural: string, id: number, body: Row) =>
    apiFetch<Row>(`/api/${plural}/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  remove: (plural: string, id: number) => apiFetch<void>(`/api/${plural}/${id}`, { method: "DELETE" }),
};
"""


def generate_auth_context_tsx() -> str:
    return """import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, getToken, setToken } from "../api/client";

interface AuthUser {
  id: number;
  email: string;
  name: string;
}

interface AuthState {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState>(null as any);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    if (!getToken()) {
      setLoading(false);
      return;
    }
    api
      .me()
      .then((u) => setUser(u))
      .catch(() => setToken(null))
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.login(email, password);
    setToken(res.access_token);
    setUser(res.user);
  }, []);

  const register = useCallback(async (name: string, email: string, password: string) => {
    await api.register(name, email, password);
    const res = await api.login(email, password);
    setToken(res.access_token);
    setUser(res.user);
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  const value = useMemo(() => ({ user, loading, login, register, logout }), [user, loading, login, register, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  return useContext(AuthContext);
}
"""


def generate_ui_tsx() -> str:
    return """import { X } from "lucide-react";
import { useEffect } from "react";

export function Button({ children, variant = "primary", className = "", ...props }: {
  children: React.ReactNode;
  variant?: "primary" | "outline" | "danger" | "ghost";
  className?: string;
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const styles = {
    primary: "bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm",
    outline: "bg-white text-slate-700 border border-slate-300 hover:bg-slate-50",
    danger: "bg-red-50 text-red-600 border border-red-200 hover:bg-red-100",
    ghost: "text-slate-500 hover:bg-slate-100",
  }[variant];
  return (
    <button className={`inline-flex items-center justify-center gap-1.5 rounded-lg px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${styles} ${className}`} {...props}>
      {children}
    </button>
  );
}

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`rounded-xl border border-slate-200 bg-white shadow-sm ${className}`}>{children}</div>;
}

export function StatCard({ label, value, tint = "indigo" }: { label: string; value: string | number; tint?: string }) {
  const tints: Record<string, string> = {
    indigo: "from-indigo-500 to-indigo-700",
    emerald: "from-emerald-500 to-emerald-700",
    amber: "from-amber-500 to-amber-600",
    sky: "from-sky-500 to-sky-700",
  };
  return (
    <Card className="p-5">
      <div className={`inline-flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br ${tints[tint] ?? tints.indigo} text-sm font-bold text-white`}>
        {String(value).slice(0, 2)}
      </div>
      <p className="mt-2 text-2xl font-bold text-slate-900">{value}</p>
      <p className="text-sm text-slate-500">{label}</p>
    </Card>
  );
}

export function Badge({ text }: { text: string }) {
  const lowered = (text || "").toLowerCase();
  const style = lowered.includes("cancel") || lowered.includes("fail") || lowered.includes("reject")
    ? "bg-red-100 text-red-700"
    : lowered.includes("pending") || lowered.includes("preparing") || lowered.includes("processing")
      ? "bg-amber-100 text-amber-700"
      : lowered.includes("complete") || lowered.includes("deliver") || lowered.includes("done") || lowered.includes("confirm") || lowered.includes("active")
        ? "bg-emerald-100 text-emerald-700"
        : "bg-indigo-100 text-indigo-700";
  return <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${style}`}>{text}</span>;
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 px-6 py-10 text-center">
      <p className="font-semibold text-slate-700">{title}</p>
      {hint && <p className="mt-1 text-sm text-slate-500">{hint}</p>}
    </div>
  );
}

export function Spinner() {
  return (
    <div className="flex items-center justify-center py-10">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-indigo-200 border-t-indigo-600" />
    </div>
  );
}

export function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4" onClick={onClose}>
      <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl animate-fade-up" onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-bold text-slate-900">{title}</h3>
          <button onClick={onClose} className="rounded-lg p-1 text-slate-400 hover:bg-slate-100">
            <X className="h-5 w-5" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Toast({ message }: { message: string }) {
  if (!message) return null;
  return (
    <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-xl bg-slate-950 px-5 py-3 text-sm font-medium text-white shadow-2xl animate-fade-up">
      {message}
    </div>
  );
}
"""


def generate_layout_tsx(entities: list[dict], app_name: str) -> str:
    return f"""import {{ LayoutDashboard, LogOut, UserCircle }} from "lucide-react";
import {{ Link, NavLink, Outlet, useNavigate }} from "react-router-dom";
import {{ useAuth }} from "../context/AuthContext";
import {{ ENTITIES }} from "../entities";

export default function Layout() {{
  const {{ user, logout }} = useAuth();
  const navigate = useNavigate();

  const doLogout = () => {{
    logout();
    navigate("/login");
  }};

  return (
    <div className="flex min-h-screen">
      <aside className="hidden w-64 shrink-0 flex-col bg-slate-950 text-slate-200 lg:flex">
        <div className="px-5 pb-5 pt-6">
          <span className="text-lg font-bold text-white">{app_name}</span>
          <p className="text-xs text-slate-400">Autonomous workspace</p>
        </div>
        <nav className="flex-1 space-y-1 px-3">
          <NavLink to="/" end className={{({{ isActive }}) => `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium ${{isActive ? "bg-indigo-600 text-white" : "text-slate-300 hover:bg-slate-800"}}`}}>
            <LayoutDashboard className="h-4 w-4" /> Dashboard
          </NavLink>
          {{ENTITIES.map((e) => (
            <NavLink key={{e.key}} to={{`/e/${{e.key}}`}} className={{({{ isActive }}) => `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium ${{isActive ? "bg-indigo-600 text-white" : "text-slate-300 hover:bg-slate-800"}}`}}>
              <span className="h-1.5 w-1.5 rounded-full bg-current" /> {{e.label}}s
            </NavLink>
          ))}}
        </nav>
        <div className="border-t border-slate-800 p-4">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-indigo-600 text-xs font-bold text-white">
              {{(user?.name ?? "U").slice(0, 2).toUpperCase()}}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-white">{{user?.name}}</p>
              <p className="truncate text-xs text-slate-400">{{user?.email}}</p>
            </div>
            <button title="Logout" onClick={{doLogout}} className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-white">
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      <div className="min-w-0 flex-1">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-4">
          <p className="font-bold text-slate-900">{app_name}</p>
          <div className="flex items-center gap-3">
            <Link to="/profile" className="flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-indigo-600">
              <UserCircle className="h-5 w-5" /> {{user?.name?.split(" ")[0]}}
            </Link>
            <button onClick={{doLogout}} className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 lg:hidden">
              Logout
            </button>
          </div>
        </header>
        <main className="mx-auto max-w-6xl p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}}
"""


def generate_dashboard_tsx(entities: list[dict], app_name: str, tagline: str) -> str:
    return f"""import {{ useEffect, useState }} from "react";
import {{ api }} from "../api/client";
import {{ ENTITIES, Row }} from "../entities";
import {{ Card, EmptyState, Spinner, StatCard, Badge }} from "../components/ui";

const TINTS = ["indigo", "emerald", "amber", "sky"];

export default function Dashboard() {{
  const [counts, setCounts] = useState<Record<string, number>>({{}});
  const [recent, setRecent] = useState<Record<string, Row[]>>({{}});
  const [loading, setLoading] = useState(true);

  useEffect(() => {{
    let alive = true;
    Promise.all(
      ENTITIES.map((e) =>
        api
          .list(e.plural)
          .then((rows: Row[]) => [e.plural, rows] as const)
          .catch(() => [e.plural, [] as Row[]] as const)
      )
    ).then((entries) => {{
      if (!alive) return;
      const c: Record<string, number> = {{}};
      const r: Record<string, Row[]> = {{}};
      for (const [plural, rows] of entries) {{
        c[plural] = rows.length;
        r[plural] = rows.slice(0, 4);
      }}
      setCounts(c);
      setRecent(r);
      setLoading(false);
    }});
    return () => {{
      alive = false;
    }};
  }}, []);

  return (
    <div className="animate-fade-up">
      <div className="rounded-2xl bg-gradient-to-br from-indigo-600 via-indigo-700 to-slate-900 p-8 text-white shadow-lg">
        <h1 className="text-2xl font-extrabold">{app_name}</h1>
        <p className="mt-1 max-w-xl text-sm text-indigo-100">{tagline}</p>
      </div>

      <div className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {{ENTITIES.slice(0, 4).map((e, i) => (
          <StatCard key={{e.key}} label={{`${{e.label}}s`}} value={{loading ? "…" : counts[e.plural] ?? 0}} tint={{TINTS[i % TINTS.length]}} />
        ))}}
      </div>

      {{ENTITIES.slice(0, 2).map((e) => (
        <Card key={{e.key}} className="mt-5 p-5">
          <h2 className="mb-3 font-bold text-slate-900">Recent {{e.label}}s</h2>
          {{loading ? (
            <Spinner />
          ) : (recent[e.plural] ?? []).length === 0 ? (
            <EmptyState title={{`No {{e.label.toLowerCase()}}s yet`}} />
          ) : (
            <div className="divide-y divide-slate-100">
              {{(recent[e.plural] ?? []).map((row, idx) => (
                <div key={{row.id ?? idx}} className="flex items-center justify-between gap-3 py-2.5 text-sm">
                  <span className="truncate font-medium text-slate-700">
                    {{row[e.fields[0]?.name ?? "id"] ?? `#${{row.id ?? idx + 1}}`}}
                  </span>
                  {{"status" in row ? <Badge text={{String(row.status)}} /> : <span className="text-xs text-slate-400">#{{row.id}}</span>}}
                </div>
              ))}}
            </div>
          )}}
        </Card>
      ))}}
    </div>
  );
}}
"""


def generate_entity_page_tsx() -> str:
    return """import { useCallback, useEffect, useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { api, ApiError } from "../api/client";
import type { EntityConfig, Row } from "../entities";
import { Badge, Button, Card, EmptyState, Modal, Spinner, Toast } from "../components/ui";

export default function EntityPage({ entity }: { entity: EntityConfig }) {
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Row | null>(null);
  const [form, setForm] = useState<Row>({});
  const [toast, setToast] = useState("");
  const [error, setError] = useState("");

  const flash = useCallback((msg: string) => {
    setToast(msg);
    window.setTimeout(() => setToast(""), 2400);
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setRows(await api.list(entity.plural));
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load records");
    } finally {
      setLoading(false);
    }
  }, [entity.plural]);

  useEffect(() => {
    void load();
  }, [load]);

  const openCreate = () => {
    setEditing(null);
    setForm({});
    setModalOpen(true);
  };

  const openEdit = (row: Row) => {
    setEditing(row);
    setForm({ ...row });
    setModalOpen(true);
  };

  const save = async () => {
    try {
      if (editing?.id) {
        await api.update(entity.plural, editing.id, form);
        flash("Record updated");
      } else {
        await api.create(entity.plural, form);
        flash("Record created");
      }
      setModalOpen(false);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Save failed");
      setModalOpen(false);
    }
  };

  const remove = async (id: number) => {
    if (!window.confirm(`Delete this ${entity.label.toLowerCase()}?`)) return;
    try {
      await api.remove(entity.plural, id);
      flash("Record deleted");
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Delete failed");
    }
  };

  const setField = (name: string, value: string) => setForm((f) => ({ ...f, [name]: value }));

  return (
    <div className="animate-fade-up">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-slate-900">{entity.label}s</h1>
          <p className="text-sm text-slate-500">Create, edit and manage {entity.label.toLowerCase()} records.</p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4" /> Add {entity.label}
        </Button>
      </div>

      {error && <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}

      <Card>
        {loading ? (
          <Spinner />
        ) : rows.length === 0 ? (
          <EmptyState title={`No ${entity.label.toLowerCase()}s yet`} hint={`Add your first ${entity.label.toLowerCase()} to get started.`} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-xs uppercase tracking-wide text-slate-400">
                  <th className="px-5 py-3">ID</th>
                  {entity.fields.map((f) => (
                    <th key={f.name} className="px-5 py-3">{f.label}</th>
                  ))}
                  <th className="px-5 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row, idx) => (
                  <tr key={row.id ?? idx} className="border-b border-slate-50 transition last:border-0 hover:bg-slate-50/70">
                    <td className="px-5 py-3 text-xs text-slate-400">#{row.id ?? idx + 1}</td>
                    {entity.fields.map((f) => (
                      <td key={f.name} className="px-5 py-3 text-slate-700">
                        {f.name === "status" ? <Badge text={String(row[f.name] ?? "active")} /> : String(row[f.name] ?? "—")}
                      </td>
                    ))}
                    <td className="px-5 py-3 text-right">
                      <button onClick={() => openEdit(row)} className="mr-1 rounded-lg p-2 text-slate-400 hover:bg-indigo-50 hover:text-indigo-600" title="Edit">
                        <Pencil className="h-4 w-4" />
                      </button>
                      <button onClick={() => row.id !== undefined && void remove(row.id)} className="rounded-lg p-2 text-slate-400 hover:bg-red-50 hover:text-red-600" title="Delete">
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {modalOpen && (
        <Modal title={editing ? `Edit ${entity.label}` : `New ${entity.label}`} onClose={() => setModalOpen(false)}>
          <div className="grid gap-3">
            {entity.fields.map((f) => (
              <label key={f.name} className="block text-sm font-semibold text-slate-600">
                {f.label}
                {f.type === "textarea" ? (
                  <textarea rows={3} value={form[f.name] ?? ""} onChange={(e) => setField(f.name, e.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" />
                ) : (
                  <input type={f.type} value={form[f.name] ?? ""} onChange={(e) => setField(f.name, e.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" />
                )}
              </label>
            ))}
            <div className="mt-2 flex justify-end gap-2">
              <Button variant="outline" onClick={() => setModalOpen(false)}>Cancel</Button>
              <Button onClick={() => void save()}>Save</Button>
            </div>
          </div>
        </Modal>
      )}

      <Toast message={toast} />
    </div>
  );
}
"""


def generate_auth_pages_tsx(app_name: str) -> str:
    login = f"""import {{ FormEvent, useState }} from "react";
import {{ Link, useNavigate }} from "react-router-dom";
import {{ useAuth }} from "../context/AuthContext";
import {{ Button }} from "../components/ui";

export default function Login() {{
  const {{ login }} = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {{
    e.preventDefault();
    setBusy(true);
    setError("");
    try {{
      await login(email, password);
      navigate("/");
    }} catch (err) {{
      setError(err instanceof Error ? err.message : "Login failed");
    }} finally {{
      setBusy(false);
    }}
  }};

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-950 via-indigo-950 to-slate-900 p-4">
      <form onSubmit={{submit}} className="w-full max-w-md rounded-2xl bg-white p-8 shadow-2xl animate-fade-up">
        <h1 className="text-2xl font-extrabold text-slate-900">{app_name}</h1>
        <p className="mt-1 text-sm text-slate-500">Sign in to continue.</p>
        <label className="mt-5 block text-sm font-semibold text-slate-600">
          Email
          <input type="email" required value={{email}} onChange={{(e) => setEmail(e.target.value)}} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" />
        </label>
        <label className="mt-3 block text-sm font-semibold text-slate-600">
          Password
          <input type="password" required value={{password}} onChange={{(e) => setPassword(e.target.value)}} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" />
        </label>
        {{error && <p className="mt-3 text-sm text-red-600">{{error}}</p>}}
        <Button disabled={{busy}} className="mt-5 w-full py-2.5">{{busy ? "Signing in…" : "Login"}}</Button>
        <p className="mt-4 text-center text-sm text-slate-500">
          No account? <Link to="/register" className="font-semibold text-indigo-600">Register</Link>
        </p>
      </form>
    </div>
  );
}}
"""
    register = f"""import {{ FormEvent, useState }} from "react";
import {{ Link, useNavigate }} from "react-router-dom";
import {{ useAuth }} from "../context/AuthContext";
import {{ Button }} from "../components/ui";

export default function Register() {{
  const {{ register }} = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {{
    e.preventDefault();
    setBusy(true);
    setError("");
    try {{
      await register(name, email, password);
      navigate("/");
    }} catch (err) {{
      setError(err instanceof Error ? err.message : "Registration failed");
    }} finally {{
      setBusy(false);
    }}
  }};

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-950 via-indigo-950 to-slate-900 p-4">
      <form onSubmit={{submit}} className="w-full max-w-md rounded-2xl bg-white p-8 shadow-2xl animate-fade-up">
        <h1 className="text-2xl font-extrabold text-slate-900">Create account</h1>
        <p className="mt-1 text-sm text-slate-500">Join {app_name}.</p>
        <label className="mt-5 block text-sm font-semibold text-slate-600">
          Name
          <input required value={{name}} onChange={{(e) => setName(e.target.value)}} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" />
        </label>
        <label className="mt-3 block text-sm font-semibold text-slate-600">
          Email
          <input type="email" required value={{email}} onChange={{(e) => setEmail(e.target.value)}} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" />
        </label>
        <label className="mt-3 block text-sm font-semibold text-slate-600">
          Password (min 8 characters)
          <input type="password" required minLength={{8}} value={{password}} onChange={{(e) => setPassword(e.target.value)}} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" />
        </label>
        {{error && <p className="mt-3 text-sm text-red-600">{{error}}</p>}}
        <Button disabled={{busy}} className="mt-5 w-full py-2.5">{{busy ? "Creating…" : "Create Account"}}</Button>
        <p className="mt-4 text-center text-sm text-slate-500">
          Have an account? <Link to="/login" className="font-semibold text-indigo-600">Login</Link>
        </p>
      </form>
    </div>
  );
}}
"""
    return login + "\n// ---- split marker ----\n" + register


def generate_profile_tsx() -> str:
    return """import { useAuth } from "../context/AuthContext";
import { Card } from "../components/ui";

export default function Profile() {
  const { user } = useAuth();
  return (
    <div className="animate-fade-up">
      <h1 className="mb-4 text-xl font-bold text-slate-900">Profile</h1>
      <Card className="max-w-md p-6">
        <div className="grid gap-2 text-sm">
          <div className="flex justify-between border-b border-slate-100 py-2"><span className="text-slate-500">Name</span><span className="font-medium">{user?.name}</span></div>
          <div className="flex justify-between border-b border-slate-100 py-2"><span className="text-slate-500">Email</span><span className="font-medium">{user?.email}</span></div>
          <div className="flex justify-between py-2"><span className="text-slate-500">User ID</span><span className="font-medium">#{user?.id}</span></div>
        </div>
      </Card>
    </div>
  );
}
"""


def generate_app_tsx(entities: list[dict]) -> str:
    return """import { Navigate, Route, Routes, useParams } from "react-router-dom";
import Layout from "./components/Layout";
import { useAuth } from "./context/AuthContext";
import { entityByKey } from "./entities";
import EntityPage from "./pages/EntityPage";
import Dashboard from "./pages/Dashboard";
import Profile from "./pages/Profile";
import NotFound from "./pages/NotFound";
import Login from "./pages/Login";
import Register from "./pages/Register";
import { Spinner } from "./components/ui";

function Protected({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <Spinner />;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route
        path="/"
        element={
          <Protected>
            <Layout />
          </Protected>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="e/:key" element={<EntityGate />} />
        <Route path="profile" element={<Profile />} />
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}

function EntityGate() {
  const { key } = useParams<{ key: string }>();
  const entity = entityByKey(key);
  if (!entity) return <NotFound />;
  return <EntityPage entity={entity} />;
}
"""


def generate_not_found_tsx() -> str:
    return """import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50 p-4">
      <p className="text-6xl font-extrabold text-indigo-600">404</p>
      <p className="mt-2 font-semibold text-slate-700">Page not found</p>
      <Link to="/" className="mt-4 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700">
        Back to Dashboard
      </Link>
    </div>
  );
}
"""


def generate_frontend_files(
    entities: list[dict], app_name: str, tagline: str = "", theme: dict | None = None
) -> dict[str, str]:
    """Generate the complete React 18 + Vite + TypeScript + Tailwind application."""
    entities = normalize_entities(entities)
    configs = _entity_configs(entities)
    auth_pages = generate_auth_pages_tsx(app_name)
    login_src, register_src = auth_pages.split("\n// ---- split marker ----\n")
    return {
        "frontend/package.json": generate_package_json(entities, app_name),
        "frontend/vite.config.ts": generate_vite_config(),
        "frontend/tsconfig.json": generate_tsconfig(),
        "frontend/tailwind.config.js": generate_tailwind_config(),
        "frontend/postcss.config.js": generate_postcss_config(),
        "frontend/index.html": generate_index_html(app_name),
        "frontend/src/main.tsx": generate_main_tsx(),
        "frontend/src/index.css": generate_index_css(theme),
        "frontend/src/config.ts": generate_config_ts(),
        "frontend/src/entities.ts": generate_types_ts(entities),
        "frontend/src/api/client.ts": generate_api_client_ts(),
        "frontend/src/context/AuthContext.tsx": generate_auth_context_tsx(),
        "frontend/src/components/ui.tsx": generate_ui_tsx(),
        "frontend/src/components/Layout.tsx": generate_layout_tsx(configs, app_name),
        "frontend/src/pages/Dashboard.tsx": generate_dashboard_tsx(configs, app_name, tagline),
        "frontend/src/pages/EntityPage.tsx": generate_entity_page_tsx(),
        "frontend/src/pages/Login.tsx": login_src,
        "frontend/src/pages/Register.tsx": register_src,
        "frontend/src/pages/Profile.tsx": generate_profile_tsx(),
        "frontend/src/pages/NotFound.tsx": generate_not_found_tsx(),
        "frontend/src/App.tsx": generate_app_tsx(configs),
    }
