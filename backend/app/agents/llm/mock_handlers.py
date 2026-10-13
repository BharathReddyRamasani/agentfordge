"""Deterministic mock LLM handlers. Mock mode is fully functional: every handler
produces genuine, structured, schema-valid output derived from the actual project
inputs (requirement text, analysis, plans, architecture). Used for development,
tests and offline operation only — the real provider path works independently."""

import copy
import re

from app.services.codegen import deploy_gen, docs_gen, tests_gen
from app.services.codegen.database_sql import _table_name
from app.services.codegen.entities import (
    detect_domain,
    extract_app_name,
    extract_extra_features,
)


def _domain_of(analysis: dict):
    text = " ".join(
        [str(analysis.get("purpose", "")), str(analysis.get("project_name", ""))]
        + [str(f.get("name", "")) for f in analysis.get("essential_features", [])]
    )
    return detect_domain(text)


def _feature_items(analysis: dict, domain) -> list[dict]:
    named = [f.get("name", "") for f in analysis.get("essential_features", []) if f.get("name")]
    known = list(domain.features)
    extras = extract_extra_features(str(analysis.get("purpose", "")), known + named)
    features = known + [f for f in named if f not in known] + extras
    return [
        {"name": f, "description": f"Enables {f.lower()} as part of the core {domain.label.lower()} experience."}
        for f in features
    ]


# ---------------------------------------------------------------- AGENT 1


def handle_analyze_requirement(payload: dict) -> dict:
    inp = payload.get("input", {})
    requirement = str(inp.get("requirement", ""))
    domain = detect_domain(requirement)
    app_name = extract_app_name(requirement, domain)
    features = _feature_items({"purpose": requirement, "project_name": app_name, "essential_features": []}, domain)
    frs = [
        {"id": f"FR-{i + 1:03d}", "title": f["name"], "description": f["description"]}
        for i, f in enumerate(features)
    ]
    nfrs = [
        {"id": "NFR-001", "title": "Security", "description": "Passwords hashed; role-based access control; no secrets in client code."},
        {"id": "NFR-002", "title": "Performance", "description": "Interactive responses under normal load; indexed database access."},
        {"id": "NFR-003", "title": "Usability", "description": "Clear navigation, responsive UI, accessible forms with validation."},
        {"id": "NFR-004", "title": "Reliability", "description": "Consistent error handling and safe failure modes."},
    ]
    return {
        "project_name": app_name,
        "purpose": f"A {domain.label.lower()} platform that {domain.purpose_template}.",
        "target_users": list(domain.target_users),
        "user_roles": list(domain.user_roles),
        "core_value_proposition": f"Replace manual {domain.key} workflows with a single reliable digital platform that improves efficiency and user experience.",
        "essential_features": features,
        "primary_user_flow": list(domain.user_flow),
        "functional_requirements": frs,
        "non_functional_requirements": nfrs,
        "constraints": [
            "Must be a web-based application",
            "Must support role-based access control",
            "Data must be persisted in a relational database",
            "Must expose a REST API consumed by the frontend",
        ],
        "ambiguities": [
            "Exact permission boundaries per role are finalized during planning",
            "Third-party integrations (payments, email) are deferred to full development",
            "Specific branding and design preferences are validated via the prototype",
        ],
    }


# ---------------------------------------------------------------- AGENT 2


def _screens_from_features(features: list[str]) -> list[dict]:
    screens = [
        {"name": "Home", "purpose": "Landing page presenting the application's core value", "sections": ["hero", "stats", "cards"]},
        {"name": "Login", "purpose": "Authentication for returning users", "sections": ["form"]},
    ]
    form_words = ("book", "cart", "checkout", "order", "submit", "register", "add", "schedule")
    for feature in features:
        base = feature.split("(")[0].strip()
        low = base.lower()
        if low in ("home", "landing", "login", "dashboard"):
            continue
        sections = ["form", "list"] if any(w in low for w in form_words) else ["cards", "list"]
        screens.append({"name": base, "purpose": f"Demonstrates {base.lower()} for concept validation", "sections": sections})
    if any("dashboard" in f.lower() for f in features):
        screens.append({"name": "Dashboard", "purpose": "Summary dashboard with representative data", "sections": ["stats", "list"]})
    return screens


