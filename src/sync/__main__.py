import contextlib
import json
import os
import re
from enum import IntEnum
from functools import partial
from json import JSONDecodeError
from pathlib import Path
from shutil import copy2, copytree, rmtree

from git import Repo

from sync.config import (
    BUCKETS,
    CURRENT_DIR,
    DEFAULT_RULES,
    GITHUB_RULES,
    GITHUB_URL,
    HIGH_QUALITY_BUCKETS,
    INVALID_GITHUB_URL,
    NODEJS_RULES,
    PHP_RULES,
    SOURCEFORGE_RULES,
    SYNC_DIR_NAMES,
    TEMP_DIR,
    Rules,
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
        if not s or s.strip() == "":
            return 0.0
        try:
            return float(s)
        except ValueError:
            return 0.0

    for i in range(count):
        old_num: int | float = (
            to_num(s=old_segments[i]) if i < len(old_segments) else 0.0
        )
        new_num: int | float = (
            to_num(s=new_segments[i]) if i < len(new_segments) else 0.0
        )

        if old_num > new_num:
            return SemverStatus.GREATER
        elif new_num > old_num:
            return SemverStatus.LESS
    return SemverStatus.EQUAL


# {file: {repo: "owner/repo", version: "x.y.z"# optional}}
existing_files: dict[str, dict[str, str]] = {}


def is_exists(dst: str) -> bool:
    return existing_files.get(dst.lower()) is not None


def copy(src: str, dst: str, *_, repo: str) -> str:
    src_file, dst_file = Path(src), Path(dst)
    version: str = "unknown"

    try:
        content: str = src_file.read_text("utf-8").replace("\r\n", "\n").strip()

        if src_file.suffix == ".json":
            content: str = json.dumps(json.loads(content), indent=4, ensure_ascii=False)

        if is_exists(src_file.name):
            info: dict[str, str] = existing_files[src_file.name.lower()]
            if info["repo"] in HIGH_QUALITY_BUCKETS:
                return dst
            elif src_file.suffix == ".json":
                version: str = json.loads(content)["version"]
                dst_version: str = info["version"]
                status: SemverStatus = semver_compare(dst_version, version)
                if status == SemverStatus.GREATER or status == SemverStatus.EQUAL:
                    return dst

        rules: Rules = DEFAULT_RULES
        if "github.com" in content or "githubusercontent.com" in content:
            for url in INVALID_GITHUB_URL:
                content: str = content.replace(url, GITHUB_URL)
            rules += GITHUB_RULES
        elif "sourceforge.net" in content:
            rules += SOURCEFORGE_RULES
        elif "nodejs" in src_file.name:
            rules += NODEJS_RULES
        elif "php" in src_file.name:
            rules += PHP_RULES

        for pattern, replace in rules:
            content: str = pattern.sub(replace, content)

        dst_file.write_text(content, "utf-8")
        existing_files[src_file.name.lower()] = {
            "repo": repo,
            "version": version,
        }
        return dst
    except (
        UnicodeDecodeError,
        JSONDecodeError,
    ):  # 如果是二进制文件或 JSON 解析失败,则直接复制
        return copy2(src, dst)


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
        multi_options=["--filter=blob:none", "--no-checkout", "--depth=1"],
    )
    repo.git.sparse_checkout("init", "--no-cone")
    repo.git.sparse_checkout("set", *SYNC_DIR_NAMES)
    repo.git.checkout("-b", "result", "origin/HEAD")

    for sync_dir_name in SYNC_DIR_NAMES:
        if not (repo_dir / sync_dir_name).exists():
            continue

        result_dir: Path = CURRENT_DIR / sync_dir_name
        copytree(
            repo_dir / sync_dir_name,
            result_dir,
            dirs_exist_ok=True,
            copy_function=partial(copy, repo=repo_name),
        )
