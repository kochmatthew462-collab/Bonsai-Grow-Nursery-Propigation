"""
Static checks on the front end.

This suite exists because of a bug it would have caught immediately: `app.js`
shipped with a missing closing parenthesis. Every other test passed, the file was
served with HTTP 200, and the whole application UI was dead — a syntax error takes
out the entire script, so `app.js` defined none of its globals and both `chart.js`
and `shell.js` then failed on the first identifier they touched.

Serving a file is not the same as the file working. Nothing in a Python test suite
notices that, so these checks look at the JavaScript itself:

1. **It parses.** `node --check` on every script. This is the check that matters
   and it is the one that was missing.
2. **Cross-file identifiers resolve.** `chart.js` and `shell.js` are classic
   scripts that rely on globals declared in `app.js`. A rename in one file and not
   the other produces a runtime `ReferenceError` that no amount of Python testing
   would find.
3. **Every element the scripts look up exists in the HTML.** A typo in a
   `getElementById` is silent until the moment a user clicks the thing.
4. **Every API path the front end calls exists on the server.** A path that drifts
   returns 404 at the worst possible moment.

If `node` is not installed the parse check reports that it was skipped rather than
passing quietly — a skipped check that looks like a pass is how this class of bug
survives.

Run: python3 tests/test_frontend.py
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

STATIC = ROOT / "app" / "static"

FAILURES: list[str] = []
NOTES: list[str] = []
CHECKS = 0


def check(label: str, got, want) -> None:
    global CHECKS
    CHECKS += 1
    if got != want:
        FAILURES.append(f"{label}\n     got: {got!r}\n    want: {want!r}")


# ============================================================== 1. it parses


SCRIPTS = ["app.js", "chart.js", "shell.js"]


def test_scripts_parse() -> None:
    """The check that would have caught the shipped syntax error."""
    node = shutil.which("node")
    if not node:
        NOTES.append(
            "node is not installed, so the JavaScript parse check was SKIPPED. "
            "Install node to run it — a syntax error in any of these files takes "
            "out the entire UI, and no other test in this suite would notice."
        )
        return
    for name in SCRIPTS:
        path = STATIC / name
        check(f"{name} exists", path.exists(), True)
        if not path.exists():
            continue
        result = subprocess.run([node, "--check", str(path)],
                                capture_output=True, text=True)
        if result.returncode != 0:
            FAILURES.append(f"{name} does not parse\n    "
                            + result.stderr.strip().split("\n")[0])
        global CHECKS
        CHECKS += 1


# =================================================== 2. cross-file identifiers


def _source(name: str) -> str:
    path = STATIC / name
    return path.read_text("utf-8") if path.exists() else ""


def _code_only(source: str) -> str:
    """Source with comments and string bodies blanked out.

    Without this, an identifier check scans English prose: the word "correction"
    inside a comment, or "identifier" inside a user-facing string, reads as a call
    to an undefined function. Blanking rather than deleting keeps offsets and line
    structure intact.
    """
    out = re.sub(r"/\*.*?\*/", " ", source, flags=re.S)
    out = re.sub(r"(?m)//.*$", "", out)
    out = re.sub(r"'(?:\\.|[^'\\\n])*'", "''", out)
    out = re.sub(r'"(?:\\.|[^"\\\n])*"', '""', out)
    out = re.sub(r"`(?:\\.|[^`\\])*`", "``", out, flags=re.S)
    return out


def _declared(source: str) -> set[str]:
    """Top-level names a classic script contributes to the global scope."""
    code = _code_only(source)
    names: set[str] = set()
    names |= set(re.findall(r"^(?:const|let|var)\s+([A-Za-z_$][\w$]*)", code, re.M))
    names |= set(re.findall(r"^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)", code,
                            re.M))
    return names


def _any_scope_names(source: str) -> set[str]:
    """Every binding, at any indentation — locals, params and arrow functions.

    Used only for the "is this call defined" check, which cares whether a name
    resolves at all rather than whether it is global.
    """
    code = _code_only(source)
    names: set[str] = set()
    names |= set(re.findall(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)", code))
    names |= set(re.findall(r"\b(?:async\s+)?function\s+([A-Za-z_$][\w$]*)", code))
    # Parameters of both anonymous and named function declarations —
    # `function repeatable(title, hint, list, columns, blank, onChange)` binds six
    # names that are called later in the body.
    for group in re.findall(r"\bfunction\s*[A-Za-z_$][\w$]*\s*\(([^)]*)\)", code):
        for part in group.split(","):
            cleaned = part.strip().split("=")[0].strip()
            if cleaned.isidentifier():
                names.add(cleaned)
    for group in re.findall(r"\bfunction\s*\(([^)]*)\)", code):
        for part in group.split(","):
            cleaned = part.strip().split("=")[0].strip()
            if cleaned.isidentifier():
                names.add(cleaned)
    # Destructured and plain parameters of arrow functions.
    for group in re.findall(r"\(([^()]*)\)\s*=>", code):
        for part in group.split(","):
            cleaned = part.strip().split("=")[0].strip()
            if cleaned.isidentifier():
                names.add(cleaned)
    for single in re.findall(r"(?<![\w$])([A-Za-z_$][\w$]*)\s*=>", code):
        names.add(single)
    return names


# What each file relies on the others to have defined. Listed explicitly rather
# than inferred, because an inferred list would silently shrink if a use were
# deleted, and the point is to pin the contract.
_SHARED_FROM_APP_JS = [
    "state", "api", "post", "toast", "guard", "el", "card", "notice", "chip",
    "field", "statBlock", "render", "takeToken",
]
_SHARED_FROM_CHART_JS = [
    "chartState", "renderChart", "goChart", "initCharting",
]


def test_shared_globals_are_declared() -> None:
    app_names = _declared(_source("app.js"))
    chart_names = _declared(_source("chart.js"))

    for name in _SHARED_FROM_APP_JS:
        check(f"app.js declares {name} (used by chart.js/shell.js)",
              name in app_names, True)
    for name in _SHARED_FROM_CHART_JS:
        check(f"chart.js declares {name} (used by shell.js)",
              name in chart_names, True)


def test_no_duplicate_top_level_declarations() -> None:
    """Two `const` of the same name in different classic scripts is a hard
    `SyntaxError: Identifier has already been declared` at load, and it takes out
    the page exactly like a missing paren does."""
    seen: dict[str, str] = {}
    for name in SCRIPTS:
        for identifier in _declared(_source(name)):
            if identifier in seen:
                FAILURES.append(
                    f"{identifier!r} is declared at top level in both "
                    f"{seen[identifier]} and {name} — classic scripts share one "
                    f"global scope, so this throws at load")
            seen[identifier] = name
        global CHECKS
        CHECKS += 1


def test_chart_js_calls_are_defined_somewhere() -> None:
    """Every function chart.js calls must be defined in chart.js or app.js."""
    chart = _source("chart.js")
    known = (_any_scope_names(chart) | _any_scope_names(_source("app.js")))
    # Browser and language builtins the scripts legitimately use.
    builtins = {
        "Object", "Array", "String", "Number", "Boolean", "Math", "JSON", "Date",
        "Promise", "Set", "Map", "RegExp", "Error", "parseInt", "parseFloat",
        "isNaN", "encodeURIComponent", "decodeURIComponent", "setTimeout",
        "clearTimeout", "setInterval", "clearInterval", "fetch", "FormData",
        "document", "window", "location", "history", "sessionStorage", "console",
        "navigator", "confirm", "alert", "require", "if", "for", "while",
        "switch", "catch", "return", "function", "typeof", "new", "await",
        "async", "of", "in", "do", "else", "try",
    }
    called = set(re.findall(r"(?<![\w.$])([A-Za-z_$][\w$]*)\s*\(",
                            _code_only(chart)))
    missing = sorted(n for n in called if n not in known and n not in builtins)
    check("every function chart.js calls is defined", missing, [])


def test_shell_js_calls_are_defined() -> None:
    shell = _source("shell.js")
    known = (_any_scope_names(shell) | _any_scope_names(_source("app.js"))
             | _any_scope_names(_source("chart.js")))
    builtins = {
        "Object", "Array", "String", "Math", "JSON", "Set", "document", "window",
        "sessionStorage", "console", "if", "for", "while", "catch", "return",
        "function", "typeof", "new", "await", "async", "of", "in", "do", "else",
        "try",
    }
    called = set(re.findall(r"(?<![\w.$])([A-Za-z_$][\w$]*)\s*\(",
                            _code_only(shell)))
    missing = sorted(n for n in called if n not in known and n not in builtins)
    check("every function shell.js calls is defined", missing, [])


# ================================================= 3. element ids exist in HTML


def test_element_ids_exist() -> None:
    """A typo in getElementById is silent until someone clicks the thing."""
    html = (STATIC / "index.html").read_text("utf-8")
    declared_ids = set(re.findall(r'\bid="([^"]+)"', html))
    # Ids the scripts create themselves — `el('div', { id: 'gate-panel' }, …)` —
    # are just as real as ids in the HTML, and are looked up the same way.
    for script in SCRIPTS:
        declared_ids |= set(re.findall(r"id:\s*'([^']+)'", _source(script)))
        declared_ids |= set(re.findall(r'id:\s*"([^"]+)"', _source(script)))

    for name in SCRIPTS:
        source = _source(name)
        for looked_up in re.findall(r"getElementById\(\s*'([^']+)'", source):
            check(f"{name} looks up #{looked_up}, which exists in index.html",
                  looked_up in declared_ids, True)
        for looked_up in re.findall(r'getElementById\(\s*"([^"]+)"', source):
            check(f"{name} looks up #{looked_up}, which exists in index.html",
                  looked_up in declared_ids, True)


def test_query_selectors_resolve() -> None:
    """The class and data-attribute selectors the shell relies on."""
    html = (STATIC / "index.html").read_text("utf-8")
    for selector, needle in [
        (".tabbar", 'class="tabbar"'),
        ("[data-tab]", "data-tab="),
        ("[data-view]", "data-view="),
        ("[data-cview]", "data-cview="),
    ]:
        used = any(selector in _source(name) for name in SCRIPTS)
        if used:
            check(f"{selector} has a match in index.html", needle in html, True)


def test_html_loads_every_script() -> None:
    html = (STATIC / "index.html").read_text("utf-8")
    for name in SCRIPTS:
        check(f"index.html loads {name}", f"/static/{name}" in html, True)
    # Order matters: app.js declares the shared helpers, chart.js declares the
    # charting entry points, and shell.js runs immediately and calls both.
    positions = [html.index(f"/static/{name}") for name in SCRIPTS]
    check("scripts load in dependency order", positions, sorted(positions))


# ==================================================== 4. API paths exist


def _server_paths() -> set[str]:
    """Every route path the server declares, with parameters normalised."""
    paths: set[str] = set()
    for source_file in (ROOT / "app" / "main.py",
                        ROOT / "app" / "charting" / "routes.py"):
        text = source_file.read_text("utf-8")
        prefix = ""
        match = re.search(r'APIRouter\(prefix="([^"]+)"', text)
        if match:
            prefix = match.group(1)
        for path in re.findall(
                r'@(?:app|router)\.(?:get|post|delete|put)\(\s*"([^"]+)"', text):
            paths.add(re.sub(r"\{[^}]+\}", "{}", prefix + path))
    return paths


def _client_paths() -> set[str]:
    """Every path the front end builds, with interpolations normalised."""
    paths: set[str] = set()
    for name in SCRIPTS:
        source = _source(name)
        # Template literals and plain strings alike.
        for raw in re.findall(r"[`'\"](/api/[^`'\"]*)[`'\"]", source):
            cleaned = re.sub(r"\$\{[^}]*\}", "{}", raw)
            cleaned = cleaned.split("?")[0].rstrip("/")
            # `chartApi` is defined as `api('/api/charting' + path)`, so the bare
            # router prefix appears as a literal. It is a prefix, not an endpoint.
            if cleaned in ("/api", "/api/charting"):
                continue
            paths.add(cleaned)
        # chartApi('/xyz') prepends the charting prefix.
        for raw in re.findall(r"chartApi\(\s*[`'\"](/[^`'\"]*)[`'\"]", source):
            cleaned = re.sub(r"\$\{[^}]*\}", "{}", raw)
            cleaned = cleaned.split("?")[0].rstrip("/")
            paths.add("/api/charting" + cleaned)
    return paths


def _covers(one: str, other: str) -> bool:
    """Whether two normalised paths describe the same endpoint.

    The front end builds several paths by concatenation — a template literal that
    ends in a slash, plus a variable — so the client side loses the final "{}"
    segment the server declares. Comparing with a prefix test in both directions
    matches those without matching genuinely different routes, because a route
    only ever differs from its prefix by a parameter segment.
    """
    a = one.rstrip("/")
    b = other.rstrip("/")
    if a == b:
        return True
    for long, short in ((a, b), (b, a)):
        if long.startswith(short) and long[len(short):].strip("/") in ("{}", ""):
            return True
    return False


def test_every_called_path_exists() -> None:
    server = _server_paths()
    # Concatenated paths (a prefix string plus a variable) normalise to a trailing
    # "{}" segment; accept a server path that matches once its own parameters are
    # normalised the same way.
    unmatched: list[str] = []
    for path in sorted(_client_paths()):
        if path in server:
            continue
        # The front end sometimes builds ".../loops/" + id, which normalises with a
        # trailing slash removed and the id absent.
        if any(_covers(path, candidate) for candidate in server):
            continue
        unmatched.append(path)
    check("every API path the front end calls exists on the server", unmatched, [])


def test_charting_routes_are_reachable_from_the_ui() -> None:
    """The reverse direction: a route nobody calls is dead code, and more often it
    is a feature that was built and never wired up."""
    called = _client_paths()
    server = _server_paths()
    charting = {p for p in server if p.startswith("/api/charting")}
    orphaned = sorted(
        p for p in charting
        if not any(_covers(p, c) for c in called)
    )
    check("no charting route is orphaned from the UI", orphaned, [])


# Routes the browser reaches without any script asking for them: the shell
# itself, and a health check meant for the terminal.
NOT_CALLED_BY_SCRIPT = {"/", "/healthz", "/static", "/api/config"}


def test_research_routes_are_reachable_from_the_ui() -> None:
    """The same check on the research side, where it was not being run.

    Extending it found seven endpoints with no caller — among them the entire
    figure generator, which is a feature of the specification rather than a
    loose end. An endpoint nobody can reach is indistinguishable from one that
    was never built, and it passes every other test in this suite.
    """
    called = _client_paths()
    orphaned = sorted(
        p for p in _server_paths()
        if not p.startswith("/api/charting")
        and p not in NOT_CALLED_BY_SCRIPT
        and not any(_covers(p, c) for c in called)
    )
    check("no research route is orphaned from the UI", orphaned, [])


def main() -> int:
    for name, function in sorted(globals().items()):
        if name.startswith("test_") and callable(function):
            function()
    print(f"tests/test_frontend.py: {CHECKS} checks, {len(FAILURES)} failures")
    for note in NOTES:
        print(f"  ! {note}")
    for failure in FAILURES:
        print(f"  ✗ {failure}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
