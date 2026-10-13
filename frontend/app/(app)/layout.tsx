"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/shell";
import { useAuth } from "@/lib/auth";
import { Spinner } from "@/components/common";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { initialized, token, init } = useAuth();

  useEffect(() => {
    void init();
  }, [init]);

  useEffect(() => {
    if (initialized && !token) router.replace("/login");
  }, [initialized, token, router]);

  if (!initialized || !token) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar />
      <main className="min-w-0 flex-1 p-4 sm:p-6 lg:p-8">{children}</main>
    </div>
  );
}
