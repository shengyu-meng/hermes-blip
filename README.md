# Hermes Blip

> Make Hermes Telegram Gateway tool-progress messages transient: one editable rolling progress bubble during execution, up to the latest 3 lines, automatically deleted after the final reply.

中文说明 / Chinese README: [README.zh.md](README.zh.md)

## What problem does it solve?

When Hermes Agent runs tools through Telegram Gateway, it may send progress messages such as `terminal`, `read_file`, and `search_files` into the chat. This is transparent, but it can pollute chat history.

This patch changes tool progress into:

- **one editable Telegram progress bubble**;
- at most the latest N operation lines, default `3`;
- subsequent tool calls edit the same message;
- when the turn finishes, Hermes calls Telegram `deleteMessage` to remove the transient progress bubble;
- the final assistant reply is preserved.

In short: **visible while working, clean after completion.**

## Current scope

- Platform: Telegram Gateway
- Behavior: single rolling bubble + latest 3 lines + delete on completion
- Mechanism: local Hermes source patch + profile config
- Replayable: run the script again after Hermes upgrades
- Feishu/Lark: conceptually reusable, but requires `delete_message(...)` support in the Feishu adapter

## When to use

Use this if:

- you run Hermes Agent via Telegram Gateway;
- you want live tool progress;
- you do not want every tool call to stay in Telegram history forever;
- you accept this as a local source patch that may need to be reapplied after upgrades.

Do not use this if:

- you want no progress messages at all — disabling `display.tool_progress` is simpler;
- you need an official stable plugin API — this is a patch, not an upstream Hermes feature;
- you are not using Telegram.

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/shengyu-meng/hermes-blip.git
cd hermes-blip
```


### 2. Run the patch script

Default Hermes source location:

```bash
python3 scripts/apply-transient-progress-cleanup.py
```

Profile example:

```bash
python3 scripts/apply-transient-progress-cleanup.py --profile myprofile
```

Explicit source and config paths:

```bash
python3 scripts/apply-transient-progress-cleanup.py \
  --repo ~/.hermes/hermes-agent \
  --config ~/.hermes/profiles/myprofile/config.yaml \
  --max-lines 3
```

Patch source only, without editing config:

```bash
python3 scripts/apply-transient-progress-cleanup.py --no-config
```

### 3. Restart Hermes Gateway

macOS launchd example:

```bash
launchctl stop ai.hermes.gateway
sleep 2
launchctl start ai.hermes.gateway
```

Profile-specific label example:

```bash
launchctl stop ai.hermes.gateway-myprofile
sleep 2
launchctl start ai.hermes.gateway-myprofile
```

Depending on your installation, this may also work:

```bash
hermes gateway restart
```

## Config written by the script

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

Meaning:

- `tool_progress_cleanup: delete_on_complete`: delete the transient progress message after the final reply;
- `tool_progress_message_style: recent`: use one rolling bubble rather than appending new messages;
- `tool_progress_max_lines: 3`: keep at most 3 lines;
- `interim_assistant_messages: false`: reduce natural-language interim messages;
- `gateway_notify_interval: 0`: disable periodic `Still working...` notifications.

## Install as a Hermes skill

This repository includes a Hermes skill:

```text
skills/hermes-blip/SKILL.md
```

Copy it into your Hermes skill directory:

```bash
mkdir -p ~/.hermes/skills/devops/hermes-blip
cp -R skills/hermes-blip/* ~/.hermes/skills/devops/hermes-blip/
```

Then ask Hermes:

```text
Run hermes-blip and restore Telegram transient tool progress cleanup.
```

## Verification

### Check source markers

```bash
cd ~/.hermes/hermes-agent
rg "tool_progress_cleanup|tool_progress_message_style|tool_progress_max_lines|__complete__|_cleanup_progress_messages" gateway/run.py gateway/display_config.py
```

### Check config

```bash
python3 - <<'PY'
import pathlib, yaml
cfg = yaml.safe_load(pathlib.Path('~/.hermes/config.yaml').expanduser().read_text())
print(cfg.get('display', {}).get('platforms', {}).get('telegram', {}))
PY
```

Profile example:

```bash
python3 - <<'PY'
import pathlib, yaml
cfg = yaml.safe_load(pathlib.Path('~/.hermes/profiles/myprofile/config.yaml').expanduser().read_text())
print(cfg.get('display', {}).get('platforms', {}).get('telegram', {}))
PY
```

### Run Hermes tests if available

```bash
cd ~/.hermes/hermes-agent
python -m pytest tests/gateway/test_display_config.py tests/gateway/test_run_progress_topics.py -q
```

## Security

This repository intentionally does not include:

- bot tokens;
- API keys;
- OAuth tokens;
- cookies;
- local user paths;
- private profile config.

The script does not read or print `.env`, tokens, cookies, or auth files. It only reads/writes:

- `gateway/run.py`;
- `gateway/display_config.py`;
- the explicit `config.yaml` you point it at.

## Limitations

- This patch depends on the current Hermes Gateway source layout. If upstream changes significantly, anchors may fail and manual adaptation may be needed.
- Deletion is best-effort. Telegram API failures, old messages, or permission issues can leave the progress bubble visible.
- It only targets gateway tool-progress bubbles. It does not delete final replies, approval prompts, media messages, or natural-language interim assistant comments.
- Feishu/Lark does not get this behavior automatically; the platform adapter needs `delete_message(...)` support.

## License

MIT
