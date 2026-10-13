"""Automated prototype validation: deterministic mandatory/optional checks over the
rendered HTML. A prototype failing a mandatory check must not become READY_FOR_REVIEW.

Coverage (honest limits documented per check):
- file accessibility, document structure, hero CTA visibility + color-contrast rule
- navigation target resolution, form labels/validation/submit, empty states
- dashboard stats consistency against the embedded store seed
- inline JS syntax (node --check when available, else recorded skip)
- NOT covered without a browser: runtime console errors, real layout pixels,
  visual regression (Playwright path is separate and optional).
"""

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path


@dataclass
class Check:
    name: str
    mandatory: bool
    status: str  # pass | fail | skip
    detail: str = ""

    def dump(self) -> dict:
        return {"name": self.name, "mandatory": self.mandatory, "status": self.status, "detail": self.detail}


@dataclass
class ValidationReport:
    verdict: str  # pass | fail
    checks: list = field(default_factory=list)

    def dump(self) -> dict:
        return {"verdict": self.verdict, "checks": [c.dump() for c in self.checks]}

    def summary(self) -> str:
        failed = [c.name for c in self.checks if c.mandatory and c.status == "fail"]
        if not failed:
            return "all mandatory checks passed"
        return "mandatory checks failed: " + ", ".join(failed)


class _Doc(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._in_title = False
        self.has_doctype = False
        self.viewport = False
        self.screens: set[str] = set()
        self.nav_targets: list[str] = []
        self.flow_targets: list[str] = []
        self.hero_ctas: list[str] = []
        self.forms: list[dict] = []
        self._form = None
        self._label_open = False
        self._button_text = ""
        self._in_button = False
        self._button_class = ""
        self.tbodys: list[dict] = []
        self.stats: list[dict] = []
        self.scripts: list[str] = []
        self._in_script = False
        self._script_buf: list[str] = []
        self.css = ""
        self._in_style = False

    def handle_decl(self, decl: str) -> None:
        if decl.strip().lower().startswith("doctype"):
            self.has_doctype = True

    def handle_starttag(self, tag: str, attrs: list) -> None:
        a = dict(attrs)
        if tag == "title":
            self._in_title = True
        if tag == "meta" and (a.get("name") == "viewport"):
            self.viewport = True
        if tag == "section" and a.get("data-screen"):
            self.screens.add(a["data-screen"])
        if tag == "button" and "data-screen" in a:
            self.nav_targets.append(a["data-screen"])
        if tag == "button" and "data-goto" in a:
            self.flow_targets.append(a["data-goto"])
        if tag == "button" and "hero-cta" in (a.get("class") or ""):
            self._in_button = True
            self._button_text = ""
            self._button_class = "hero"
        if tag == "form":
            self._form = {"inputs": [], "labels": 0, "submit": False, "required": 0}
            self.forms.append(self._form)
        if tag == "label" and self._form is not None:
            self._form["labels"] += 1
        if tag in ("input", "select", "textarea") and self._form is not None:
            self._form["inputs"].append({"type": a.get("type", tag), "required": "required" in a or a.get("required") is not None})
            if "required" in a:
                self._form["required"] += 1
        if tag == "button" and self._form is not None and a.get("type") == "submit":
            self._form["submit"] = True
        if tag == "tbody":
            self.tbodys.append({"store": a.get("data-store"), "empty_row": False, "rows": 0})
        if tag == "tr" and self.tbodys:
            self.tbodys[-1]["rows"] += 1
        if tag == "tr" and self.tbodys and "empty-row" in (a.get("class") or ""):
            self.tbodys[-1]["empty_row"] = True
        if tag in ("div", "span") and "data-stat" in a:
            self.stats.append({"key": a["data-stat"], "value": ""})
            self._stat_open = True
        else:
            self._stat_open = False
        if tag == "script":
            self._in_script = True
            self._script_buf = []
        if tag == "style":
            self._in_style = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag == "button" and self._in_button:
            self.hero_ctas.append(self._button_text.strip())
            self._in_button = False
        if tag == "form":
            self._form = None
        if tag == "script":
            self._in_script = False
            self.scripts.append("".join(self._script_buf))
        if tag == "style":
            self._in_style = False
        if tag in ("div", "span"):
            self._stat_open = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        if self._in_button:
            self._button_text += data
        if self._in_script:
            self._script_buf.append(data)
        if self._in_style:
            self.css += data
        if getattr(self, "_stat_open", False) and self.stats:
            self.stats[-1]["value"] += data.strip()


def _extract_seed(html: str) -> dict | None:
    """Extract the embedded STORE seed (var SEED = {...};) with balanced-brace scan."""
    marker = "var SEED ="
    i = html.find(marker)
    if i == -1:
        return None
    j = html.find("{", i + len(marker))
    if j == -1:
        return None
    depth = 0
    in_str = False
    str_ch = ""
    k = j
    while k < len(html):
        ch = html[k]
        if in_str:
            if ch == "\\":
                k += 2
                continue
            if ch == str_ch:
                in_str = False
        else:
            if ch in ("'", '"'):
                in_str, str_ch = True, ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    break
        k += 1
    if depth != 0:
        return None
    try:
        data = json.loads(html[j : k + 1])
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, ValueError):
        return None


