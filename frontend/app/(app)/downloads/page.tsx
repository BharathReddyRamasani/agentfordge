"use client";

import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { Topbar } from "@/components/shell";
import { getToken } from "@/lib/auth";
import { api } from "@/lib/api";
import { EmptyState, Spinner } from "@/components/common";
import type { DownloadPackage, Project } from "@/types";

export default function DownloadsPage() {
  const [rows, setRows] = useState<{ project: Project; pkgs: DownloadPackage[] }[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getToken();
    if (!token) return;
    (async () => {
      try {
        const list = await api.listProjects(token);
        const done = list.items.filter((p) => p.status === "COMPLETED");
        const out = [];
        for (const p of done) {
          try {
            const pkgs = await api.getDownloads(token, p.id);
            out.push({ project: p, pkgs });
          } catch {
            /* skip */
          }
        }
        setRows(out);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const token = typeof window !== "undefined" ? getToken() : null;

  return (
    <div>
      <Topbar title="My Downloads" subtitle="Packages from your completed projects." />
      {loading ? (
        <Spinner />
      ) : rows.length === 0 ? (
        <EmptyState title="No downloads yet" hint="Complete a project to download its packages." />
      ) : (
        <div className="space-y-4">
          {rows.map(({ project, pkgs }) => (
            <div key={project.id} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="font-bold text-slate-900">{project.name}</p>
              <div className="mt-3 divide-y divide-slate-100">
                {pkgs.map((d) => (
                  <div key={d.kind} className="flex items-center justify-between gap-3 py-2">
                    <div>
                      <p className="text-sm font-medium capitalize text-slate-800">{d.kind}</p>
                      <p className="text-xs text-slate-400">{d.filename} · {(d.size / 1024).toFixed(1)} KB</p>
                    </div>
                    <a
                      href={token ? api.downloadUrl(project.id, d.kind, token) : "#"}
                      className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700"
                    >
                      <Download className="h-3.5 w-3.5" /> ZIP
                    </a>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