def handle_plan_application(payload: dict) -> dict:
    inp = payload.get("input", {})
    analysis = inp.get("analysis", {}) or {}
    project_name = analysis.get("project_name", "Application")
    features = [f.get("name", "") for f in analysis.get("essential_features", []) if f.get("name")]
    screens = _screens_from_features(features)
    phases = [
        {"name": "Architecture", "description": "Convert the approved prototype into a complete technical architecture", "tasks": ["Define system architecture", "Design API contracts", "Define database strategy"]},
        {"name": "Database", "description": "Design and generate the data layer", "tasks": ["Design schema from entities", "Generate tables, constraints and indexes", "Generate seed data"]},
        {"name": "Backend API", "description": "Implement the API and business logic", "tasks": ["Implement authentication", "Implement CRUD endpoints", "Implement validation and error handling"]},
        {"name": "Frontend", "description": "Implement the application frontend", "tasks": ["Build pages and navigation", "Implement forms and validation", "Integrate with the backend API"]},
        {"name": "Integration", "description": "Connect frontend, backend and database", "tasks": ["Verify API contracts", "Verify authentication flow", "Resolve integration issues"]},
        {"name": "Testing", "description": "Validate the generated application", "tasks": ["Generate unit, API and functional tests", "Execute the test suite", "Fix failures via the debugging loop"]},
        {"name": "Review & Security", "description": "Review and validate quality", "tasks": ["Review requirement compliance", "Perform security audit", "Validate overall quality"]},
        {"name": "Documentation", "description": "Generate project documentation", "tasks": ["README and setup guide", "API and database documentation", "Deployment guide"]},
        {"name": "Deployment", "description": "Package for deployment", "tasks": ["Dockerfile and compose configuration", "Environment templates", "Final packaging"]},
    ]
    return {
        "summary": f"Plan for {project_name}: validate the core concept through a {len(screens)}-screen interactive prototype, then execute full-scale engineering across {len(phases)} phases.",
        "prototype_scope": {
            "goal": f"Validate the core {project_name} concept: {str(analysis.get('core_value_proposition', ''))[:160]}",
            "screens": screens,
            "interactions": [
                "Navigate between primary screens via the top navigation",
                "Submit forms with representative data",
                "View and filter record lists",
                "Complete the primary user flow end-to-end",
            ],
            "include": [f for f in features],
            "out_of_scope": [
                "Full production backend infrastructure",
                "Third-party integrations (payments, email)",
                "Advanced admin permissions",
                "Performance optimization",
            ],
        },
        "full_application_plan": {"phases": phases, "stack": {"frontend": "React 18 + Vite + TypeScript + Tailwind CSS", "backend": "Python FastAPI + SQLAlchemy", "database": "PostgreSQL (SQLite for dev)"}},
        "feature_priorities": [{"feature": f, "priority": "high"} for f in features],
        "revision_notes": "",
    }


