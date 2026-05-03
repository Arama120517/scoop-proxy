from pathlib import Path

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
