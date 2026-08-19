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


def test_hidden_beats_every_layout_rule() -> None:
    """`hidden` must not be silently overridden by the stylesheet.

    `[hidden] { display: none }` is a *user-agent* rule, and any author rule
    beats it. `.app-nav { display: flex }` therefore un-hid a nav that
    JavaScript had explicitly set `hidden` on — the workflow nav appeared
    before any project was open, both navs showed at once, and seven of those
    buttons then threw on a null project and left the page blank.

    The guard needs `!important` rather than mere source order, because
    `[hidden]` and `.app-nav` have identical specificity: without it, whichever
    rule is written last wins, and that is not a property anyone will remember
    while editing a stylesheet.
    """
    # Comments stripped first. Without that this matched the `[hidden] {
    # display: none }` written inside the comment *explaining* the rule, and
    # passed while asserting nothing — the same trap the identifier scans in
    # this file already carry a note about.
    css = re.sub(r"/\*.*?\*/", "", (STATIC / "styles.css").read_text("utf-8"),
                 flags=re.DOTALL)
    rule = re.search(r"\[hidden\]\s*\{([^}]*)\}", css)
    check("styles.css defines a [hidden] rule", bool(rule), True)
    if not rule:
        return
    body = rule.group(1)
    check("it sets display: none", "display" in body and "none" in body, True)
    check("it is !important, so specificity and order cannot defeat it",
          "!important" in body, True)


def test_every_element_the_scripts_hide_is_actually_hideable() -> None:
    """The reverse direction: find the conflict rather than trust the guard.

    For every element the scripts set `.hidden` on, look for a stylesheet rule
    that sets `display` on the same id or on a class that element carries. Any
    such rule is a live override unless the global guard is in place.
    """
    html = (STATIC / "index.html").read_text("utf-8")
    css = (STATIC / "styles.css").read_text("utf-8")
    guarded = bool(re.search(r"\[hidden\]\s*\{[^}]*!important", css))

    hidden_ids: set[str] = set()
    for name in SCRIPTS:
        source = _source(name)
        hidden_ids |= set(re.findall(
            r"getElementById\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\.hidden\s*=", source))

    check("the scripts hide at least one element", bool(hidden_ids), True)

    for element_id in sorted(hidden_ids):
        # The classes that element carries in the HTML.
        tag = re.search(rf'<[^>]*\bid="{re.escape(element_id)}"[^>]*>', html)
        classes: set[str] = set()
        if tag:
            found = re.search(r'class="([^"]*)"', tag.group(0))
            if found:
                classes = set(found.group(1).split())

        selectors = [f"#{element_id}"] + [f".{c}" for c in sorted(classes)]
        conflicting = [
            selector for selector in selectors
            if re.search(rf"(?:^|[,}}])\s*{re.escape(selector)}\s*\{{[^}}]*display\s*:",
                         css, re.MULTILINE)
        ]
        if conflicting:
            check(f"#{element_id} sets display via {conflicting} — needs the "
                  f"[hidden] !important guard", guarded, True)


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


def test_every_nav_button_has_a_view() -> None:
    """A `data-view` with no entry in VIEWS silently falls back to Projects."""
    html = (STATIC / "index.html").read_text("utf-8")
    source = _source("app.js")
    block = re.search(r"const VIEWS\s*=\s*\{(.*?)\n\};", source, re.DOTALL)
    check("app.js declares a VIEWS map", bool(block), True)
    if not block:
        return
    mapped = set(re.findall(r"^\s*(\w+)\s*:", block.group(1), re.MULTILINE))
    for view in sorted(set(re.findall(r'data-view="([^"]+)"', html))):
        check(f"nav button {view!r} has a view function", view in mapped, True)


