import contextlib
import json
import re
from collections.abc import Callable
from json import JSONDecodeError
from pathlib import Path
from shutil import copy2, copytree
from typing import Any

from git import Repo, rmtree

from sync.config import (
    BUCKETS,
    CURRENT_DIR,
    GITHUB_URL,
    INVALID_GITHUB_URL,
    SOURCEFORGE_URL,
    SYNC_DIR_NAMES,
    TEMP_DIR,
)


def patch_update(data: str | dict | list) -> str | dict | list:
    if isinstance(data, str):
        return data.replace(f"{GITHUB_URL}/", "")
    if isinstance(data, dict):
        return {k: patch_update(v) for k, v in data.items()}
    if isinstance(data, list):
        return [patch_update(i) for i in data]


def patch(content: str) -> str:
    rules: list[tuple[str, str | Callable[[re.Match[str]], str]]] = [
        (r"\$bucketsdir\\[a-zA-Z\-]+\\", r"$$bucketsdir\\$$bucket\\"),
        (
            r"Find-BucketDirectory -Root -Name [a-zA-Z]+\)",
            r"Find-BucketDirectory -Root -Name main)",
        ),
    ]
    if "github.com" in content or "githubusercontent.com" in content:
        for url in INVALID_GITHUB_URL:
            content: str = content.replace(url, GITHUB_URL)

        rules += [
            (
                r"(https://github\.com.+/releases/download/)",
                lambda m: f"{GITHUB_URL}/{m.group(1)}",
            ),
            (
                r"(https://github\.com.+/archive/)",
                lambda m: f"{GITHUB_URL}/{m.group(1)}",
            ),
            (
                r"(https://(raw|gist)\.githubusercontent\.com)",
                lambda m: f"{GITHUB_URL}/{m.group(1)}",
            ),
            (f"{GITHUB_URL}/{GITHUB_URL}", GITHUB_URL),
            (
                rf"https://[.0-9a-zA-Z]+/{re.escape(GITHUB_URL)}/https:",
                f"{GITHUB_URL}/https:",
            ),
        ]
    elif "sourceforge.net" in content:
        rules += [
            (
                r"(https://sourceforge\.net/projects/[^/]+(?:/files/.+?)?/download(?![\w/]))",
                lambda m: f"{SOURCEFORGE_URL}/{m.group(1)}",
            ),
            (
                r"(https://(?:downloads|[a-z0-9.-]+\.dl)\.sourceforge\.net/project/.+)",
                lambda m: f"{SOURCEFORGE_URL}/{m.group(1)}",
            ),
            (f"{SOURCEFORGE_URL}/{SOURCEFORGE_URL}", SOURCEFORGE_URL),
            (
                rf"https://[.0-9a-zA-Z-]+/{re.escape(SOURCEFORGE_URL)}/https:",
                f"{SOURCEFORGE_URL}/https:",
            ),
        ]

    for pattern, replace in rules:
        content: str = re.sub(
            pattern, replace, content, flags=re.IGNORECASE | re.MULTILINE
        )
    with contextlib.suppress(JSONDecodeError):
        manifest: Any = json.loads(content)
        if "checkver" in manifest:
            manifest["checkver"] = patch_update(manifest["checkver"])
        if "autoupdate" in manifest:
            manifest["autoupdate"] = patch_update(manifest["autoupdate"])
        content: str = json.dumps(manifest, indent=4, ensure_ascii=False)
    return content


def copy(src: str, dst: str, *, follow_symlinks: bool = True) -> str:
    if Path(dst).exists():
        return dst
    return copy2(src, dst, follow_symlinks=follow_symlinks)


for dir_name in [*SYNC_DIR_NAMES, "temp"]:
    result_dir: Path = CURRENT_DIR / dir_name
    if result_dir.exists():
        rmtree(CURRENT_DIR / dir_name)


for repo_name in BUCKETS:
    repo_dir: Path = TEMP_DIR / repo_name.replace("/", "_")
    repo = Repo.clone_from(
        f"{GITHUB_URL}/https://github.com/{repo_name}",
        repo_dir,
        multi_options=["--depth=1", "--filter=blob:none", "--no-checkout"],
    )
    repo.git.sparse_checkout("init", "--cone")
    repo.git.sparse_checkout("set", *SYNC_DIR_NAMES)
    repo.git.checkout("-b", "default", "origin/HEAD")

    for sync_dir_name in SYNC_DIR_NAMES:
        if not (repo_dir / sync_dir_name).exists():
            continue

        result_dir: Path = CURRENT_DIR / sync_dir_name
        copytree(
            repo_dir / sync_dir_name, result_dir, dirs_exist_ok=True, copy_function=copy
        )
        for path in result_dir.rglob("*"):
            if not path.is_file():
                continue
            try:
                content: str = path.read_text("utf-8")
                path.write_text(patch(content), "utf-8")
            except UnicodeDecodeError:
                pass
