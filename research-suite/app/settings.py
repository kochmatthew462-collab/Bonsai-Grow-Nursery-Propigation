"""
Configuration and secret handling.

The request was for "a secure site used only by me". The honest architecture for
that is **not** a hosted site: it is a local application that binds to
`127.0.0.1`, holds its keys in the OS keychain or a git-ignored `.env`, and is
never reachable from the network at all. A hosted single-user site has to solve
authentication, TLS, key storage and access control before it is as safe as a
localhost app is on the first run.

Why not a static site like the nursery tracker in this repo: that app has nothing
to keep secret, so shipping it as plain files on GitHub Pages is exactly right.
This one holds an NCBI key, an Anthropic key and a contact email, and needs to
call a dozen APIs that do not send CORS headers. Neither is possible from a
static page — a key in front-end JavaScript is a published key.

Secret resolution order, first hit wins:

1. an explicit environment variable (what CI and containers use);
2. the OS keychain via `keyring`, when it is available and unlocked;
3. a `.env` file next to the application.

`.env` is in `.gitignore`, and `redacted()` exists so configuration can be shown
in the UI and written into the audit document without leaking anything.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

APP_NAME = "koch-research-suite"

# Keys the suite knows about. Every one is optional: with none of them the tool
# still searches Europe PMC, Crossref, OpenAlex, ERIC, ClinicalTrials.gov, CDC
# and WHO, imports citation files, appraises, builds matrices and writes both
# documents. Keys buy rate limits and drafting, not core function.
KNOWN_SECRETS = {
    "anthropic": {
        "env": "ANTHROPIC_API_KEY",
        "label": "Anthropic API key",
        "enables": "AI-assisted drafting of the claim ledger and the abstract.",
        "without": ("Everything else works. Write claims yourself in the Claims "
                    "editor, or draft in Word and paste them in."),
        "get": "https://console.anthropic.com/settings/keys",
    },
    "ncbi": {
        "env": "NCBI_API_KEY",
        "label": "NCBI API key",
        "enables": "Raises PubMed's rate limit from 3 to 10 requests per second.",
        "without": "PubMed still works, just more slowly on large searches.",
        "get": "https://account.ncbi.nlm.nih.gov/settings/",
    },
    "openalex": {
        "env": "OPENALEX_API_KEY",
        "label": "OpenAlex API key",
        "enables": ("OpenAlex search, its retraction flag, and open-access "
                    "locations."),
        "without": ("OpenAlex has required a key since February 2026 — anonymous "
                    "callers get about 100 credits a day, which one search "
                    "spends. Signup is free. Retraction checking still works "
                    "through Crossref and MEDLINE without it."),
        "get": "https://openalex.org/",
    },
    "semantic_scholar": {
        "env": "SEMANTIC_SCHOLAR_API_KEY",
        "label": "Semantic Scholar API key",
        "enables": "Higher rate limits on Semantic Scholar lookups.",
        "without": "Unauthenticated access works at about one request per second.",
        "get": "https://www.semanticscholar.org/product/api",
    },
    "scopus": {
        "env": "SCOPUS_API_KEY",
        "label": "Elsevier / Scopus API key",
        "enables": "Scopus search, to the extent your entitlement allows.",
        "without": ("Scopus is import-only: run the search on scopus.com and "
                    "import the CSV or RIS export."),
        "get": "https://dev.elsevier.com/",
    },
    "copyleaks": {
        "env": "COPYLEAKS_API_KEY",
        "label": "Copyleaks API key",
        "enables": "A web-wide similarity index alongside the built-in overlap report.",
        "without": ("The built-in check compares your draft against the sources "
                    "you cited, which is the check that catches accidental "
                    "borrowing from your own reading."),
        "get": "https://api.copyleaks.com/",
    },
}


@dataclass
class Settings:
    root: Path
    data_dir: Path
    cache_dir: Path
    export_dir: Path
    host: str = "127.0.0.1"
    port: int = 8765
    contact_email: str = ""
    default_font: str = "Times New Roman"
    session_token: str = ""
    api_keys: dict[str, str] = field(default_factory=dict)
    keyring_available: bool = False
    env_file: Path | None = None

    # ---------------------------------------------------------------- secrets

    def key(self, name: str) -> str:
        return self.api_keys.get(name, "")

    def redacted(self) -> dict[str, object]:
        """Configuration safe to render in the UI or write into a document."""
        return {
            "host": self.host,
            "port": self.port,
            "contact_email": self.contact_email,
            "default_font": self.default_font,
            "data_dir": str(self.data_dir),
            "export_dir": str(self.export_dir),
            "keyring_available": self.keyring_available,
            "env_file": str(self.env_file) if self.env_file else None,
            "keys": [
                {
                    "name": name,
                    "label": spec["label"],
                    "configured": bool(self.api_keys.get(name)),
                    "hint": _hint(self.api_keys.get(name, "")),
                    "enables": spec["enables"],
                    "without": spec["without"],
                    "get": spec["get"],
                    "env": spec["env"],
                }
                for name, spec in KNOWN_SECRETS.items()
            ],
        }

    def store_key(self, name: str, value: str) -> str:
        """Save a key to the OS keychain, falling back to `.env`.

        Returns where it went, so the UI can tell the user rather than leaving
        them to guess whether a key survives a restart.
        """
        if name not in KNOWN_SECRETS:
            raise ValueError(f"unknown key {name!r}")
        value = value.strip()
        if not value:
            self.api_keys.pop(name, None)
            return "cleared for this session"

        self.api_keys[name] = value
        if self.keyring_available:
            try:
                import keyring
                keyring.set_password(APP_NAME, name, value)
                return "OS keychain"
            except Exception:
                pass
        written = self._write_env(KNOWN_SECRETS[name]["env"], value)
        return f".env file ({written})" if written else "this session only"

    def _write_env(self, variable: str, value: str) -> str:
        path = self.env_file or (self.root / ".env")
        try:
            lines: list[str] = []
            if path.exists():
                lines = [
                    line for line in path.read_text("utf-8").splitlines()
                    if not line.strip().startswith(f"{variable}=")
                ]
            lines.append(f"{variable}={value}")
            path.write_text("\n".join(lines) + "\n", "utf-8")
            try:
                path.chmod(0o600)   # owner-only; a world-readable key file is a leak
            except OSError:
                pass
            self.env_file = path
            return str(path)
        except OSError:
            return ""


def _hint(value: str) -> str:
    """The last four characters, so a user can tell which key is loaded without
    the key being displayed."""
    if not value:
        return ""
    return f"…{value[-4:]}" if len(value) > 8 else "…"


def load(root: Path | None = None) -> Settings:
    root = (root or Path(__file__).resolve().parents[1]).resolve()
    data_dir = Path(os.environ.get("RESEARCH_SUITE_DATA", root / "data")).resolve()
    settings = Settings(
        root=root,
        data_dir=data_dir,
        cache_dir=data_dir / "cache",
        export_dir=Path(os.environ.get("RESEARCH_SUITE_EXPORTS",
                                       data_dir / "exports")).resolve(),
    )
    for directory in (settings.data_dir, settings.cache_dir, settings.export_dir):
        directory.mkdir(parents=True, exist_ok=True)

    env_path = root / ".env"
    env_values = _read_env(env_path)
    if env_values:
        settings.env_file = env_path

    settings.keyring_available = _keyring_works()

    for name, spec in KNOWN_SECRETS.items():
        value = (
            os.environ.get(spec["env"], "").strip()
            or _from_keyring(name)
            or env_values.get(spec["env"], "")
        )
        if value:
            settings.api_keys[name] = value

    settings.contact_email = (
        os.environ.get("RESEARCH_SUITE_EMAIL", "").strip()
        or env_values.get("RESEARCH_SUITE_EMAIL", "")
    )
    settings.host = os.environ.get("RESEARCH_SUITE_HOST", "127.0.0.1").strip()
    settings.port = int(os.environ.get("RESEARCH_SUITE_PORT", "8765"))
    settings.default_font = (
        os.environ.get("RESEARCH_SUITE_FONT", "").strip()
        or env_values.get("RESEARCH_SUITE_FONT", "")
        or "Times New Roman"
    )

    # A fresh token each run. Printed once at startup; the browser is handed it
    # in the launch URL, so nothing else on the machine can reach the API.
    settings.session_token = (
        os.environ.get("RESEARCH_SUITE_TOKEN", "").strip()
        or secrets.token_urlsafe(24)
    )
    return settings


def _read_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    try:
        for line in path.read_text("utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            values[name.strip()] = value.strip().strip("'\"")
    except OSError:
        return {}
    return values


def _keyring_works() -> bool:
    """Whether a usable keychain backend is present.

    `keyring` imports successfully on headless Linux but then raises on first
    use, so the check has to attempt a real read.
    """
    try:
        import keyring
        from keyring.backends import fail
        backend = keyring.get_keyring()
        if isinstance(backend, fail.Keyring):
            return False
        keyring.get_password(APP_NAME, "__probe__")
        return True
    except Exception:
        return False


def _from_keyring(name: str) -> str:
    try:
        import keyring
        return (keyring.get_password(APP_NAME, name) or "").strip()
    except Exception:
        return ""


def contact_email_warning(settings: Settings) -> str:
    """NCBI's usage policy asks callers to identify themselves; Unpaywall
    requires an address outright. Better to say so than to fail quietly."""
    if settings.contact_email:
        return ""
    return (
        "No contact email is configured. NCBI's E-utilities usage policy asks "
        "every client to identify itself, Crossref and OpenAlex give faster and "
        "more reliable service to clients that do, and Unpaywall requires an "
        "address. Set one on the Settings page — it is sent only to those APIs, "
        "in the User-Agent header, and nowhere else."
    )