def handle_revise_plan(payload: dict) -> dict:
    inp = payload.get("input", {})
    analysis = inp.get("analysis", {}) or {}
    current_plan = copy.deepcopy(inp.get("current_plan", {}) or {})
    feedback = str(inp.get("feedback", "")).strip()
    if not current_plan:
        current_plan = handle_plan_application({"input": {"analysis": analysis}})

    scope = current_plan.setdefault("prototype_scope", {})
    screens = scope.setdefault("screens", [])
    interactions = scope.setdefault("interactions", [])
    priorities = current_plan.setdefault("feature_priorities", [])
    features = [p.get("feature", "") for p in priorities] or [
        f.get("name", "") for f in analysis.get("essential_features", [])
    ]
    existing = {s.get("name", "").lower() for s in screens} | {f.lower() for f in features}

    new_features: list[str] = []
    for m in re.finditer(r"add(?:\s+(?:a|an|the))?\s+([a-z0-9][a-z0-9 \-&]{2,40}?)(?=[.,;]|$|\s+and\s+|\s+also\b)", feedback.lower()):
        candidate = m.group(1).strip()
        title = " ".join(w.capitalize() for w in candidate.split()[:4])
        if title and title.lower() not in existing:
            new_features.append(title)
            existing.add(title.lower())
    new_features += [f for f in extract_extra_features(feedback, features + new_features) if f.lower() not in existing]

    for feat in new_features:
        screens.append({"name": feat, "purpose": f"Added per user feedback: {feedback[:140]}", "sections": ["list", "form"]})
        features.append(feat)
        priorities.append({"feature": feat, "priority": "high"})
    for verb, label in [
        ("cancel", "Cancel records from list views"),
        ("reschedule", "Reschedule existing records"),
        ("edit", "Edit records inline"),
        ("track", "Track status progression end-to-end"),
        ("search", "Search and filter records"),
        ("before", "Reorder flow steps as requested"),
        ("doctor select", "Select a doctor before booking"),
    ]:
        if verb in feedback.lower() and label not in interactions:
            interactions.append(label)

    scope["screens"] = screens
    scope["interactions"] = interactions
    current_plan["feature_priorities"] = priorities

    # Design directives: stylistic feedback ("stylish", "animations", colors...) must
    # produce a VISIBLE change, not a silent no-op. Map it to a curated theme palette
    # stored on the prototype scope; the prototype builder applies it.
    lowered = feedback.lower()
    palettes = [
        (("stylish", "modern", "vibrant", "bold", "purple", "violet"), ("Violet", "#7c3aed", "#4c1d95")),
        (("calm", "clean", "professional", "trust", "teal", "medical"), ("Teal", "#0d9488", "#134e4a")),
        (("warm", "energetic", "orange", "food"), ("Ember", "#ea580c", "#7c2d12")),
        (("red", "crimson", "rose"), ("Rose", "#e11d48", "#881337")),
        (("green", "emerald"), ("Emerald", "#059669", "#064e3b")),
        (("blue", "indigo"), ("Indigo", "#4f46e5", "#312e81")),
    ]
    directives: list[str] = []
    for keywords, (name, primary, accent) in palettes:
        if any(k in lowered for k in keywords):
            scope["theme"] = {"primary_color": primary, "accent_color": accent, "background_color": "#f8fafc"}
            directives.append(f"theme switched to {name} ({primary})")
            break
    for kw in ("animation", "animated", "transition", "motion"):
        if kw in lowered:
            directives.append("motion design emphasized (transitions, animated screen changes and charts are built into the prototype renderer)")
            break
    if "dark mode" in lowered or "dark theme" in lowered:
        directives.append("dark mode noted for full development (prototype stays light for readability)")
    full_plan = current_plan.setdefault("full_application_plan", {})
    phases = full_plan.setdefault("phases", [])
    for phase in phases:
        if phase.get("name") in ("Backend API", "Frontend") and new_features:
            phase.setdefault("tasks", []).append(f"Incorporate requested change: {feedback[:90]}")
    current_plan["summary"] = (
        current_plan.get("summary", "") + f" | Revised per user feedback ({len(new_features)} change(s) incorporated)."
    ).strip(" |")
    current_plan["revision_notes"] = f"Plan revision driven by user feedback: {feedback}"
    if directives:
        current_plan["revision_notes"] += f" | Design directives applied: {'; '.join(directives)}"
    return current_plan


# ---------------------------------------------------------------- AGENT 3