def test_project_dependent_views_are_declared() -> None:
    """Each view that dereferences the open project must say so.

    Without the declaration the view runs with `state.project === null`, throws,
    and leaves the page blank — which is how a nav bug turned into "nothing
    populates". The list is checked against the source rather than trusted.
    """
    source = _source("app.js")
    block = re.search(r"const VIEWS_NEEDING_A_PROJECT\s*=\s*new Set\(\[(.*?)\]\)",
                      source, re.DOTALL)
    check("app.js declares VIEWS_NEEDING_A_PROJECT", bool(block), True)
    if not block:
        return
    declared = set(re.findall(r"'([^']+)'", block.group(1)))

    # A view function that reads a property straight off `state.project` cannot
    # run without one. `state.project ? …` and `!state.project` are guards, not
    # dereferences, so they do not count.
    for match in re.finditer(r"^function view(\w+)\(\) \{", source, re.MULTILINE):
        name = match.group(1).lower()
        end = source.find("\n}\n", match.end())
        body = source[match.end(): end if end > 0 else len(source)]
        dereferences = re.search(r"state\.project\.\w+", body) or re.search(
            r"const project = state\.project;[\s\S]{0,400}?project\.\w+", body)
        # A view may instead handle the empty case itself — Question and
        # Compliance are useful before a project exists and only need one when
        # you press a button, so they check at that point. Either discipline is
        # fine; having neither is the defect.
        guards = "!state.project" in body
        if dereferences and not guards and name != "projects":
            check(f"view{match.group(1)} reads the project, so it is declared "
                  f"or guards internally", name in declared, True)

    mapped = set(re.findall(r"^\s*(\w+)\s*:", re.search(
        r"const VIEWS\s*=\s*\{(.*?)\n\};", source, re.DOTALL).group(1),
        re.MULTILINE))
    for view in sorted(declared):
        check(f"{view!r} is a real view", view in mapped, True)


def test_apa_is_a_first_class_screen() -> None:
    """The formatting is the point of this tool and it had no screen.

    Four thousand lines across app/apa/, every rule cited to the manual, and
    the only place any of it surfaced was a .docx at the end of an eight-step
    workflow whose first screen is PICO(T). The user asked, reasonably, why
    there was nothing about APA 7 in an APA 7 tool.
    """
    html = (STATIC / "index.html").read_text("utf-8")
    check("APA has its own nav button", 'data-view="apa"' in html, True)

    source = _source("app.js")
    check("and its own view", "function viewApa(" in source, True)
    check("routed", re.search(r"^\s*apa:\s*viewApa,", source, re.MULTILINE)
          is not None, True)

    body = source[source.index("function viewApa("):
                  source.index("function settingsTable(")]
    check("it reads the live report", "/apa" in body, True)
    for section in ("setup", "outstanding", "previews", "headings", "rules",
                    "examples", "fonts"):
        check(f"it shows {section}", section in body, True)

    # APA 7 leads the nav. It is the standard the numbered steps work toward,
    # not step nine, and the user said plainly that it was the main thing they
    # wanted — burying it after "8 · Export" was how it went unnoticed.
    buttons = re.findall(r'data-view="([^"]+)"', html)
    check("APA 7 is the first button in the research nav",
          buttons[0] if buttons else None, "apa")
    check("and is marked as the standard rather than a step",
          'data-view="apa" class="nav-standard"' in html, True)
    check("which the stylesheet sets apart",
          ".nav-standard" in (STATIC / "styles.css").read_text("utf-8"), True)

    # And it must survive having no project. This is the whole point of the
    # change: the formatting rules do not depend on a paper existing, and
    # requiring one to read them repeats the mistake of hiding them behind an
    # export button.
    check("viewApa falls back to the project-free route",
          "'/api/apa'" in body, True)
    check("and only offers Export when a project is open",
          "if (project) {" in body, True)


