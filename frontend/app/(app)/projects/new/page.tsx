"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Stepper } from "@/components/ui";
import { getToken } from "@/lib/auth";
import { ApiError, api } from "@/lib/api";
import { Spinner } from "@/components/common";

const EXAMPLES: Record<string, string> = {
  "Hospital Management": "Build a Hospital Management System where patients can register, doctors can manage appointments, administrators can manage users, and users can view medical records.",
  "Food Delivery": "Build a food delivery platform where customers can browse restaurants, search for food, add items to cart, place orders, track deliveries and manage their profiles.",
  "E-Commerce": "Build an e-commerce website where customers can browse products, manage a cart, place orders, track shipments and admins manage inventory.",
  "Student Portal": "Build a student portal where students can register, enroll in courses, submit assignments, view grades and teachers manage classes.",
};

function NewProjectForm() {
  const router = useRouter();
  const search = useSearchParams();
  const preset = search.get("template");
  const [name, setName] = useState(preset ?? "Hospital Management System");
  const [description, setDescription] = useState(EXAMPLES[preset ?? ""] ?? EXAMPLES["Hospital Management"]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    const token = getToken();
    if (!token || !name.trim() || description.trim().length < 10) {
      setError("Give your project a name and a requirement of at least 10 characters.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const project = await api.createProject(token, name.trim(), description.trim());
      await api.submitRequirement(token, project.id, description.trim());
      await api.analyze(token, project.id);
      router.replace(`/projects/${project.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to create project");
      setBusy(false);
    }
  };

  return (
    <div>
      <Stepper status="CREATED" />
      <div className="mx-auto mt-6 max-w-3xl rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h1 className="text-xl font-bold text-slate-900">Describe Your Application</h1>
        <p className="mt-1 text-sm text-slate-500">Enter your requirements in natural language. Be as detailed as possible.</p>
        <label className="mt-4 block text-sm font-semibold text-slate-600">
          Project name
          <input value={name} onChange={(e) => setName(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" />
        </label>
        <label className="mt-3 block text-sm font-semibold text-slate-600">
          Requirement
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={6} className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2" />
        </label>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
          <span className="text-slate-500">Or try an example:</span>
          {Object.keys(EXAMPLES).map((k) => (
            <button key={k} onClick={() => { setName(`${k} ${k === "E-Commerce" ? "Website" : k === "Student Portal" ? "" : "System"}`.trim()); setDescription(EXAMPLES[k]); }} className="rounded-full border border-slate-300 px-3 py-1 text-xs font-medium text-slate-600 hover:border-indigo-500 hover:text-indigo-600">
              {k}
            </button>
          ))}
        </div>
        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
        <div className="mt-5 flex justify-end">
          <button onClick={() => void submit()} disabled={busy} className="flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2.5 font-medium text-white hover:bg-indigo-700 disabled:opacity-60">
            {busy && <Spinner className="text-white" />} Analyze Requirement →
          </button>
        </div>
        <p className="mt-3 text-xs text-slate-400">AgentForge will analyze your requirement and create a plan.</p>
      </div>
    </div>
  );
}

export default function NewProjectPage() {
  return (
    <Suspense>
      <NewProjectForm />
    </Suspense>
  );
}