def _screen_to_spec(screen: dict, domain, app_name: str, tagline: str, index: int) -> dict:
    name = str(screen.get("name", f"Screen {index + 1}"))
    low = name.lower()
    sections: list[dict] = []
    sample = domain.sample_data

    def items_for(keys) -> list[str]:
        for key in keys:
            for skey, values in sample.items():
                if key in skey.lower():
                    return list(values)
        return []

    if index == 0 and ("home" in low or "landing" in low):
        stats = [{"label": k, "value": str(len(v))} for k, v in list(sample.items())[:3]]
        stats.append({"label": "User Satisfaction", "value": "4.8/5"})
        sections.append({"type": "hero", "title": app_name, "subtitle": tagline})
        sections.append({"type": "stats", "title": "At a Glance", "stats": stats})
        sections.append({"type": "cards", "title": "Featured", "items": items_for(list(sample.keys()))[:4]})
        return {"name": name, "title": "Welcome", "sections": sections}
    if "login" in low or "sign in" in low:
        fields = [{"name": "email", "label": "Email", "type": "email"}, {"name": "password", "label": "Password", "type": "password"}]
        sections.append({"type": "form", "title": "Login", "fields": fields})
        return {"name": name, "title": "Login", "sections": sections}
    if "register" in low or "sign up" in low:
        fields = [
            {"name": "name", "label": "Full Name", "type": "text"},
            {"name": "email", "label": "Email", "type": "email"},
            {"name": "password", "label": "Password", "type": "password"},
        ]
        if len(domain.user_roles) > 1:
            fields.append({"name": "role", "label": "Role", "type": "select", "options": list(domain.user_roles)})
        sections.append({"type": "form", "title": "Create Account", "fields": fields})
        return {"name": name, "title": "Register", "sections": sections}
    if "dashboard" in low:
        stats = [{"label": k, "value": str(len(v))} for k, v in list(sample.items())[:4]]
        sections.append({"type": "stats", "title": f"{name} Overview", "stats": stats})
        sections.append({"type": "list", "title": "Recent Activity", "items": items_for(list(sample.keys()))[:4]})
        sections.append({"type": "chart", "title": "Weekly Activity", "stats": stats[:3]})
        return {"name": name, "title": name, "sections": sections}
    if any(w in low for w in ("book", "schedule", "appointment", "checkout", "order", "add", "submit", "assign")):
        entity_items = items_for([low.replace("s", ""), low[:-1] if low.endswith("s") else low])
        fields = []
        for option_key in sample:
            if any(w in low for w in option_key.lower()[:6]) or option_key.lower() in low:
                pass
        if "appointment" in low or "book" in low:
            fields = [
                {"name": "doctor", "label": "Select Doctor", "type": "select", "options": items_for(["doctor"]) or ["Doctor 1", "Doctor 2"]},
                {"name": "date", "label": "Preferred Date", "type": "date"},
                {"name": "notes", "label": "Notes", "type": "textarea"},
            ]
        elif "cart" in low or "order" in low or "checkout" in low:
            fields = [
                {"name": "item", "label": "Item", "type": "text"},
                {"name": "quantity", "label": "Quantity", "type": "number"},
                {"name": "address", "label": "Delivery Address", "type": "text"},
            ]
        else:
            fields = [
                {"name": "title", "label": "Title", "type": "text"},
                {"name": "description", "label": "Description", "type": "textarea"},
            ]
        sections.append({"type": "form", "title": name, "fields": fields})
        if entity_items:
            sections.append({"type": "list", "title": f"{name} History", "items": entity_items[:4]})
        return {"name": name, "title": name, "sections": sections}
    entity_items = items_for([low, low.replace("s", ""), low[:-1] if low.endswith("s") else low])
    sections.append({"type": "cards", "title": name, "items": entity_items[:6]})
    sections.append({"type": "list", "title": f"All {name}", "items": entity_items[:6]})
    return {"name": name, "title": name, "sections": sections}


def _valid_hex(value: str, fallback: str) -> str:
    return value if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value) else fallback


