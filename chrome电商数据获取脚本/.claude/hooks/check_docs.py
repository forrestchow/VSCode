#!/usr/bin/env python3
"""文档同步 Hook（最小版本）。

PostToolUse：记录本次会话中 Edit / Write / MultiEdit 改过的文件。
Stop：做机械检查，缺文档时 block 一次：
  - endpoints.json 变了 → PLAN.md 必须也变
  - api.py / collect.py 变了 → SPEC.md 必须也变
  - platforms/ 下新增 / 删除 / 重命名文件 → STRUCTURE.md 必须也变

它只检查文件路径和 git status，不判断「底层逻辑是否真的变了」；
语义判断仍然交给模型和 CLAUDE.md。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = Path(tempfile.gettempdir()) / "claude_doc_sync"


def read_payload() -> dict:
    # Hook JSON is UTF-8; Windows 控制台默认可能是 GBK，必须按字节读再解码。
    raw = sys.stdin.buffer.read().decode("utf-8", "replace")
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def safe_session_id(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in value)
    return cleaned or "default"


def state_path(session_id: str) -> Path:
    return STATE_DIR / f"{safe_session_id(session_id)}.json"


def load_state(session_id: str) -> dict:
    path = state_path(session_id)
    if not path.exists():
        return {"touched": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"touched": []}


def save_state(session_id: str, state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state_path(session_id).write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def clear_state(session_id: str) -> None:
    try:
        state_path(session_id).unlink()
    except OSError:
        pass


def normalize_path(value: str, cwd: str) -> Path | None:
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = Path(cwd) / path
    try:
        path = path.resolve()
        path.relative_to(PROJECT_ROOT)
    except (OSError, ValueError):
        return None
    return path


def safe_rel(path: Path) -> str | None:
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return None


def git_status(rel_path: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(PROJECT_ROOT), "status", "--porcelain", "--", rel_path],
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def is_structure_change(rel_path: str, new_paths: set[str]) -> bool:
    """platforms/ 下的新增、删除、重命名才算结构变化；普通修改不算。

    `new_paths` 是 PostToolUse 时观察到的新文件（git status 为 `??`）。
    不把单独的 `A` 当成结构变化，避免把「重构时已 staged 的 A + 本次 M」
    误判为本次新增。
    """
    if not rel_path.startswith("platforms/"):
        return False
    if rel_path in new_paths:
        return True
    status = git_status(rel_path)
    if not status:
        # 没有状态通常是「已跟踪且无变化」；不要误报结构变化。
        return False
    for line in status.splitlines():
        code = line[:2]
        if any(ch in code for ch in ("D", "R", "?")):
            return True
    return False


def handle_post_tool_use(payload: dict) -> int:
    tool = payload.get("tool_name") or ""
    if tool not in {"Edit", "Write", "MultiEdit"}:
        return 0
    tool_input = payload.get("tool_input") or {}
    path = normalize_path(
        tool_input.get("file_path") or "",
        payload.get("cwd") or str(PROJECT_ROOT),
    )
    if path is None:
        return 0

    session_id = payload.get("session_id") or "default"
    state = load_state(session_id)
    touched = set(state.get("touched") or [])
    touched.add(str(path))
    state["touched"] = sorted(touched)

    rel_path = safe_rel(path)
    if rel_path:
        new_paths = set(state.get("new") or [])
        status = git_status(rel_path)
        if "?" in status[:2]:
            new_paths.add(rel_path)
            state["new"] = sorted(new_paths)

    save_state(session_id, state)
    return 0


def handle_stop(payload: dict) -> int:
    session_id = payload.get("session_id") or "default"
    state = load_state(session_id)
    touched = [Path(item) for item in state.get("touched") or []]
    touched_rel = {rel for path in touched if (rel := safe_rel(path))}
    new_paths = set(state.get("new") or [])

    missing: list[str] = []

    if any(rel.endswith("endpoints.json") for rel in touched_rel):
        if "PLAN.md" not in touched_rel:
            missing.append("改了 endpoints.json，但没有更新 PLAN.md")

    if any(rel.endswith(("api.py", "collect.py")) for rel in touched_rel):
        if "SPEC.md" not in touched_rel:
            missing.append("改了 api.py / collect.py，但没有 review / 更新 SPEC.md")

    structure = sorted(
        rel for rel in touched_rel if is_structure_change(rel, new_paths)
    )
    if structure and "STRUCTURE.md" not in touched_rel:
        missing.append(
            "platforms/ 下新增 / 删除 / 重命名了文件，但没有更新 STRUCTURE.md："
            + "、".join(structure)
        )

    if missing:
        if payload.get("stop_hook_active"):
            # 已经 block 过一次，避免无限循环：放行并提示。
            print(
                json.dumps(
                    {
                        "systemMessage": "文档同步检查仍有未处理项，本次已放行：\n"
                        + "\n".join(missing)
                    },
                    ensure_ascii=False,
                )
            )
        else:
            print(
                json.dumps(
                    {
                        "decision": "block",
                        "reason": "文档同步检查未通过：\n" + "\n".join(missing),
                    },
                    ensure_ascii=False,
                )
            )
    clear_state(session_id)
    return 0


def main() -> int:
    event = None
    for index, arg in enumerate(sys.argv):
        if arg == "--event" and index + 1 < len(sys.argv):
            event = sys.argv[index + 1]
            break

    payload = read_payload()
    if event == "post-tool-use":
        return handle_post_tool_use(payload)
    if event == "stop":
        return handle_stop(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
