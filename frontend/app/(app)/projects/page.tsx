"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Search, Trash2 } from "lucide-react";
import { Topbar } from "@/components/shell";
import { getToken } from "@/lib/auth";
import { api } from "@/lib/api";
import { ProgressBar, StatusBadge } from "@/components/ui";
import { EmptyState, Spinner } from "@/components/common";
import type { Project } from "@/types";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);

  const load = () => {
    const token = getToken();
    if (!token) return;
    setLoading(true);
    api.listProjects(token).then((r) => setProjects(r.items)).catch(() => {}).finally(() => setLoading(false));
  };

  useEffect(load, []);

  const remove = async (id: number) => {
    if (!confirm("Delete this project and all its artifacts?")) return;
    const token = getToken();
    if (!token) return;
    await api.deleteProject(token, id).catch(() => {});
    load();
  };

  const filtered = projects.filter((p) => {
    if (query && !p.name.toLowerCase().includes(query.toLowerCase())) return false;
    if (filter === "active") return !["COMPLETED", "FAILED", "CANCELLED"].includes(p.status);
    if (filter === "completed") return p.status === "COMPLETED";
    return true;
  });

  return (
    <div>
      <Topbar title="Projects" subtitle="All your AI-generated application projects." />
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search projects…" className="w-full rounded-lg border border-slate-200 bg-white py-2 pl-9 pr-3 text-sm" />
        </div>
        {(["all", "active", "completed"] as const).map((f) => (
          <button key={f} onClick={() => setFilter(f)} className={`rounded-lg px-3 py-2 text-sm font-medium ${filter === f ? "bg-indigo-600 text-white" : "bg-white text-slate-600 border border-slate-200"}`}>
            {f[0].toUpperCase() + f.slice(1)}
          </button>
        ))}
        <Link href="/projects/new" className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700">
          Create Project
        </Link>
      </div>
      {loading ? (
        <Spinner />
      ) : filtered.length === 0 ? (
        <EmptyState title="No projects found" hint="Create a project to get started." />
      ) : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((p) => (
            <div key={p.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-start justify-between gap-2">
                <Link href={`/projects/${p.id}`} className="font-bold text-slate-900 hover:text-indigo-600">{p.name}</Link>
                <button onClick={() => void remove(p.id)} title="Delete" className="rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600">
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
              <div className="mt-2 flex items-center gap-2">
                <StatusBadge status={p.status} />
                <span className="text-xs text-slate-400">{p.current_stage || "new"}</span>
              </div>
              <div className="mt-3 flex items-center gap-2">
                <ProgressBar value={p.progress} className="flex-1" />
                <span className="text-xs text-slate-500">{p.progress}%</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