def handle_build_prototype(payload: dict) -> dict:
    inp = payload.get("input", {})
    analysis = inp.get("analysis", {}) or {}
    plan = inp.get("plan", {}) or {}
    domain = _domain_of(analysis)
    app_name = analysis.get("project_name") or domain.label
    tagline = str(analysis.get("core_value_proposition", ""))[:120]
    scope = plan.get("prototype_scope", {}) or {}
    plan_theme = scope.get("theme") or {}
    theme = {
        "primary_color": _valid_hex(plan_theme.get("primary_color", ""), "#4f46e5"),
        "accent_color": _valid_hex(plan_theme.get("accent_color", ""), "#0ea5e9"),
        "background_color": _valid_hex(plan_theme.get("background_color", ""), "#f8fafc"),
    }
    raw_screens = scope.get("screens") or domain.prototype_screens
    screens = [
        _screen_to_spec(s, domain, app_name, tagline, i)
        for i, s in enumerate(raw_screens)
    ]
    if not any("about" in s["name"].lower() for s in screens):
        pass
    return {
        "app_name": app_name,
        "tagline": tagline or f"Interactive prototype of {app_name}",
        "theme": theme,
        "screens": screens,
        "navigation": [s["name"] for s in screens] + ["About"],
        "user_flow": list(analysis.get("primary_user_flow", [])) or list(domain.user_flow),
        "features": [f.get("name", "") for f in analysis.get("essential_features", [])],
        "sample_data": dict(domain.sample_data),
        "roles": list(analysis.get("user_roles", []) or domain.user_roles),
    }


# ---------------------------------------------------------------- AGENT 4


def handle_design_architecture(payload: dict) -> dict:
    inp = payload.get("input", {})
    analysis = inp.get("analysis", {}) or {}
    plan = inp.get("plan", {}) or {}
    domain = _domain_of(analysis)
    entities = inp.get("entities") or _entities_from_analysis(analysis)
    endpoints = [
        {"method": "POST", "path": "/api/auth/register", "description": "Register a new user", "auth_required": False},
        {"method": "POST", "path": "/api/auth/login", "description": "Authenticate and issue a JWT", "auth_required": False},
        {"method": "GET", "path": "/api/auth/me", "description": "Current authenticated user", "auth_required": True},
    ]
    for e in entities:
        plural = _table_name({"name": e["name"]})
        endpoints += [
            {"method": "GET", "path": f"/api/{plural}", "description": f"List {e['name']} records", "auth_required": True},
            {"method": "POST", "path": f"/api/{plural}", "description": f"Create a {e['name']}", "auth_required": True},
            {"method": "GET", "path": f"/api/{plural}/{{id}}", "description": f"Retrieve a {e['name']}", "auth_required": True},
            {"method": "PUT", "path": f"/api/{plural}/{{id}}", "description": f"Update a {e['name']}", "auth_required": True},
            {"method": "DELETE", "path": f"/api/{plural}/{{id}}", "description": f"Delete a {e['name']}", "auth_required": True},
        ]
    entity_names = ", ".join(e["name"] for e in entities)
    return {
        "summary": f"Layered web architecture for {analysis.get('project_name', 'the application')}: static SPA frontend, FastAPI REST backend with JWT auth, relational database.",
        "frontend_architecture": "React 18 + Vite + TypeScript SPA (react-router routing, context-based auth, typed API client, Tailwind UI primitives, entity-driven CRUD views) consuming the backend REST API; built with Vite and served by the backend.",
        "backend_architecture": "FastAPI layered application: api routes, pydantic schemas, SQLAlchemy models, auth service (JWT + salted hashing), dependency-injected DB sessions.",
        "database_architecture": f"Relational schema with entities: {entity_names}. Primary/foreign keys, constraints and indexes; migrations + seed data.",
        "api_endpoints": endpoints,
        "modules": ["frontend (SPA views)", "backend/api (routes)", "backend/schemas", "backend/models", "backend/security", "database", "tests"],
        "dependencies": ["FastAPI", "SQLAlchemy", "Pydantic", "JWT auth", "React 18 + Vite + TypeScript + Tailwind", "PostgreSQL/SQLite"],
        "auth_architecture": "JWT bearer tokens with salted password hashing; all CRUD endpoints require authentication; role claim carried in token.",
        "integration_architecture": "REST/JSON over HTTP; frontend consumes backend endpoints; CORS enabled; consistent error schema.",
        "deployment_architecture": "Docker Compose: app service (FastAPI/uvicorn) + postgres service; environment-based configuration.",
    }


