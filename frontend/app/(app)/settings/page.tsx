"use client";

import { useRouter } from "next/navigation";
import { Topbar } from "@/components/shell";
import { useAuth } from "@/lib/auth";
import { SectionCard } from "@/components/common";

export default function SettingsPage() {
  const router = useRouter();
  const { user, logout } = useAuth();

  return (
    <div>
      <Topbar title="Settings" subtitle="Your account and workspace preferences." />
      <div className="max-w-2xl space-y-4">
        <SectionCard title="Profile">
          <div className="grid gap-2 text-sm">
            <div className="flex justify-between border-b border-slate-100 py-2"><span className="text-slate-500">Name</span><span className="font-medium">{user?.name}</span></div>
            <div className="flex justify-between py-2"><span className="text-slate-500">Email</span><span className="font-medium">{user?.email}</span></div>
          </div>
        </SectionCard>
        <SectionCard title="Session">
          <p className="mb-3 text-sm text-slate-500">Sign out everywhere on this device. Tokens expire automatically after 7 days.</p>
          <button
            onClick={() => void logout().then(() => router.replace("/login"))}
            className="rounded-lg border border-red-300 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50"
          >
            Logout
          </button>
        </SectionCard>
        <SectionCard title="Backend">
          <p className="text-sm text-slate-500">API endpoint: <span className="font-mono">{process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}</span></p>
          <p className="mt-1 text-sm text-slate-500">Interactive API docs: <span className="font-mono">/docs</span> on the backend.</p>
        </SectionCard>
      </div>
    </div>
  );
}