def test_the_nav_bars_are_never_hidden_wholesale() -> None:
    """Hiding the whole bar takes the always-available screens with it.

    Making `hidden` actually work (see the [hidden] test above) exposed a second
    defect underneath it: `nav.hidden = !state.project` meant that with no
    project open there was no Settings button at all — and Settings is where the
    contact email goes, which every search wants, so it is the one screen you
    need *before* starting a paper. The charting half had the same shape, and
    hiding that bar removed Reference: the licensing register and the plain
    statement of what the tool is not.

    So neither bar may be hidden on its own tab. Visibility is per button.
    """
    app = _source("app.js")
    chart = _source("chart.js")

    check("app.js does not hide the research nav on the project",
          "nav.hidden = !state.project" not in app, True)
    check("chart.js does not hide the charting nav on the encounter",
          "nav.hidden = !chartState.encounter" not in chart, True)

    # Each render toggles `hidden` per button instead.
    check("app.js hides individual research buttons",
          "button.hidden = VIEWS_NEEDING_A_PROJECT" in app, True)
    check("chart.js hides individual charting buttons",
          "button.hidden = CVIEWS_NEEDING_AN_ENCOUNTER" in chart, True)


def test_the_always_available_screens_stay_reachable() -> None:
    """Settings and Reference must never be gated behind creating something."""
    app = _source("app.js")
    chart = _source("chart.js")

    research = re.search(r"const VIEWS_NEEDING_A_PROJECT\s*=\s*new Set\(\[(.*?)\]\)",
                         app, re.DOTALL)
    charting = re.search(r"const CVIEWS_NEEDING_AN_ENCOUNTER\s*=\s*new Set\(\[(.*?)\]\)",
                         chart, re.DOTALL)
    check("app.js declares the gated research views", bool(research), True)
    check("chart.js declares the gated charting views", bool(charting), True)
    if not research or not charting:
        return

    gated_research = set(re.findall(r"'([^']+)'", research.group(1)))
    gated_charting = set(re.findall(r"'([^']+)'", charting.group(1)))

    for view in ("settings", "compliance", "question", "apa"):
        check(f"research {view!r} is reachable without a project",
              view not in gated_research, True)
    check("charting 'reference' is reachable without an encounter",
          "reference" not in gated_charting, True)

    # And the charting router must actually serve Reference in that state,
    # rather than falling through to the encounter picker.
    check("renderChart serves Reference with no encounter open",
          "chartState.view !== 'reference'" in chart, True)


def test_the_shell_and_scripts_are_never_cached() -> None:
    """A cached app.js makes a fixed bug keep reproducing.

    The user hit the same "Cannot read properties of null" twice — once for
    real, and once because the browser was still running the previous
    /static/app.js after the fix had been pushed, pulled and restarted. The
    only cure was a hard refresh nobody thinks to do, and from the outside it
    looks like the fix did not work.

    This is a localhost single-user app: no CDN, no bandwidth budget, files
    measured in tens of kilobytes. Correctness beats a cache hit.
    """
    source = (ROOT / "app" / "main.py").read_text("utf-8")
    middleware = source[source.index("async def enforce_security"):
                        source.index("# ------")]
    check("no-store is set", "no-store" in middleware, True)
    check("on the shell", '"/"' in middleware, True)
    check("and on the scripts", '"/static/"' in middleware, True)
    # The API must not be blanket no-store'd by accident: these headers belong
    # to the two things a browser caches aggressively, not to every response.
    check("scoped by path rather than applied to everything",
          "request.url.path" in middleware, True)


def test_a_rejected_token_is_forgotten() -> None:
    """One stale URL used to lock the page out permanently.

    takeToken stores whatever arrives in the fragment and then strips the
    fragment from the address bar. So pasting a stale URL put the bad token in
    sessionStorage, every reload read it back, and the retry resent it — there
    was no way out from inside the page, and the only escape was pasting a
    *different* URL, which is what someone stuck in this state does not have.
    """
    source = _source("app.js")
    check("there is a single writer for the token",
          "function setToken(" in source, True)
    check("and a way to clear it", "function forgetToken(" in source, True)

    boot = source[source.index("takeToken();"):]
    check("a rejected token is forgotten before the next load",
          "forgetToken()" in boot, True)

    # takeToken must go through setToken rather than writing storage itself,
    # so clearing cannot be bypassed by a future edit.
    taker = source[source.index("function takeToken()"):
                   source.index("function setToken(")]
    check("takeToken delegates the write", "setToken(" in taker, True)
    check("and does not write storage directly",
          "sessionStorage.setItem" in taker, False)


