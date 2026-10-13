"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Hexagon } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import { Spinner } from "@/components/common";

export default function RegisterPage() {
  const router = useRouter();
  const register = useAuth((s) => s.register);
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await register(email, name, password);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Registration failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 p-4">
      <form onSubmit={submit} className="w-full max-w-md rounded-2xl bg-white p-8 shadow-2xl">
        <div className="mb-6 flex items-center gap-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-indigo-700">
            <Hexagon className="h-5 w-5 text-white" />
          </span>
          <span className="text-lg font-bold text-slate-900">AgentForge</span>
        </div>
        <h1 className="text-2xl font-bold text-slate-900">Create your account</h1>
        <p className="mt-1 text-sm text-slate-500">Start turning requirements into applications.</p>
        <label className="mt-5 block text-sm font-semibold text-slate-600">
          Name
          <input required value={name} onChange={(e) => setName(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900" />
        </label>
        <label className="mt-3 block text-sm font-semibold text-slate-600">
          Email
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900" />
        </label>
        <label className="mt-3 block text-sm font-semibold text-slate-600">
          Password (min 8 characters)
          <input type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900" />
        </label>
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
        <button disabled={busy} className="mt-5 flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-600 py-2.5 font-medium text-white hover:bg-indigo-700 disabled:opacity-60">
          {busy && <Spinner className="text-white" />} Create Account
        </button>
        <p className="mt-4 text-center text-sm text-slate-500">
          Have an account? <Link href="/login" className="font-semibold text-indigo-600">Login</Link>
        </p>
      </form>
    </div>
  );
}
