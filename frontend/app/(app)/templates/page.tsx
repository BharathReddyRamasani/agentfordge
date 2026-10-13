"use client";

import Link from "next/link";
import { Topbar } from "@/components/shell";
import { LayoutTemplate } from "lucide-react";

const TEMPLATES = [
  { name: "Hospital Management", desc: "Patients, doctors, appointments, medical records and admin user management.", req: "Build a Hospital Management System where patients can register, doctors can manage appointments, administrators can manage users, and users can view medical records." },
  { name: "Food Delivery", desc: "Restaurants, menus, cart, checkout and live order tracking.", req: "Build a food delivery platform where customers can browse restaurants, search for food, add items to cart, place orders and track deliveries." },
  { name: "E-Commerce", desc: "Catalog, cart, checkout, order history and admin product management.", req: "Build an e-commerce website where customers can browse products, manage a cart, place orders and admins manage inventory." },
  { name: "Student Portal", desc: "Courses, enrollment, assignments, grades and teacher dashboards.", req: "Build a student portal where students can register, enroll in courses, submit assignments, view grades and teachers manage classes." },
  { name: "Learning Management", desc: "Course catalog, lessons, quizzes and progress tracking.", req: "Build a learning management system where students enroll in courses, complete lessons, take quizzes and track progress." },
];

export default function TemplatesPage() {
  return (
    <div>
      <Topbar title="Templates" subtitle="Start from a proven requirement sketch." />
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {TEMPLATES.map((t) => (
          <div key={t.name} className="flex flex-col rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-100 text-indigo-600">
              <LayoutTemplate className="h-5 w-5" />
            </span>
            <p className="mt-3 font-bold text-slate-900">{t.name}</p>
            <p className="mt-1 flex-1 text-sm text-slate-500">{t.desc}</p>
            <Link href={`/projects/new?template=${encodeURIComponent(t.name)}`} className="mt-4 rounded-lg bg-indigo-600 px-4 py-2 text-center text-sm font-medium text-white hover:bg-indigo-700">
              Use This Template
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
}