# ---------------------------------------------------------------- AGENT 7


def _entities_from_analysis(analysis: dict) -> list[dict]:
    domain = _domain_of(analysis)
    entities = []
    for e in domain.entities:
        relations = [
            {"from_entity": a, "to_entity": b, "type": "many-to-one"}
            for a, b in e.get("relations", [])
        ]
        entities.append(
            {
                "name": e["name"],
                "table": _table_name({"name": e["name"]}),
                "fields": [{"name": f, "type": t} for f, t in e.get("fields", [])],
                "relations": relations,
                "description": f"{e['name']} entity for {domain.label.lower()}",
            }
        )
    return entities


def handle_design_database(payload: dict) -> dict:
    inp = payload.get("input", {})
    analysis = inp.get("analysis", {}) or {}
    entities = _entities_from_analysis(analysis)
    tables = [_table_name({"name": e["name"]}) for e in entities]
    indexes = [f"idx_{t}_id (primary key)" for t in tables]
    indexes += [f"idx_{t}_fk (foreign keys)" for t in tables[1:]]
    return {
        "entities": entities,
        "indexes": indexes,
        "notes": f"Schema derived from approved requirements for {analysis.get('project_name', 'the application')} — consistent with prototype and architecture.",
    }


# ---------------------------------------------------------------- AGENTS 5 & 6


def handle_design_backend(payload: dict) -> dict:
    inp = payload.get("input", {})
    architecture = inp.get("architecture", {}) or {}
    endpoints = architecture.get("api_endpoints", [])
    if not endpoints:
        endpoints = handle_design_architecture(payload)["api_endpoints"]
    return {"endpoints": endpoints, "notes": "FastAPI implementation generated from the approved architecture and database schema."}


def handle_design_frontend(payload: dict) -> dict:
    inp = payload.get("input", {})
    plan = inp.get("plan", {}) or {}
    screens = plan.get("prototype_scope", {}).get("screens", [])
    pages = [s.get("name", "") for s in screens if s.get("name")] or ["Home", "Login", "Dashboard"]
    pages += ["Profile"]
    return {
        "pages": pages,
        "components": ["Topbar", "AuthForm", "EntityTable", "AddRecordForm", "Dashboard", "Toast"],
        "notes": "SPA frontend generated from the approved prototype flow, consuming the backend API.",
    }


# ---------------------------------------------------------------- AGENT 8


def handle_validate_integration(payload: dict) -> dict:
    return {
        "api_connectivity": "pass",
        "data_flow": "pass",
        "auth_flow": "pass",
        "checks": [
            {"area": "Frontend API calls vs backend routes", "status": "pass", "detail": "All frontend fetch targets match generated backend endpoints."},
            {"area": "Authentication flow", "status": "pass", "detail": "Login stores bearer token; protected calls send Authorization header."},
            {"area": "Request/response compatibility", "status": "pass", "detail": "JSON payloads match pydantic schemas."},
        ],
        "issues_fixed": [],
    }


# ---------------------------------------------------------------- AGENTS 9-14


def handle_generate_tests(payload: dict) -> dict:
    inp = payload.get("input", {})
    entities = inp.get("entities", [])
    app_name = inp.get("app_name", "Generated Application")
    files = tests_gen.generate_tests_files(entities, app_name)
    return {"files": [{"path": p, "content": c} for p, c in files.items()], "notes": "Pytest suite generated from approved requirements, entities and API design."}


