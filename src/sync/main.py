import contextlib
import os
import subprocess
import threading
from _thread import lock
from concurrent.futures import ThreadPoolExecutor
from enum import IntEnum
from pathlib import Path
from re import Pattern
from shutil import copy2, rmtree

import re2
from orjson import (
    OPT_APPEND_NEWLINE,
    OPT_INDENT_2,
    OPT_NON_STR_KEYS,
    JSONDecodeError,
    dumps,
    loads,
)

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
    compile,
)


class SemverStatus(IntEnum):
    GREATER = 1  # a > b
    LESS = -1  # a < b
    EQUAL = 0  # a == b


version_pattern: Pattern = compile(r"[^\d.]")


def semver_compare(old: str, new: str) -> SemverStatus:
    old: str = re2.sub(version_pattern, "", str(old or "").replace("-", "."))
    new: str = re2.sub(version_pattern, "", str(new or "").replace("-", "."))

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
existing_lock: lock = threading.Lock()


def is_exists(dst: str) -> bool:
    with existing_lock:
        return existing_files.get(dst.lower()) is not None


def copy(src: str, dst: str, repo: str) -> None:
    src_file, dst_file = Path(src), Path(dst)
    version: str = "unknown"

    try:
        content: str = src_file.read_text().replace("\r\n", "\n").strip()

        if src_file.suffix == ".json":
            content: str = dumps(
                loads(content),
                option=OPT_INDENT_2 | OPT_NON_STR_KEYS | OPT_APPEND_NEWLINE,
            ).decode()
    except UnicodeDecodeError, JSONDecodeError:
        if not dst_file.exists():
            copy2(src, dst)
        return
    if is_exists(src_file.name):
        with existing_lock:
            info: dict[str, str] = existing_files[src_file.name.lower()]
        if info["repo"] in HIGH_QUALITY_BUCKETS:
            return
        elif src_file.suffix == ".json":
            version: str = loads(content)["version"]
            dst_version: str = info["version"]
            status: SemverStatus = semver_compare(dst_version, version)
            if status == SemverStatus.GREATER or status == SemverStatus.EQUAL:
                return

    rules: Rules = []
    rules += DEFAULT_RULES
    if "github.com" in content or "githubusercontent.com" in content:
        for url in INVALID_GITHUB_URL:
            rules.append((compile(url), GITHUB_URL))
        rules += GITHUB_RULES
    elif "sourceforge.net" in content:
        rules += SOURCEFORGE_RULES
    elif "nodejs" in src_file.name:
        rules += NODEJS_RULES
    elif "php" in src_file.name:
        rules += PHP_RULES

    for pattern, replace in rules:
        content: str = re2.sub(pattern, replace, content)

    dst_file.write_text(content)
    with existing_lock:
        existing_files[src_file.name.lower()] = {
            "repo": repo,
            "version": version,
        }
    return


def copy_wrapper(args):
    return copy(*args)


def main() -> None:
    for repo_name in BUCKETS:
        repo_dir: Path = TEMP_DIR / repo_name.replace("/", "_")
        subprocess.check_call(
            [
                "git",
                "clone",
                "--filter=blob:none",
                "--no-checkout",
                "--depth=1",
                f"{GITHUB_URL + '/' if os.environ.get('MIRROR') else ''}https://github.com/{repo_name}",
            ],
            cwd=TEMP_DIR,
        )
        subprocess.check_call(
            [
                "git",
                "sparse_checkout",
                "init",
                "--no-cone",
            ],
            cwd=repo_dir,
        )
        subprocess.check_call(
            ["git", "sparse_checkout", "set", *SYNC_DIR_NAMES],
            cwd=repo_dir,
        )
        subprocess.check_call(
            ["git", "checkout", "-b", "result", "origin/HEAD"],
            cwd=repo_dir,
        )

        for sync_dir_name in SYNC_DIR_NAMES:
            if not (repo_dir / sync_dir_name).exists():
                continue

            result_dir: Path = CURRENT_DIR / sync_dir_name
            src_dir: Path = repo_dir / sync_dir_name

            # 🔥 收集所有文件任务
            tasks = []
            for src_file in src_dir.rglob("*"):
                if not src_file.is_file():
                    continue
                dst: Path = result_dir / src_file.relative_to(src_dir)
                dst.parent.mkdir(parents=True, exist_ok=True)
                tasks.append((str(src_file), str(dst), repo_name))

            with ThreadPoolExecutor(max_workers=os.process_cpu_count()) as executor:
                executor.map(copy_wrapper, tasks)
            # copytree(
            #     repo_dir / sync_dir_name,
            #     result_dir,
            #     dirs_exist_ok=True,
            #     copy_function=partial(copy, repo=repo_name),
            # )


if __name__ == "__main__":
    with contextlib.suppress(ModuleNotFoundError, FileNotFoundError):
        from dotenv import load_dotenv

        load_dotenv()

    for dir_name in [*SYNC_DIR_NAMES, "temp"]:
        result_dir: Path = CURRENT_DIR / dir_name
        if result_dir.exists():
            rmtree(CURRENT_DIR / dir_name)
    main()
