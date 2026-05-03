#!/usr/bin/env python3
"""Patch Hermes Gateway Telegram tool-progress into one transient rolling bubble.

Desired behavior:
- Telegram shows one editable tool-progress bubble during a turn.
- That bubble keeps only the most recent N lines (default: 3), not a long log.
- When the turn finishes, the runner gracefully drains progress and calls
  adapter.delete_message(...) best-effort before returning the final reply.
- Final assistant replies are preserved.

This script reads/writes Hermes source files and config only. It does not read,
print, or require API keys, bot tokens, cookies, OAuth credentials, or secrets.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None


def default_hermes_repo() -> Path:
    env = os.environ.get("HERMES_AGENT_REPO")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".hermes" / "hermes-agent"


def default_config(profile: str | None) -> Path:
    env = os.environ.get("HERMES_CONFIG")
    if env:
        return Path(env).expanduser()
    home = Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
    if profile:
        prof = home / "profiles" / profile / "config.yaml"
        if prof.exists():
            return prof
    return home / "config.yaml"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def replace_once(path: Path, old: str, new: str, label: str) -> bool:
    text = read_text(path)
    if new in text:
        print(f"✓ {label}: already present")
        return False
    if old not in text:
        print(f"! {label}: anchor not found; skipped")
        return False
    write_text(path, text.replace(old, new, 1))
    print(f"+ {label}: patched {path}")
    return True


def insert_before(path: Path, marker: str, insertion: str, present: str, label: str) -> bool:
    text = read_text(path)
    if present in text:
        print(f"✓ {label}: already present")
        return False
    if marker not in text:
        print(f"! {label}: marker not found; skipped")
        return False
    write_text(path, text.replace(marker, insertion + marker, 1))
    print(f"+ {label}: patched {path}")
    return True


def patch_display_config(display: Path) -> bool:
    changed = False
    if not display.exists():
        print(f"! display_config missing: {display}")
        return False

    changed |= replace_once(
        display,
        '            "append_lines": "append",\n            "log": "append",\n',
        '            "append_lines": "append",\n            "log": "append",\n'
        '            "recent": "recent",\n'
        '            "rolling": "recent",\n'
        '            "rolling_log": "recent",\n'
        '            "tail": "recent",\n'
        '            "tail_lines": "recent",\n'
        '            "last_lines": "recent",\n'
        '            "last_3": "recent",\n'
        '            "three_lines": "recent",\n',
        "display_config recent-style aliases",
    )

    changed |= replace_once(
        display,
        '    "tool_progress": "all",\n    "show_reasoning": False,\n',
        '    "tool_progress": "all",\n'
        '    "tool_progress_cleanup": "keep",\n'
        '    "tool_progress_message_style": "append",\n'
        '    "tool_progress_max_lines": 0,\n'
        '    "show_reasoning": False,\n',
        "display_config cleanup/style defaults",
    )

    if 'if setting == "tool_progress_cleanup"' in read_text(display):
        print("✓ display_config cleanup normalizer fallback: already present")
    else:
        changed |= replace_once(
            display,
            '    if setting in ("show_reasoning", "streaming"):\n',
            '    if setting == "tool_progress_cleanup":\n'
            '        if value is True:\n'
            '            return "delete_on_complete"\n'
            '        if value is False or value is None:\n'
            '            return "keep"\n'
            '        value_s = str(value).strip().lower().replace("-", "_")\n'
            '        aliases = {"delete": "delete_on_complete", "delete_on_done": "delete_on_complete", "delete_after": "delete_on_complete", "ephemeral": "delete_on_complete", "transient": "delete_on_complete", "off": "keep", "false": "keep", "none": "keep"}\n'
            '        return aliases.get(value_s, value_s)\n'
            '    if setting in ("show_reasoning", "streaming"):\n',
            "display_config cleanup normalizer fallback",
        )
    return changed


def patch_run_py(run_py: Path) -> bool:
    changed = False
    if not run_py.exists():
        print(f"! run.py missing: {run_py}")
        return False

    changed |= replace_once(
        run_py,
        '        if progress_message_style in {"last", "replace", "replace_last", "single", "single_line", "one_line"}:\n'
        '            progress_message_style = "latest"\n'
        '        if progress_message_style not in {"append", "latest"}:\n'
        '            progress_message_style = "append"\n',
        '        if progress_message_style in {"last", "replace", "replace_last", "single", "single_line", "one_line"}:\n'
        '            progress_message_style = "latest"\n'
        '        if progress_message_style in {"recent", "rolling", "rolling_log", "tail", "tail_lines", "last_lines", "last_3", "three_lines"}:\n'
        '            progress_message_style = "recent"\n'
        '        if progress_message_style not in {"append", "latest", "recent"}:\n'
        '            progress_message_style = "append"\n'
        '        try:\n'
        '            progress_max_lines = int(\n'
        '                resolve_display_setting(\n'
        '                    user_config,\n'
        '                    platform_key,\n'
        '                    "tool_progress_max_lines",\n'
        '                    3 if progress_message_style == "recent" else 0,\n'
        '                ) or 0\n'
        '            )\n'
        '        except (TypeError, ValueError):\n'
        '            progress_max_lines = 3 if progress_message_style == "recent" else 0\n'
        '        if progress_message_style == "latest":\n'
        '            progress_max_lines = 1\n'
        '        elif progress_message_style == "recent" and progress_max_lines <= 0:\n'
        '            progress_max_lines = 3\n',
        "run.py recent-style resolver",
    )

    changed |= replace_once(
        run_py,
        '            progress_msg_id = None   # ID of the progress message to edit\n'
        '            can_edit = True          # False once an edit fails (platform doesn\'t support it)\n',
        '            progress_msg_id = None   # ID of the progress message to edit\n'
        '            progress_msg_ids = []    # All transient progress messages sent in this turn\n'
        '            can_edit = True          # False once an edit fails (platform doesn\'t support it)\n',
        "run.py progress id tracking",
    )

    if "Progress cleanup deleted transient message" in read_text(run_py):
        print("✓ run.py cleanup diagnostic logging: already present")
    else:
        changed |= replace_once(
            run_py,
            '                    try:\n'
            '                        await adapter.delete_message(source.chat_id, _mid)\n'
            '                    except Exception as _delete_err:\n'
            '                        logger.debug(\n'
            '                            "Progress cleanup delete failed for message %s: %s",\n'
            '                            _mid,\n'
            '                            _delete_err,\n'
            '                        )\n',
            '                    try:\n'
            '                        _deleted = await adapter.delete_message(source.chat_id, _mid)\n'
            '                        if _deleted:\n'
            '                            logger.info("Progress cleanup deleted transient message chat=%s message=%s", source.chat_id, _mid)\n'
            '                        else:\n'
            '                            logger.warning("Progress cleanup delete returned false chat=%s message=%s", source.chat_id, _mid)\n'
            '                    except Exception as _delete_err:\n'
            '                        logger.warning("Progress cleanup delete failed chat=%s message=%s error=%s", source.chat_id, _mid, _delete_err)\n',
            "run.py cleanup diagnostic logging",
        )

    changed |= insert_before(
        run_py,
        '                    # Handle dedup messages: update last line with repeat counter\n',
        '                    # Handle completion sentinel from the outer runner. Prefer a\n'
        '                    # graceful drain+delete over task.cancel(); Telegram API\n'
        '                    # calls made from a cancelled task can be skipped, leaving\n'
        '                    # the transient progress bubble behind.\n'
        '                    if isinstance(raw, tuple) and len(raw) >= 1 and raw[0] == "__complete__":\n'
        '                        if can_edit and progress_lines and progress_msg_id:\n'
        '                            try:\n'
        '                                await adapter.edit_message(\n'
        '                                    chat_id=source.chat_id,\n'
        '                                    message_id=progress_msg_id,\n'
        '                                    content="\\n".join(progress_lines),\n'
        '                                )\n'
        '                            except Exception:\n'
        '                                pass\n'
        '                        await _cleanup_progress_messages()\n'
        '                        return\n\n',
        'raw[0] == "__complete__"',
        "run.py graceful progress completion sentinel",
    )

    changed |= replace_once(
        run_py,
        '            # Stop progress sender, interrupt monitor, and notification task\n'
        '            if progress_task:\n'
        '                progress_task.cancel()\n'
        '            interrupt_monitor.cancel()\n',
        '            # Stop progress sender, interrupt monitor, and notification task.\n'
        '            # For progress, prefer a graceful completion sentinel over immediate\n'
        '            # cancellation: cancellation can abort Telegram delete_message and\n'
        '            # leave the transient tool bubble visible after the final answer.\n'
        '            if progress_task:\n'
        '                try:\n'
        '                    if progress_queue is not None:\n'
        '                        progress_queue.put(("__complete__",))\n'
        '                except Exception:\n'
        '                    progress_task.cancel()\n'
        '            interrupt_monitor.cancel()\n',
        "run.py graceful progress shutdown",
    )

    changed |= replace_once(
        run_py,
        '            # Wait for cancelled tasks\n'
        '            for task in [progress_task, interrupt_monitor, tracking_task, _notify_task]:\n'
        '                if task:\n'
        '                    try:\n'
        '                        await task\n'
        '                    except asyncio.CancelledError:\n'
        '                        pass\n',
        '            # Wait for progress cleanup and cancelled tasks. Progress gets a\n'
        '            # short graceful window to drain/delete; if it hangs, fall back to\n'
        '            # cancellation so the final response is not blocked indefinitely.\n'
        '            if progress_task:\n'
        '                try:\n'
        '                    await asyncio.wait_for(progress_task, timeout=4.0)\n'
        '                except asyncio.TimeoutError:\n'
        '                    progress_task.cancel()\n'
        '                    try:\n'
        '                        await progress_task\n'
        '                    except asyncio.CancelledError:\n'
        '                        pass\n'
        '                except asyncio.CancelledError:\n'
        '                    pass\n\n'
        '            for task in [interrupt_monitor, tracking_task, _notify_task]:\n'
        '                if task:\n'
        '                    try:\n'
        '                        await task\n'
        '                    except asyncio.CancelledError:\n'
        '                        pass\n',
        "run.py wait for progress cleanup",
    )

    text = read_text(run_py)
    if 'progress_message_style in {"latest", "recent"}' in text:
        print("✓ run.py latest/recent reset handling: already present")
    else:
        print("! run.py latest/recent reset handling: not detected; manual patch may be needed")

    if "progress_max_lines > 0 and len(progress_lines) > progress_max_lines" in text:
        print("✓ run.py progress max-line trimming: already present")
    else:
        print("! run.py progress max-line trimming: not detected; manual patch may be needed")

    return changed


def enable_config(config: Path, *, max_lines: int, no_config: bool) -> bool:
    if no_config:
        print("- config edit skipped by --no-config")
        return False
    if not config.exists():
        print(f"! config not found; skipped: {config}")
        return False
    if yaml is None:
        raise RuntimeError("PyYAML is required to edit config.yaml. Install it or run inside Hermes' venv.")

    data: dict[str, Any] = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
    display = data.setdefault("display", {})
    agent = data.setdefault("agent", {})
    platforms = display.setdefault("platforms", {})
    telegram = platforms.setdefault("telegram", {})
    before = (
        display.get("interim_assistant_messages"),
        agent.get("gateway_notify_interval"),
        telegram.get("tool_progress_cleanup"),
        telegram.get("tool_progress_message_style"),
        telegram.get("tool_progress_max_lines"),
    )
    display["interim_assistant_messages"] = False
    agent["gateway_notify_interval"] = 0
    telegram["tool_progress_cleanup"] = "delete_on_complete"
    telegram["tool_progress_message_style"] = "recent"
    telegram["tool_progress_max_lines"] = max_lines
    after = (False, 0, "delete_on_complete", "recent", max_lines)
    if before == after:
        print(f"✓ config: already enabled in {config}")
        return False
    config.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"+ config: enabled Telegram cleanup/recent({max_lines}) progress in {config}")
    return True


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Patch Hermes Telegram tool-progress into a transient rolling progress bubble."
    )
    parser.add_argument("--repo", type=Path, default=default_hermes_repo(), help="Hermes source checkout. Default: $HERMES_AGENT_REPO or ~/.hermes/hermes-agent")
    parser.add_argument("--profile", default=os.environ.get("HERMES_PROFILE"), help="Hermes profile name used to locate config.yaml when --config is omitted")
    parser.add_argument("--config", type=Path, default=None, help="Hermes config.yaml path. Default: $HERMES_CONFIG or profile/default config")
    parser.add_argument("--max-lines", type=int, default=3, help="Number of recent progress lines to keep in the single bubble. Default: 3")
    parser.add_argument("--no-config", action="store_true", help="Patch source files only; do not edit config.yaml")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    repo = args.repo.expanduser().resolve()
    config = (args.config.expanduser() if args.config else default_config(args.profile)).resolve()
    run_py = repo / "gateway" / "run.py"
    display = repo / "gateway" / "display_config.py"

    if args.max_lines < 1:
        print("ERROR: --max-lines must be >= 1", file=sys.stderr)
        return 2
    if not repo.exists():
        print(f"ERROR: repo not found: {repo}", file=sys.stderr)
        return 2

    changed = False
    changed |= patch_display_config(display)
    changed |= patch_run_py(run_py)
    changed |= enable_config(config, max_lines=args.max_lines, no_config=args.no_config)

    print("\nSummary:")
    print(f"- repo: {repo}")
    print(f"- config: {config if not args.no_config else 'skipped'}")
    print(f"- source_changed_or_config_changed: {changed}")
    if changed:
        print("- restart recommended if Hermes Gateway is currently running")
    else:
        print("- no restart needed for source/config; already in desired state")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