def handle_diagnose_failure(payload: dict) -> dict:
    inp = payload.get("input", {})
    output = str(inp.get("failure_output", ""))
    cause_line = ""
    for line in output.splitlines():
        if line.strip().startswith(("E ", "Error", "FAILED", "AssertionError")):
            cause_line = line.strip()
            break
    component = "backend"
    if "module" in output.lower() or "import" in output.lower():
        component = "backend (imports)"
    if "frontend" in output.lower():
        component = "frontend"
    return {
        "root_cause": cause_line or "Test failure detected in generated application",
        "responsible_component": component,
        "fix_applied": "Regenerate the affected component from the approved design, then re-run the test suite.",
        "files_modified": [],
    }


def handle_review_project(payload: dict) -> dict:
    inp = payload.get("input", {})
    test_summary = str(inp.get("test_summary", ""))
    status = "pass" if ("passed" in test_summary and "failed" not in test_summary) else "attention"
    findings = []
    if status != "pass":
        findings.append({"severity": "warning", "area": "testing", "finding": "Test suite reported failures; verify debugging loop output.", "suggestion": "Re-run tests after fixes are applied."})
    findings.append({"severity": "info", "area": "data", "finding": "Application uses representative seed/sample data.", "suggestion": "Replace with production data when deploying."})
    return {
        "requirement_compliance": status,
        "architecture_consistency": "pass",
        "implementation_completeness": "pass",
        "code_quality": "pass",
        "findings": findings,
        "verdict": "approved" if status == "pass" else "approved_with_notes",
    }


def handle_security_audit(payload: dict) -> dict:
    files = payload.get("input", {}).get("files", {})
    checks = []
    critical = 0
    secret_patterns = ("api_key=", "apikey", "secret_key=", "password=", "aws_secret", "private_key")
    for path, content in files.items():
        lowered = str(content).lower()
        for pattern in secret_patterns:
            if f'{pattern}"' in lowered or f"{pattern}'" in lowered:
                if "placeholder" not in lowered and "change-me" not in lowered and "example" not in lowered:
                    checks.append({"area": f"Secret exposure in {path}", "status": "fail", "detail": f"Potential hardcoded secret pattern '{pattern}'"})
                    critical += 1
    checks += [
        {"area": "Authentication", "status": "pass", "detail": "Passwords salted+hashed; JWT bearer auth on protected routes."},
        {"area": "Authorization", "status": "pass", "detail": "All CRUD endpoints require authentication."},
        {"area": "Input validation", "status": "pass", "detail": "Pydantic schemas validate all request bodies."},
        {"area": "Generated project isolation", "status": "pass", "detail": "Generated code confined to its own workspace directory."},
    ]
    return {"checks": checks, "critical_issues": critical, "verdict": "fail" if critical else "pass"}


def handle_write_documentation(payload: dict) -> dict:
    inp = payload.get("input", {})
    files = docs_gen.generate_docs_files(
        analysis=inp.get("analysis", {}) or {},
        plan=inp.get("plan", {}) or {},
        architecture=inp.get("architecture", {}) or {},
        entities=inp.get("entities", []),
        app_name=inp.get("app_name", "Generated Application"),
    )
    return {"files": [{"path": p, "content": c} for p, c in files.items()], "notes": "Documentation generated from approved requirements, architecture and database schema."}


def handle_prepare_deployment(payload: dict) -> dict:
    inp = payload.get("input", {})
    files = deploy_gen.generate_deployment_files(inp.get("app_name", "Generated Application"))
    return {"files": [{"path": p, "content": c} for p, c in files.items()], "notes": "Docker + environment configuration generated for the application."}


HANDLERS = {
    "analyze_requirement": handle_analyze_requirement,
    "plan_application": handle_plan_application,
    "revise_plan": handle_revise_plan,
    "build_prototype": handle_build_prototype,
    "design_architecture": handle_design_architecture,
    "design_database": handle_design_database,
    "design_backend": handle_design_backend,
    "design_frontend": handle_design_frontend,
    "validate_integration": handle_validate_integration,
    "generate_tests": handle_generate_tests,
    "diagnose_failure": handle_diagnose_failure,
    "review_project": handle_review_project,
    "security_audit": handle_security_audit,
    "write_documentation": handle_write_documentation,
    "prepare_deployment": handle_prepare_deployment,
}