def test_the_gate_accepts_a_pasted_token_or_url() -> None:
    """The escape hatch. Someone locked out is copying from a terminal, and
    either the whole launch URL or the bare token is a reasonable thing to
    grab, so both are accepted."""
    source = _source("app.js")
    check("there is a paste box", "function tokenBox(" in source, True)
    check("and a parser for it", "function tokenFromPaste(" in source, True)

    parser = source[source.index("function tokenFromPaste("):
                    source.index("function tokenBox(")]
    check("it pulls the token out of a URL fragment",
          "token=" in parser, True)
    check("it also accepts a bare token", "A-Za-z0-9_-" in parser, True)

    box = source[source.index("function tokenBox("):]
    box = box[:box.index("\nconst VIEWS") if "\nconst VIEWS" in box else 4000]
    check("a rejected paste is forgotten too", "forgetToken()" in box, True)
    check("Enter submits", "'Enter'" in box, True)


def test_render_survives_a_missing_config() -> None:
    """Nothing can be drawn before /api/config answers.

    shell.js calls render() as soon as the scripts load, before the fetch has
    finished — and again if it failed. Every view reads state.config, so the
    first paint threw "Cannot read properties of null (reading 'settings')" and
    the real cause, a stale session token, never reached the screen: it was a
    toast that faded.
    """
    source = _source("app.js")
    body = source[source.index("function render()"):source.index("const VIEWS = {")]
    check("render checks for the config first", "if (!state.config)" in body, True)
    check("and paints a gate instead of a view", "configGate()" in body, True)
    check("the gate is declared", "function configGate()" in source, True)

    # The bootstrap must record *why* it failed rather than letting guard()
    # swallow it into a toast.
    boot = source[source.index("takeToken();"):]
    check("bootstrap stores the failure", "state.configError" in boot, True)
    check("bootstrap renders either way", boot.count("render()") >= 1, True)
    check("state declares the field", "configError:" in source, True)

    # The gate ends where the paste box begins; the box is asserted separately.
    gate = source[source.index("function configGate()"):
                  source.index("function tokenBox(")]
    # Phrases are checked in a form that survives string concatenation: the
    # source wraps mid-sentence, so "after the #" is split across two literals.
    flat = re.sub(r"'\s*\+\s*'", "", gate)
    for phrase in ("old session token", "after the #", "bash run.sh",
                   "projects are files on disk", "stable across restarts"):
        check(f"the gate explains {phrase!r}", phrase in flat, True)


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


# ==================================================== 6. Startup

# Not front-end code, but the same class of defect and the same suite is where
# anyone would look for it: something the user is told, that is not true.


def test_the_banner_never_advertises_a_port_that_was_not_claimed() -> None:
    """The URL in the banner must be one something is listening on.

    The banner used to print first and uvicorn bound afterwards. With the port
    already taken — a second `run.sh`, or an earlier run still going in another
    terminal — the user got a healthy-looking URL with a bind error underneath
    it, opened the URL, and the browser said the page could not be reached.

    So: the socket is claimed before the banner is composed, and handed to
    uvicorn. That ordering is the whole fix, and it is what this asserts.
    """
    source = (ROOT / "app" / "main.py").read_text("utf-8")
    body = source[source.index("def run() -> None:"):]

    claim = body.find("_claim_port(")
    banner = body.find("startup_banner(")
    check("run() claims the port", claim >= 0, True)
    check("run() prints a banner", banner >= 0, True)
    check("the port is claimed before the banner is printed",
          0 <= claim < banner, True)

    # The claimed socket must be the one served on, or the claim proves nothing.
    check("the claimed socket is handed to uvicorn",
          "sockets=[sock]" in body, True)
    check("uvicorn.run is not used, since it would bind a second time",
          "uvicorn.run(" not in body, True)


