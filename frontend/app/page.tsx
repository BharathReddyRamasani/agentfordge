import Link from "next/link";
import { ArrowRight, CheckCircle2, Hexagon, PlayCircle } from "lucide-react";

const NODES = ["Analyze", "Plan", "Prototype", "Test", "Deploy", "Review"];

const STEPS = [
  { n: "01", t: "Analyze", d: "AI extracts purpose, users, roles, features and flows from your requirement." },
  { n: "02", t: "Plan", d: "A development plan scopes the prototype and the full application." },
  { n: "03", t: "Prototype", d: "A lightweight interactive prototype demonstrates the core concept." },
  { n: "04", t: "Review & Approve", d: "You review, request changes, and approve only when it is right." },
  { n: "05", t: "Autonomous Build", d: "14 specialized agents engineer, test and package the full application." },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
        <span className="flex items-center gap-2 font-bold">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-indigo-700">
            <Hexagon className="h-4 w-4 text-white" />
          </span>
          AgentForge
        </span>
        <nav className="hidden items-center gap-6 text-sm text-slate-300 md:flex">
          <span>Features</span>
          <span>How It Works</span>
          <span>Use Cases</span>
          <span>Docs</span>
        </nav>
        <div className="flex gap-2">
          <Link href="/login" className="rounded-lg border border-slate-700 px-4 py-2 text-sm font-medium hover:bg-slate-800">
            Login
          </Link>
          <Link href="/register" className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium hover:bg-indigo-700">
            Get Started
          </Link>
        </div>
      </header>

      <main className="mx-auto grid max-w-6xl items-center gap-10 px-6 pb-16 pt-10 lg:grid-cols-2">
        <div>
          <h1 className="text-4xl font-extrabold leading-tight sm:text-5xl">
            Turn Your Requirements into Real Applications with{" "}
            <span className="bg-gradient-to-r from-indigo-400 to-sky-400 bg-clip-text text-transparent">Autonomous AI Agents</span>
          </h1>
          <p className="mt-4 max-w-lg text-slate-300">
            AgentForge analyzes your requirements, builds a prototype for your review, and then delivers a complete
            application through a multi-agent autonomous engineering workflow.
          </p>
          <div className="mt-6 flex gap-3">
            <Link href="/register" className="flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2.5 font-medium hover:bg-indigo-700">
              Get Started <ArrowRight className="h-4 w-4" />
            </Link>
            <Link href="/templates" className="flex items-center gap-2 rounded-lg border border-slate-700 px-5 py-2.5 font-medium hover:bg-slate-800">
              <PlayCircle className="h-4 w-4" /> View Templates
            </Link>
          </div>
          <div className="mt-10 grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
            {[
              ["14", "Specialized Agents"],
              ["Prototype-First", "Validation"],
              ["End-to-End", "App Generation"],
              ["Open & Extensible", "Architecture"],
            ].map(([big, small]) => (
              <div key={small}>
                <p className="font-bold text-white">{big}</p>
                <p className="text-slate-400">{small}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="relative mx-auto flex h-80 w-80 items-center justify-center">
          <div className="absolute h-64 w-64 rounded-full border border-slate-700" />
          <div className="absolute h-44 w-44 rounded-full border border-slate-800" />
          <div className="z-10 flex h-24 w-24 flex-col items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-indigo-800 shadow-2xl">
            <Hexagon className="h-6 w-6" />
            <span className="mt-1 text-xs font-bold">AgentForge</span>
          </div>
          {NODES.map((n, i) => (
            <div key={n} className="absolute" style={{ transform: `rotate(${i * 60}deg) translateX(128px)` }}>
              <div style={{ transform: `rotate(-${i * 60}deg)` }} className="rounded-full border border-indigo-500/50 bg-slate-900 px-3 py-1 text-xs font-medium text-indigo-200">
                {n}
              </div>
            </div>
          ))}
        </div>
      </main>

      <section className="border-t border-slate-800 bg-slate-900/50">
        <div className="mx-auto max-w-6xl px-6 py-14">
          <h2 className="text-2xl font-bold">How it works</h2>
          <p className="mt-1 text-slate-400">Validate the idea first — then build autonomously.</p>
          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {STEPS.map((s) => (
              <div key={s.n} className="rounded-xl border border-slate-800 bg-slate-900 p-4">
                <p className="text-xs font-bold text-indigo-400">{s.n}</p>
                <p className="mt-1 font-semibold">{s.t}</p>
                <p className="mt-1 text-sm text-slate-400">{s.d}</p>
              </div>
            ))}
          </div>
          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <div className="rounded-xl border border-indigo-500/40 bg-indigo-950/40 p-5">
              <p className="font-semibold text-indigo-200">Prototype Validation Loop</p>
              <p className="mt-1 text-sm text-slate-300">Plan → Prototype → Review → Feedback → Revise → Rebuild… until YOU approve.</p>
            </div>
            <div className="rounded-xl border border-emerald-500/40 bg-emerald-950/40 p-5">
              <p className="font-semibold text-emerald-200">Engineering Quality Loop</p>
              <p className="mt-1 text-sm text-slate-300">Develop → Test → Debug → Re-test… until the application passes validation.</p>
            </div>
          </div>
          <div className="mt-8 flex items-center gap-2 text-sm text-slate-300">
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
            No code editor, no IDE — AgentForge delivers validated, tested, downloadable applications.
          </div>
        </div>
      </section>

      <footer className="border-t border-slate-800 py-6 text-center text-sm text-slate-500">
        AgentForge — autonomous multi-agent software engineering platform
      </footer>
    </div>
  );
}
