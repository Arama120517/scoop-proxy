import contextlib
import json
import math
import os
import re
from collections.abc import Callable
from enum import IntEnum
from json import JSONDecodeError
from pathlib import Path
from re import Pattern
from shutil import copy2, copytree, rmtree
from typing import Any

from git import Repo

from sync.config import (
    BUCKETS,
    CURRENT_DIR,
    DEFAULT_RULES,
    GITHUB_RULES,
    GITHUB_URL,
    INVALID_GITHUB_URL,
    SOURCEFORGE_RULES,
    SYNC_DIR_NAMES,
    TEMP_DIR,
)


class SemverStatus(IntEnum):
    GREATER = 1  # a > b
    LESS = -1  # a < b
    EQUAL = 0  # a == b


def semver_compare(old: str, new: str) -> SemverStatus:
    old: str = re.sub(r"[^\d.]", "", str(old or "").replace("-", "."))
    new: str = re.sub(r"[^\d.]", "", str(new or "").replace("-", "."))

    old_segments, new_segments = old.split("."), new.split(".")

    count: int = max(len(old_segments), len(new_segments), 3)

    def to_num(s: str) -> float:
        if not s:
            return 0.0
        try:
            return float(s)
        except ValueError:
            return float("nan")

    for i in range(count):
        old_num: int | float = (
            to_num(s=old_segments[i]) if i < len(old_segments) else float("nan")
        )
        new_num: int | float = (
            to_num(s=new_segments[i]) if i < len(new_segments) else float("nan")
        )
        old_num_is_nan: bool = math.isnan(old_num)
        new_num_is_nan: bool = math.isnan(new_num)

        if old_num > new_num or (not old_num_is_nan and new_num_is_nan):
            return SemverStatus.GREATER
        elif new_num > old_num or (old_num_is_nan and not new_num_is_nan):
            return SemverStatus.LESS
    return SemverStatus.EQUAL


def patch_update(data: str | dict | list) -> str | dict | list:
    if isinstance(data, str):
        return data.replace(f"{GITHUB_URL}/", "")
    if isinstance(data, dict):
        return {k: patch_update(v) for k, v in data.items()}
    if isinstance(data, list):
        return [patch_update(i) for i in data]


existing_files: list[str] = []


def is_exists(dst: str) -> bool:
    return dst.lower() in existing_files


def copy(src: str, dst: str, *_) -> str:
    src_file, dst_file = Path(src), Path(dst)

    try:
        content: str = src_file.read_text("utf-8")
    except UnicodeDecodeError:
        return dst if is_exists(dst) else copy2(src, dst)

    if src_file.suffix == ".json":
        content: str = json.dumps(json.loads(content), indent=4, ensure_ascii=False)
        if is_exists(dst):
            src_ver: str = json.loads(content)["version"]
            dst_ver: str = json.loads(dst_file.read_text("utf-8"))["version"]
            status: SemverStatus = semver_compare(dst_ver, src_ver)
            if status == SemverStatus.EQUAL or status.GREATER:
                return dst
    else:
        content: str = content.replace("\r\n", "\n").strip()

    rules: list[tuple[Pattern, str | Callable[[re.Match[str]], str]]] = []
    rules += DEFAULT_RULES
    if "github.com" in content or "githubusercontent.com" in content:
        for url in INVALID_GITHUB_URL:
            content: str = content.replace(url, GITHUB_URL)
        rules += GITHUB_RULES
    elif "sourceforge.net" in content:
        rules += SOURCEFORGE_RULES

    for pattern, replace in rules:
        content: str = pattern.sub(replace, content)

    with contextlib.suppress(JSONDecodeError):
        manifest: Any = json.loads(content)
        if "checkver" in manifest:
            manifest["checkver"] = patch_update(manifest["checkver"])
        if "autoupdate" in manifest:
            manifest["autoupdate"] = patch_update(manifest["autoupdate"])
        content: str = json.dumps(manifest, indent=4, ensure_ascii=False)
    dst_file.write_text(content, "utf-8")
    existing_files.append(dst.lower())
    return dst


with contextlib.suppress(ModuleNotFoundError, FileNotFoundError):
    from dotenv import load_dotenv

    load_dotenv()

for dir_name in [*SYNC_DIR_NAMES, "temp"]:
    result_dir: Path = CURRENT_DIR / dir_name
    if result_dir.exists():
        rmtree(CURRENT_DIR / dir_name)


for repo_name in BUCKETS:
    repo_dir: Path = TEMP_DIR / repo_name.replace("/", "_")
    repo: Repo = Repo.clone_from(
        f"{GITHUB_URL + '/' if os.environ.get('MIRROR') else ''}https://github.com/{repo_name}",
        repo_dir,
        multi_options=["--filter=blob:none", "--no-checkout"],
    )
    repo.git.sparse_checkout("init", "--no-cone")
    repo.git.sparse_checkout("set", *SYNC_DIR_NAMES)
    repo.git.checkout("-b", "default", "origin/HEAD")

    for sync_dir_name in SYNC_DIR_NAMES:
        if not (repo_dir / sync_dir_name).exists():
            continue

        result_dir: Path = CURRENT_DIR / sync_dir_name
        copytree(
            repo_dir / sync_dir_name, result_dir, dirs_exist_ok=True, copy_function=copy
        )