def test_an_unclaimable_port_fails_loudly() -> None:
    """No URL may be printed when nothing could be bound."""
    source = (ROOT / "app" / "main.py").read_text("utf-8")
    claim = source[source.index("def _claim_port("):source.index("def run() -> None:")]
    check("it raises rather than returning", "raise SystemExit" in claim, True)
    for phrase in ("already running in another terminal", "RESEARCH_SUITE_PORT"):
        check(f"the failure explains {phrase!r}", phrase in claim, True)
    # Asserted on the call, not the constant's name: the source *comment*
    # explains why SO_REUSEADDR is absent, and a name-based check matched that
    # comment and failed. Comments are prose; setsockopt is behaviour.
    check("it sets no socket option that would let a bind succeed alongside "
          "an existing listener", "setsockopt" not in claim, True)


def test_shell_scripts_are_pinned_to_lf() -> None:
    """A CRLF shebang is the most confusing way this app can fail to start.

    Git for Windows defaults to core.autocrlf=true, which rewrites checked-out
    shell scripts to CRLF. The script then dies with

        bash: ./run.sh: /usr/bin/env bash^M: bad interpreter

    which reads as "the file is missing or broken" while the file looks perfect
    in an editor. Without a .gitattributes nothing prevents it, and nothing on
    screen points at the cause.
    """
    attributes = ROOT.parent / ".gitattributes"
    check(".gitattributes exists at the repository root", attributes.exists(),
          True)
    if not attributes.exists():
        return
    text = attributes.read_text("utf-8")
    check("*.sh is pinned to LF",
          bool(re.search(r"^\*\.sh\s+text\s+eol=lf", text, re.MULTILINE)), True)

    # And the files in the tree must actually be LF, or the attribute is
    # describing something that is not true.
    for name in ("run.sh",):
        raw = (ROOT / name).read_bytes()
        check(f"{name} contains no CR bytes", b"\r" not in raw, True)


def test_the_launcher_names_its_own_failures() -> None:
    """"It won't start" must never be all the user gets.

    Every branch that can stop the launcher says which one it was: no Python, a
    Python too old, or a missing venv module. The failure this replaced printed
    nothing useful and left the browser pointed at a dead URL.
    """
    script = (ROOT / "run.sh").read_text("utf-8")
    for phrase, why in [
        ("Python 3.11 or newer", "the version requirement"),
        ("python3-venv", "Debian's separately-packaged venv module"),
        ("KRS_PYTHON", "the override for a differently-named interpreter"),
        ("run.ps1", "the Windows launcher"),
        ("bash run.sh", "the fallback when the executable bit or shebang fails"),
    ]:
        check(f"run.sh mentions {why}", phrase in script, True)
    # It must try more than one interpreter name: minimal installs have only
    # one of python3 and python, and "python3: not found" is a dead end for
    # someone who does have Python.
    check("run.sh tries more than one interpreter name",
          "python3 python" in script, True)
    check("run.sh exits non-zero when it cannot find one",
          "exit 1" in script, True)


def test_the_launcher_refreshes_a_stale_environment() -> None:
    """A pull that adds a dependency must not leave the venv behind.

    Installing only when `.venv` was absent meant a newly added, optional,
    guarded dependency silently did not install — so the feature it backed just
    did not work, with nothing on screen to say why.
    """
    for name in ("run.sh", "run.ps1"):
        script = (ROOT / name).read_text("utf-8")
        check(f"{name} hashes requirements.txt",
              "requirements.txt" in script and "sha" in script.lower(), True)
        check(f"{name} reinstalls when the hash differs",
              script.count("pip install --quiet -r requirements.txt") >= 2, True)


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
