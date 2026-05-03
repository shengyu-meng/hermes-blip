---
name: hermes-transient-progress-cleanup
description: Use when Hermes Telegram Gateway tool-progress messages should be visible during execution as one rolling transient bubble, then deleted after the final reply.
version: 1.0.0
author: Hermes Agent community
license: MIT
metadata:
  hermes:
    tags: [hermes, gateway, telegram, tool-progress, cleanup, transient-messages]
    related_skills: [hermes-agent]
---

# Hermes Transient Progress Cleanup

## Overview

This skill restores a Telegram Gateway behavior for Hermes Agent: tool progress stays visible while the agent is running, but does not remain as chat-history clutter after the final answer.

The desired behavior is:

- one editable Telegram progress bubble during a turn;
- at most the latest three operation lines by default;
- progress updates edit the same bubble instead of sending many messages;
- after the final assistant reply is ready, Hermes best-effort deletes the transient progress bubble;
- final replies are preserved.

This is a local Hermes source patch plus config change. It is meant to be replayable after Hermes upgrades.

## When to Use

Use this when:

- the user runs Hermes through Telegram Gateway;
- `terminal`, `read_file`, `search_files`, or other tool-progress messages are cluttering Telegram;
- the user wants live execution visibility but clean chat history;
- Hermes upgrades overwrote the previous local patch.

Do not use this when:

- the user wants no tool progress at all — use `display.tool_progress: none/off` instead;
- the platform is not Telegram, unless that platform adapter implements `delete_message(...)`;
- the user expects this to delete final replies, media, approval prompts, or natural-language interim commentary.

## Apply the Patch

From this skill directory:

```bash
python scripts/apply-transient-progress-cleanup.py --profile <profile-name>
```

Or explicitly:

```bash
python scripts/apply-transient-progress-cleanup.py   --repo ~/.hermes/hermes-agent   --config ~/.hermes/profiles/<profile-name>/config.yaml   --max-lines 3
```

The script is idempotent. If the source/config already has the patch, it prints `already present` and leaves files unchanged.

## Config Written

```yaml
display:
  tool_progress: all
  interim_assistant_messages: false
  platforms:
    telegram:
      tool_progress_cleanup: delete_on_complete
      tool_progress_message_style: recent
      tool_progress_max_lines: 3
agent:
  gateway_notify_interval: 0
```

## Restart Gateway

After source or config changes, restart the Hermes Gateway using the user's installation method, for example:

```bash
hermes gateway restart
```

On macOS launchd installs, the label may be profile-specific:

```bash
launchctl stop ai.hermes.gateway-<profile-name>
sleep 2
launchctl start ai.hermes.gateway-<profile-name>
```

## Verify

Check markers:

```bash
cd ~/.hermes/hermes-agent
rg "tool_progress_cleanup|tool_progress_message_style|tool_progress_max_lines|__complete__|_cleanup_progress_messages" gateway/run.py gateway/display_config.py
```

Check config:

```bash
python - <<'PY'
import pathlib, yaml
cfg = yaml.safe_load(pathlib.Path('~/.hermes/profiles/<profile-name>/config.yaml').expanduser().read_text())
print(cfg.get('display', {}).get('platforms', {}).get('telegram', {}))
PY
```

If the Hermes checkout contains matching tests:

```bash
cd ~/.hermes/hermes-agent
python -m pytest tests/gateway/test_display_config.py tests/gateway/test_run_progress_topics.py -q
```

## Troubleshooting

1. **Progress bubble still remains after final reply**
   - Verify the Telegram bot can delete its own messages.
   - Check gateway logs for `Progress cleanup delete returned false` or `Progress cleanup delete failed`.
   - Ensure the gateway was restarted after patching.

2. **Many progress bubbles are still sent**
   - Confirm `tool_progress_message_style: recent`.
   - Confirm `tool_progress_max_lines` is positive.
   - Confirm `edit_message` works for Telegram in the Hermes adapter.

3. **Still seeing `Still working...` messages**
   - Confirm `agent.gateway_notify_interval: 0`.
   - Those periodic notifications are separate from tool-progress cleanup.

4. **Natural-language interim commentary remains**
   - Confirm `display.interim_assistant_messages: false`.
   - This patch targets tool-progress bubbles, not arbitrary assistant text messages.

## Platform Boundary

The cleanup core is platform-generic only if the platform adapter supports `delete_message(...)`.

- Telegram: supported by the Bot API and this patch.
- Feishu/Lark: requires adapter-level delete/recall support first.
- Other platforms: must be evaluated per adapter.

## Security

The script does not read or print API keys, bot tokens, OAuth tokens, cookies, `.env`, or auth files. It only modifies Hermes source files and the selected `config.yaml`.