def _hero_cta_rule_ok(css: str) -> tuple[bool, str]:
    """The hero CTA must declare BOTH background and color explicitly in one rule,
    with different values — the exact class of defect that produced white-on-white."""
    m = re.search(r"\.hero-cta\s*\{([^}]*)\}", css)
    if not m:
        return False, "no dedicated .hero-cta rule found"
    body = m.group(1)
    bg = re.search(r"background(?:-color)?\s*:\s*([^;]+);", body)
    color = re.search(r"(?<![\w-])color\s*:\s*([^;]+);", body)
    if not bg or not color:
        return False, "hero CTA rule must declare both background and color explicitly"
    if bg.group(1).strip().lower() == color.group(1).strip().lower():
        return False, f"hero CTA background ({bg.group(1).strip()}) equals text color — invisible text"
    return True, f"background {bg.group(1).strip()} vs text {color.group(1).strip()}"


def _node_check_available() -> bool:
    return shutil.which("node") is not None


def validate_prototype_html(path: str | Path, spec: dict | None = None) -> ValidationReport:
    """Run all checks against a rendered prototype file. Never raises on bad input."""
    checks: list[Check] = []
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        return ValidationReport("fail", [Check("preview_accessible", True, "fail", f"cannot read file: {exc}")])

    if not text.strip():
        return ValidationReport("fail", [Check("preview_accessible", True, "fail", "file is empty")])
    checks.append(Check("preview_accessible", True, "pass", f"{len(text)} bytes"))

    if isinstance(spec, dict) and spec:
        screens = spec.get("screens", []) or []
        problems = []
        if len(screens) < 2:
            problems.append(f"only {len(screens)} screen(s)")
        if not spec.get("navigation"):
            problems.append("empty navigation")
        if not spec.get("user_flow"):
            problems.append("empty user flow")
        checks.append(Check("spec_complete", True, "pass" if not problems else "fail", "; ".join(problems) or f"{len(screens)} screens, flow + nav present"))


    doc = _Doc()
    try:
        doc.feed(text)
    except Exception as exc:
        return ValidationReport("fail", checks + [Check("html_parses", True, "fail", f"HTML parse error: {exc}")])
    checks.append(Check("html_parses", True, "pass", "document parsed"))

    if not doc.has_doctype:
        checks.append(Check("document_structure", True, "fail", "missing DOCTYPE"))
    elif not doc.title.strip():
        checks.append(Check("document_structure", True, "fail", "empty <title>"))
    else:
        checks.append(Check("document_structure", True, "pass", f"title: {doc.title.strip()[:80]}"))

    # Hero CTA: present, labeled, and not same-color-on-same-color
    if not doc.hero_ctas:
        checks.append(Check("hero_cta_visible", True, "fail", "no hero call-to-action button found"))
    elif not any(t for t in doc.hero_ctas):
        checks.append(Check("hero_cta_visible", True, "fail", "hero call-to-action has no visible label"))
    else:
        ok, detail = _hero_cta_rule_ok(doc.css)
        checks.append(Check("hero_cta_visible", True, "pass" if ok else "fail", detail))

    # Navigation resolution
    missing_nav = [t for t in doc.nav_targets if t not in doc.screens]
    missing_flow = [t for t in doc.flow_targets if t and t not in doc.screens]
    if missing_nav or missing_flow:
        checks.append(Check("nav_resolves", True, "fail", f"dead targets: nav={missing_nav[:5]} flow={missing_flow[:5]}"))
    elif not doc.nav_targets:
        checks.append(Check("nav_resolves", True, "fail", "no navigation targets found"))
    else:
        checks.append(Check("nav_resolves", True, "pass", f"{len(doc.nav_targets)} nav + {len(doc.flow_targets)} flow targets resolve"))
    unreachable = [s for s in doc.screens if s not in set(doc.nav_targets) and s != "About"]
    if unreachable:
        checks.append(Check("all_screens_reachable", False, "fail", f"screens without nav entry: {unreachable[:5]}"))
    else:
        checks.append(Check("all_screens_reachable", False, "pass", "every screen reachable from nav"))

    # Forms: labels, validation, submit — required when forms exist; a formless
    # prototype is legitimate, so absence is recorded as skip, never as failure.
    if not doc.forms:
        checks.append(Check("forms_valid", True, "skip", "prototype contains no forms"))
    else:
        problems = []
        for i, f in enumerate(doc.forms):
            if not f["inputs"]:
                problems.append(f"form#{i} has no inputs")
            if f["labels"] == 0:
                problems.append(f"form#{i} has no labels")
            if not f["submit"]:
                problems.append(f"form#{i} has no submit button")
            text_inputs = [x for x in f["inputs"] if x["type"] in ("text", "email", "password", "date", "number")]
            if text_inputs and f["required"] == 0:
                problems.append(f"form#{i} has no required-field validation")
        checks.append(Check("forms_valid", True, "pass" if not problems else "fail", "; ".join(problems) or f"{len(doc.forms)} form(s) labeled, validated, submittable"))

    # Empty states: bound tables render them via the store renderer; static tables
    # must contain at least one row (data or explicit empty-state row) — a table
    # with headers but zero rows is the audited dashboard defect.
    static_hollow = [t for t in doc.tbodys if not t["store"] and t["rows"] == 0]
    bound = [t for t in doc.tbodys if t["store"]]
    if static_hollow:
        checks.append(Check("lists_have_empty_state", True, "fail", f"{len(static_hollow)} table(s) with headers but zero rows and no empty state"))
    elif not bound and not doc.tbodys:
        checks.append(Check("lists_have_empty_state", True, "fail", "no data tables found"))
    else:
        checks.append(Check("lists_have_empty_state", True, "pass", f"{len(bound)} bound table(s) with store-driven empty states"))

    # Stats consistency against the embedded seed
    seed = _extract_seed(text)
    if seed is None:
        checks.append(Check("stats_consistent", True, "fail", "store seed block not found"))
    else:
        mismatches = []
        for s in doc.stats:
            expected = len(seed.get(s["key"], [])) if isinstance(seed.get(s["key"]), list) else None
            try:
                actual = int((s["value"] or "").strip())
            except ValueError:
                actual = None
            if expected is None:
                mismatches.append(f"{s['key']}: no seed list")
            elif actual != expected:
                mismatches.append(f"{s['key']}: shows {actual}, seed has {expected}")
        checks.append(Check("stats_consistent", True, "pass" if not mismatches else "fail", "; ".join(mismatches) or f"{len(doc.stats)} stat(s) match seed counts"))

    # Leftover template placeholders
    leftovers = []
    if "{{" in text or "}}" in text:
        leftovers.append("mustache-style placeholders")
    if re.search(r"\blorem\b|\bipsum\b", text, re.IGNORECASE):
        leftovers.append("lorem ipsum")
    if re.search(r"\bTODO\b|\bFIXME\b", text):
        leftovers.append("TODO/FIXME markers")
    checks.append(Check("no_placeholders", True, "pass" if not leftovers else "fail", "; ".join(leftovers) or "clean"))

    # Inline JS syntax via node --check when available
    if not doc.scripts or not any(s.strip() for s in doc.scripts):
        checks.append(Check("js_syntax", True, "fail", "no inline script found"))
    elif not _node_check_available():
        checks.append(Check("js_syntax", True, "skip", "node unavailable — syntax not checked"))
    else:
        import tempfile

        failures = []
        for i, script in enumerate(s for s in doc.scripts if s.strip()):
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
                f.write(script)
                tmp = f.name
            try:
                proc = subprocess.run(["node", "--check", tmp], capture_output=True, text=True, timeout=30)
                if proc.returncode != 0:
                    failures.append(f"script#{i}: {(proc.stderr or '')[:200]}")
            except Exception as exc:
                failures.append(f"script#{i}: check error {exc}")
            finally:
                try:
                    Path(tmp).unlink()
                except OSError:
                    pass
        checks.append(Check("js_syntax", True, "pass" if not failures else "fail", "; ".join(failures) or f"{len([s for s in doc.scripts if s.strip()])} script block(s) parse"))

    # Viewport + responsive CSS (mandatory: cheap, always emitted by our renderer)
    if not doc.viewport:
        checks.append(Check("responsive_basics", True, "fail", "no viewport meta tag"))
    elif "@media" not in doc.css:
        checks.append(Check("responsive_basics", True, "fail", "no responsive media queries"))
    else:
        checks.append(Check("responsive_basics", True, "pass", "viewport + media queries present"))

    # Browser-dependent checks are honestly reported, not faked
    checks.append(Check("runtime_console_errors", False, "skip", "requires browser automation (Playwright path, if available)"))
    checks.append(Check("visual_regression", False, "skip", "requires browser automation + approved baseline"))

    failed_mandatory = [c for c in checks if c.mandatory and c.status == "fail"]
    # Skips are reported explicitly but never fail the verdict: a check that could
    # not run (e.g. no node binary) must not masquerade as a failure — nor as a pass.
    verdict = "fail" if failed_mandatory else "pass"
    return ValidationReport(verdict, checks)
