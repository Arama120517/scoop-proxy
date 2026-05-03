import re
from collections.abc import Callable
from pathlib import Path
from re import Pattern

CURRENT_DIR: Path = Path.cwd()
TEMP_DIR: Path = CURRENT_DIR / "temp"

GITHUB_URL: str = "https://v6.gh-proxy.org"
INVALID_GITHUB_URL: list[str] = [
    "https://ghfast.top",
    "https://ghproxy.com",
    "https://ghproxy.net",
    "https://mirror.ghproxy.com",
    "https://ghp.ci",
    "https://ghgo.xyz",
    "https://gh-proxy.org",
    "https://hk.gh-proxy.org",
    "https://cdn.gh-proxy.org",
    "https://edgeone.gh-proxy.org",
]

SOURCEFORGE_URL: str = "https://v6.gh-proxy.org/sourceforge"

SYNC_DIR_NAMES: list[str] = ["bucket", "scripts"]

BUCKETS: list[str] = [
    "ScoopInstaller/Main",
    "ScoopInstaller/Extras",
    "ScoopInstaller/Versions",
    "ScoopInstaller/Nirsoft",
    "ScoopInstaller/Nonportable",
    "ScoopInstaller/Java",
    "niheaven/scoop-sysinternals",
    "matthewjberger/scoop-nerd-fonts",
    "Arama120517/scoop-bucket",
    "chawyehsu/dorado",
    "scoopcn/scoopcn",
    "Scoopforge/Extras-CN",
    "starise/Scoop-Gaming",
    "AkariiinMKII/Scoop4kariiin",
]


def compile(pattern: str) -> Pattern:
    return re.compile(pattern, re.IGNORECASE | re.MULTILINE)


DEFAULT_RULES: list[tuple[Pattern, str]] = [
    (compile(r"\$bucketsdir\\[a-zA-Z\-]+\\"), r"$$bucketsdir\\$$bucket\\"),
    (
        compile(r"Find-BucketDirectory -Root -Name [a-zA-Z]+\)"),
        r"Find-BucketDirectory -Root -Name main)",
    ),
]

GITHUB_RULES: list[tuple[Pattern, str | Callable[[re.Match[str]], str]]] = [
    (
        compile(r"(https://github\.com.+/releases/download/)"),
        lambda m: f"{GITHUB_URL}/{m.group(1)}",
    ),
    (
        compile(r"(https://github\.com.+/archive/)"),
        lambda m: f"{GITHUB_URL}/{m.group(1)}",
    ),
    (
        compile(r"(https://(raw|gist)\.githubusercontent\.com)"),
        lambda m: f"{GITHUB_URL}/{m.group(1)}",
    ),
    (compile(f"{GITHUB_URL}/{GITHUB_URL}"), GITHUB_URL),
    (
        compile(rf"https://[.0-9a-zA-Z]+/{re.escape(GITHUB_URL)}/https:"),
        f"{GITHUB_URL}/https:",
    ),
]

SOURCEFORGE_RULES: list[tuple[Pattern, str | Callable[[re.Match[str]], str]]] = [
    (
        compile(
            r"(https://sourceforge\.net/projects/[^/]+(?:/files/.+?)?/download(?![\w/]))"
        ),
        lambda m: f"{SOURCEFORGE_URL}/{m.group(1)}",
    ),
    (
        compile(
            r"(https://(?:downloads|[a-z0-9.-]+\.dl)\.sourceforge\.net/project/.+)"
        ),
        lambda m: f"{SOURCEFORGE_URL}/{m.group(1)}",
    ),
    (compile(f"{SOURCEFORGE_URL}/{SOURCEFORGE_URL}"), SOURCEFORGE_URL),
    (
        compile(rf"https://[.0-9a-zA-Z-]+/{re.escape(SOURCEFORGE_URL)}/https:"),
        f"{SOURCEFORGE_URL}/https:",
    ),
]
