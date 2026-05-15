from _thread import lock
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from contextlib import suppress
from enum import IntEnum
from os import environ, process_cpu_count
from pathlib import Path
from shutil import copy2, rmtree
from threading import Lock
from typing import Any

from git import Repo
from orjson import (
    OPT_APPEND_NEWLINE,
    OPT_INDENT_2,
    OPT_NON_STR_KEYS,
    JSONDecodeError,
    JSONEncodeError,
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
    NODEJS_RULES,
    PHP_RULES,
    SOURCEFORGE_RULES,
    SYNC_DIR_NAMES,
    TEMP_DIR,
    VERSION_RULE,
    Rule,
)


class SemverStatus(IntEnum):
    GREATER = 1  # a > b
    EQUAL = 0  # a == b
    LESS = -1  # a < b


def semver_compare(old: str, new: str) -> SemverStatus:
    pattern, replace = VERSION_RULE
    old: str = pattern.sub(replace, str(old or "").replace("-", "."))
    new: str = pattern.sub(replace, str(new or "").replace("-", "."))

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


# {file: {repo: "owner/repo", version: "x.y.z" | "unknown"}}
existing_files: dict[str, dict[str, str]] = {}
existing_lock: lock = Lock()


def fix_depends(val: str | list[str]) -> Any:
    if isinstance(val, str) and "/" in val:
        return "main/" + val.split("/", 1)[1]
    if isinstance(val, list):
        return [
            "main/" + item.split("/", 1)[1] if "/" in item else item for item in val
        ]
    return val


def copy(args: tuple[Path, Path, str]) -> None:
    src, dst, repo = args
    version: str = "unknown"

    try:
        content: str = src.read_text("utf-8").replace("\r\n", "\n").strip()

        if src.parent.name == "bucket" and src.suffix == ".json":
            content_json: Any = loads(content)
            # 处理依赖
            if "depends" in content_json:
                raw_depends: list[str] | str = content_json["depends"]
                depends = (
                    [raw_depends] if isinstance(raw_depends, str) else list(raw_depends)
                )
                content_json["depends"] = [fix_depends(d) for d in depends]

            if "suggest" in content_json:
                suggest: dict[str, str | list[str]] | str = content_json["suggest"]
                if isinstance(suggest, dict):
                    content_json["suggest"] = {
                        k: fix_depends(v) for k, v in suggest.items()
                    }
                elif isinstance(suggest, str):
                    content_json["suggest"] = fix_depends(suggest)

            content: str = dumps(
                content_json,
                option=OPT_INDENT_2 | OPT_NON_STR_KEYS | OPT_APPEND_NEWLINE,
            ).decode()
            version: Any = (
                content_json.get("version", "unknown")
                if isinstance(content_json, dict)
                else "unknown"
            )
            if not isinstance(version, str):
                version = "unknown"
    except UnicodeDecodeError, JSONDecodeError, JSONEncodeError:
        with existing_lock:
            if existing_files.get(src.name.lower()) is not None:
                copy2(src, dst)
        return
    with existing_lock:
        info: dict[str, str] | None = existing_files.get(src.name.lower())
        if info is not None:
            if info["repo"] in HIGH_QUALITY_BUCKETS:
                return
            elif src.suffix == ".json":
                dst_version: str = info["version"]
                status: SemverStatus = semver_compare(dst_version, version)
                if status == SemverStatus.GREATER or status == SemverStatus.EQUAL:
                    return

    rules: list[Rule] = []
    rules += DEFAULT_RULES
    if "github.com" in content or "githubusercontent.com" in content:
        rules += GITHUB_RULES
    elif "sourceforge.net" in content:
        rules += SOURCEFORGE_RULES
    elif "nodejs" in src.name:
        rules += NODEJS_RULES
    elif "php" in src.name:
        rules += PHP_RULES

    for pattern, replace in rules:
        content: str = pattern.sub(replace, content)

    dst.write_text(content, encoding="utf-8")
    with existing_lock:
        existing_files[src.name.lower()] = {
            "repo": repo,
            "version": version,
        }
    return


def clone(repo_name: str, skip_clone: bool) -> list[tuple[Path, str]]:
    repo_dir: Path = TEMP_DIR / repo_name.replace("/", "_")
    if not repo_dir.exists() or not skip_clone:
        repo: Repo = Repo.clone_from(
            f"{GITHUB_URL + '/' if environ.get('MIRROR') else ''}https://github.com/{repo_name}",
            repo_dir,
            multi_options=["--filter=blob:none", "--no-checkout", "--depth=1"],
        )
        repo.git.sparse_checkout("init", "--no-cone")
        repo.git.sparse_checkout("set", *SYNC_DIR_NAMES)
        repo.git.checkout("-b", "result", "origin/HEAD")
    need_work_dirs: list[tuple[Path, str]] = []
    for sync_dir_name in SYNC_DIR_NAMES:
        if not (repo_dir / sync_dir_name).exists():
            continue
        need_work_dirs.append((repo_dir / sync_dir_name, repo_name))
    return need_work_dirs


def main() -> None:
    with ThreadPoolExecutor(max_workers=process_cpu_count()) as executor:
        skip_clone: bool = environ.get("SKIP_CLONE") is not None

        futures: list[Future[list[tuple[Path, str]]]] = []
        for repo_name in BUCKETS:
            futures.append(executor.submit(clone, repo_name, skip_clone))

        need_work_dirs: list[tuple[Path, str]] = []
        for future in futures:
            need_work_dirs += future.result()

        futures: list[Future[None]] = []
        for sync_dir, repo_name in need_work_dirs:
            result_dir: Path = CURRENT_DIR / sync_dir.name
            src_dir: Path = sync_dir

            for src_file in src_dir.rglob("*"):
                if not src_file.is_file():
                    continue
                dst_file: Path = result_dir / src_file.relative_to(src_dir)
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                futures.append(executor.submit(copy, (src_file, dst_file, repo_name)))
        for future in as_completed(futures):
            future.result()


if __name__ == "__main__":
    with suppress(ModuleNotFoundError, FileNotFoundError):
        from dotenv import load_dotenv

        load_dotenv()

    for dir_name in [*SYNC_DIR_NAMES, "temp"]:
        result_dir: Path = CURRENT_DIR / dir_name
        if result_dir.exists():
            if environ.get("SKIP_CLONE") is None:
                rmtree(result_dir)
            result_dir.mkdir(parents=True, exist_ok=True)
    main()
