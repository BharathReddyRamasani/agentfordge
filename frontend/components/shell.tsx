"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Download,
  FilePlus2,
  FolderKanban,
  Hexagon,
  LayoutDashboard,
  LayoutTemplate,
  LogOut,
  Settings,
  HelpCircle,
  Menu,
  X,
} from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/projects", label: "Projects", icon: FolderKanban },
  { href: "/projects/new", label: "Create Project", icon: FilePlus2 },
  { href: "/templates", label: "Templates", icon: LayoutTemplate },
  { href: "/downloads", label: "My Downloads", icon: Download },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const initials = (user?.name ?? "U").split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase();

  const nav = (
    <div className="flex h-full flex-col bg-slate-950 text-slate-200">
      <div className="flex items-center gap-2 px-5 pb-5 pt-6">
        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-indigo-700">
          <Hexagon className="h-5 w-5 text-white" />
        </span>
        <span className="text-lg font-bold text-white">AgentForge</span>
      </div>
      <nav className="flex-1 space-y-1 px-3">
        {NAV.map((item) => {
          const active = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setOpen(false)}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium",
                active ? "bg-indigo-600 text-white" : "text-slate-300 hover:bg-slate-800 hover:text-white"
              )}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="space-y-1 px-3 pb-2">
        <Link href="/settings" className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-slate-300 hover:bg-slate-800 hover:text-white">
          <Settings className="h-4 w-4" /> Settings
        </Link>
        <span className="flex cursor-default items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-slate-400">
          <HelpCircle className="h-4 w-4" /> Help & Support
        </span>
      </div>
      <div className="border-t border-slate-800 p-4">
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-indigo-600 text-xs font-bold text-white">{initials}</span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-white">{user?.name}</p>
            <p className="truncate text-xs text-slate-400">{user?.email}</p>
          </div>
          <button
            title="Logout"
            onClick={() => void logout().then(() => router.replace("/login"))}
            className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-white"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <>
      <button onClick={() => setOpen(!open)} className="fixed left-3 top-3 z-40 rounded-lg bg-slate-950 p-2 text-white lg:hidden">
        {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
      </button>
      <aside className="hidden w-64 shrink-0 lg:block">{nav}</aside>
      {open && (
        <div className="fixed inset-0 z-30 lg:hidden" onClick={() => setOpen(false)}>
          <aside className="h-full w-64" onClick={(e) => e.stopPropagation()}>{nav}</aside>
        </div>
      )}
    </>
  );
}

export function Topbar({ title, subtitle }: { title: string; subtitle?: string }) {
  const { user } = useAuth();
  return (
    <div className="mb-6 flex items-center justify-between gap-4 pl-12 lg:pl-0">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>}
      </div>
      <div className="flex items-center gap-3">
        <div className="hidden rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-400 md:block">Search projects…</div>
        <span className="flex h-9 w-9 items-center justify-center rounded-full bg-indigo-100 text-xs font-bold text-indigo-700">
          {(user?.name ?? "U")[0].toUpperCase()}
        </span>
      </div>
    </div>
  );
}
