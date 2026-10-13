"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { CheckCircle2, Clock, FolderKanban, Layers } from "lucide-react";
import { Topbar } from "@/components/shell";
import { useAuth, getToken } from "@/lib/auth";
import { api } from "@/lib/api";
import { ProgressBar, StatusBadge } from "@/components/ui";
import { Spinner } from "@/components/common";
import type { Project } from "@/types";

export default function DashboardPage() {
  const user = useAuth((s) => s.user);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getToken();
    if (!token) return;
    api.listProjects(token).then((r) => setProjects(r.items)).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const inProgress = projects.filter((p) => !["COMPLETED", "FAILED", "CANCELLED"].includes(p.status)).length;
  const completed = projects.filter((p) => p.status === "COMPLETED").length;

  const stats = [
    { label: "Total Projects", value: projects.length, icon: FolderKanban, tint: "bg-indigo-100 text-indigo-600" },
    { label: "In Progress", value: inProgress, icon: Clock, tint: "bg-amber-100 text-amber-600" },
    { label: "Completed", value: completed, icon: CheckCircle2, tint: "bg-emerald-100 text-emerald-600" },
    { label: "Prototypes", value: projects.filter((p) => p.progress >= 45).length, icon: Layers, tint: "bg-sky-100 text-sky-600" },
  ];

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Welcome back, {user?.name?.split(" ")[0] ?? "there"}!</h1>
          <p className="mt-0.5 text-sm text-slate-500">Create, manage and track your AI-powered application projects.</p>
        </div>
        <Link href="/projects/new" className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700">
          Create New Project
        </Link>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {stats.map((s) => (
          <div key={s.label} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <span className={`inline-flex h-9 w-9 items-center justify-center rounded-lg ${s.tint}`}>
              <s.icon className="h-5 w-5" />
            </span>
            <p className="mt-2 text-2xl font-bold text-slate-900">{loading ? "–" : s.value}</p>
            <p className="text-sm text-slate-500">{s.label}</p>
          </div>
        ))}
      </div>

      <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-bold text-slate-900">Recent Projects</h2>
          <Link href="/projects" className="text-sm font-medium text-indigo-600">View All</Link>
        </div>
        {loading ? (
          <Spinner />
        ) : projects.length === 0 ? (
          <p className="py-6 text-center text-sm text-slate-500">
            No projects yet. <Link href="/projects/new" className="font-semibold text-indigo-600">Create your first project</Link>
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-xs uppercase text-slate-400">
                  <th className="py-2 pr-4">Project Name</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2 pr-4">Stage</th>
                  <th className="py-2 pr-4">Progress</th>
                  <th className="py-2">Updated</th>
                </tr>
              </thead>
              <tbody>
                {projects.slice(0, 6).map((p) => (
                  <tr key={p.id} className="border-b border-slate-50 last:border-0">
                    <td className="py-2.5 pr-4 font-medium text-slate-800">
                      <Link href={`/projects/${p.id}`} className="hover:text-indigo-600">{p.name}</Link>
                    </td>
                    <td className="py-2.5 pr-4"><StatusBadge status={p.status} /></td>
                    <td className="py-2.5 pr-4 text-slate-500">{p.current_stage || "—"}</td>
                    <td className="py-2.5 pr-4"><div className="flex items-center gap-2"><ProgressBar value={p.progress} className="w-24" /><span className="text-xs text-slate-500">{p.progress}%</span></div></td>
                    <td className="py-2.5 text-slate-500">{new Date(p.updated_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
