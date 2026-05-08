import re
from collections.abc import Callable
from pathlib import Path
from re import Pattern

import re2

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

HIGH_QUALITY_BUCKETS: list[str] = [
    "ScoopInstaller/Main",
    "ScoopInstaller/Extras",
    "ScoopInstaller/Versions",
    "ScoopInstaller/Nirsoft",
    "niheaven/scoop-sysinternals",
    "ScoopInstaller/PHP",
    "matthewjberger/scoop-nerd-fonts",
    "ScoopInstaller/Nonportable",
    "ScoopInstaller/Java",
    "Calinou/scoop-games",
    "Arama120517/scoop-bucket",
]

BUCKETS: list[str] = [
    *HIGH_QUALITY_BUCKETS,
    "scoopcn/scoopcn",
    "rasa/scoops",
    "amorphobia/siku",
    "ACooper81/scoop-apps",
    "kkzzhizhou/scoop-zapps",
    "cderv/r-bucket",
    "chawyehsu/dorado",
    "borger/scoop-galaxy-integrations",
    "hoilc/scoop-lemon",
    "Scoopforge/Extras-CN",
    "Scoopforge/Extras-Plus",
    "littleli/scoop-clojure",
    "TheRandomLabs/scoop-nonportable",
    "TheRandomLabs/Scoop-Spotify",
    "TheRandomLabs/Scoop-Python",
    "Paxxs/Cluttered-bucket",
    "Weidows-projects/scoop-3rd",
    "hermanjustnu/scoop-emulators",
    "borger/scoop-emulators",
    "ViCrack/scoop-bucket",
    "akirco/aki-apps",
    "batkiz/backit",
    "iquiw/scoop-bucket",
    "ygguorun/scoop-bucket",
    "seumsc/scoop-seu",
    "cc713/ownscoop",
    "aoisummer/scoop-bucket",
    "hu3rror/scoop-muggle",
    "starise/Scoop-Confetti",
    "dodorz/scoop",
    "Homeland-Community/scoop",
    "NyaMisty/scoop_bucket_misty",
    "jfut/scoop-jfut",
    "DoveBoy/Apps",
    "starise/Scoop-Gaming",
    "mo-san/scoop-bucket",
    "brian6932/dank-scoop",
    "AkariiinMKII/Scoop4kariiin",
    "littleli/Scoop-littleli",
    "aliesbelik/poldi",
    "KnotUntied/scoop-fonts",
    "HUMORCE/nuke",
    "echoiron/echo-scoop",
]


type Rules = list[tuple[Pattern, str | Callable[[re.Match[str]], str]]]

options = re2.Options()
options.case_sensitive = False


def compile(pattern: str) -> Pattern:
    return re2.compile(pattern, options)


DEFAULT_RULES: Rules = [
    (compile(r"\$bucketsdir\\\\[a-zA-Z]+\\\\"), r"$bucketsdir\\\\$bucket\\\\"),
    (
        compile(
            r"Find-BucketDirectory\s*(?:\([a-zA-Z-]+\)|-Root\s+-Name\s+[a-zA-Z-]+)"
        ),
        r"Find-BucketDirectory -Root -Name main",
    ),
]

GITHUB_RULES: Rules = [
    (
        compile(r"(https://github\.com.+/releases/download/)"),
        lambda m: rf"{GITHUB_URL}/{m.group(1)}",
    ),
    (
        compile(r"(https://github\.com.+/archive/)"),
        lambda m: rf"{GITHUB_URL}/{m.group(1)}",
    ),
    (
        compile(r"(https://(raw|gist)\.githubusercontent\.com)"),
        lambda m: rf"{GITHUB_URL}/{m.group(1)}",
    ),
    (compile(f"{GITHUB_URL}/{GITHUB_URL}"), GITHUB_URL),
    (
        compile(rf"https://[.0-9a-zA-Z]+/{re.escape(GITHUB_URL)}/https:"),
        rf"{GITHUB_URL}/https:",
    ),
]

SOURCEFORGE_RULES: Rules = [
    (
        compile(
            r"(https://sourceforge\.net/projects/[^/]+(?:/files/.+?)?/download)([^a-zA-Z0-9_/]|$)"
            #                                                                  ^^^^^^^^^^^^^^^^^^ 捕获边界
        ),
        lambda m: SOURCEFORGE_URL + "/" + m.group(1) + (m.group(2) or ""),
    ),
    (
        compile(r"(https://(?:download|[a-z0-9.-]+\.dl)\.sourceforge\.net/project/.+)"),
        lambda m: rf"{SOURCEFORGE_URL}/{m.group(1)}",
    ),
    (compile(f"{SOURCEFORGE_URL}/{SOURCEFORGE_URL}"), SOURCEFORGE_URL),
    (
        compile(rf"https://[.0-9a-zA-Z-]+/{re.escape(SOURCEFORGE_URL)}/https:"),
        rf"{SOURCEFORGE_URL}/https:",
    ),
]

PHP_RULES: Rules = [
    (
        compile(r"bin\\postinstall.ps1"),
        r"bin\\php-postinstall.ps1",
    )
]

NODEJS_RULES: Rules = [
    (
        compile(r"https://nodejs.org/dist/"),
        r"https://registry.npmmirror.com/-/binary/node/",
    )
]
