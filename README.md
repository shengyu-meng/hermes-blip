# Hermes Transient Progress Cleanup

> 让 Hermes Telegram Gateway 的工具执行过程只显示为一个临时进度气泡：执行中动态刷新最近 3 行，任务完成后自动撤回；最终回复保留。

English version: [README.en.md](README.en.md)

## 它解决什么问题？

Hermes Agent 在 Telegram Gateway 中执行工具时，可能会把 `terminal`、`read_file`、`search_files` 等过程信息发到聊天里。这样虽然透明，但会污染聊天记录。

这个补丁把过程信息变成：

- **一个可编辑的 Telegram 进度气泡**；
- 气泡中最多显示最近 N 行操作，默认 `3` 行；
- 新的工具调用会动态刷新同一条消息；
- 任务完成后，自动调用 Telegram `deleteMessage` 删除这条临时进度气泡；
- 最终 assistant 回复不受影响，仍然保留。

一句话：**看得见过程，但不留下过程垃圾。**

## 当前状态

- 平台：Telegram Gateway
- 行为：单进度气泡 + 最近 3 行 + 完成后删除
- 方式：Hermes 本地源码补丁 + profile config
- 可重放：升级 Hermes 后可重新运行脚本恢复补丁
- Feishu/Lark：思路可复用，但需要 Feishu adapter 实现 `delete_message(...)`，详见 skill notes

## 适用场景

适合你如果：

- 使用 Hermes Agent 的 Telegram Gateway；
- 希望运行时看到工具进度；
- 不希望每个工具调用都永久留在 Telegram 聊天记录里；
- 能接受这是一个本地源码补丁，Hermes 升级后需要重新应用。

不适合你如果：

- 你完全不想看到工具进度——那直接关闭 `display.tool_progress` 更简单；
- 你需要官方稳定 API 级插件——这个仓库是补丁，不是 Hermes upstream 功能；
- 你使用的不是 Telegram 平台。

## 安装

### 1. 克隆仓库

```bash
git clone https://github.com/YOUR_USERNAME/hermes-transient-progress-cleanup.git
cd hermes-transient-progress-cleanup
```

把 `YOUR_USERNAME` 换成实际仓库 owner。

### 2. 运行补丁脚本

如果你的 Hermes 源码在默认位置：

```bash
python3 scripts/apply-transient-progress-cleanup.py
```

常见 profile 用法：

```bash
python3 scripts/apply-transient-progress-cleanup.py --profile myprofile
```

显式指定 Hermes 源码和配置：

```bash
python3 scripts/apply-transient-progress-cleanup.py \
  --repo ~/.hermes/hermes-agent \
  --config ~/.hermes/profiles/myprofile/config.yaml \
  --max-lines 3
```

只补源码、不改配置：

```bash
python3 scripts/apply-transient-progress-cleanup.py --no-config
```

### 3. 重启 Hermes Gateway

macOS launchd 示例：

```bash
launchctl stop ai.hermes.gateway
sleep 2
launchctl start ai.hermes.gateway
```

如果你使用 profile-specific label，例如：

```bash
launchctl stop ai.hermes.gateway-myprofile
sleep 2
launchctl start ai.hermes.gateway-myprofile
```

也可以使用 Hermes 自带命令，视你的安装方式而定：

```bash
hermes gateway restart
```

## 需要的配置

脚本会尝试写入以下配置：

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

字段含义：

- `tool_progress_cleanup: delete_on_complete`：最终回复完成后删除临时进度消息；
- `tool_progress_message_style: recent`：用一个气泡显示最近几行，而不是不断追加新消息；
- `tool_progress_max_lines: 3`：最多显示 3 行；
- `interim_assistant_messages: false`：减少自然语言中间态消息；
- `gateway_notify_interval: 0`：关闭周期性 `Still working...` 之类的提醒。

## 安装为 Hermes skill

这个仓库包含一个 Hermes skill：

```text
skills/hermes-transient-progress-cleanup/SKILL.md
```

复制到你的 Hermes skill 目录：

```bash
mkdir -p ~/.hermes/skills/devops/hermes-transient-progress-cleanup
cp -R skills/hermes-transient-progress-cleanup/* ~/.hermes/skills/devops/hermes-transient-progress-cleanup/
```

之后你可以在 Hermes 里让 agent 执行：

```text
运行 hermes-transient-progress-cleanup，恢复 Telegram 过程消息完成后撤回功能。
```

## 验证

### 检查补丁标记

```bash
cd ~/.hermes/hermes-agent
rg "tool_progress_cleanup|tool_progress_message_style|tool_progress_max_lines|__complete__|_cleanup_progress_messages" gateway/run.py gateway/display_config.py
```

### 检查配置

```bash
python3 - <<'PY'
import pathlib, yaml
cfg = yaml.safe_load(pathlib.Path('~/.hermes/config.yaml').expanduser().read_text())
print(cfg.get('display', {}).get('platforms', {}).get('telegram', {}))
PY
```

如果你用 profile：

```bash
python3 - <<'PY'
import pathlib, yaml
cfg = yaml.safe_load(pathlib.Path('~/.hermes/profiles/myprofile/config.yaml').expanduser().read_text())
print(cfg.get('display', {}).get('platforms', {}).get('telegram', {}))
PY
```

### 运行 Hermes 测试（如果源码里有这些测试）

```bash
cd ~/.hermes/hermes-agent
python -m pytest tests/gateway/test_display_config.py tests/gateway/test_run_progress_topics.py -q
```

## 安全说明

这个仓库刻意不包含：

- bot token；
- API key；
- OAuth token；
- cookie；
- 本地用户路径；
- 私有 profile 配置。

脚本不会读取或打印 `.env`、token、cookie、认证文件。它只读取/修改：

- Hermes 源码中的 `gateway/run.py`；
- Hermes 源码中的 `gateway/display_config.py`；
- 你显式指定的 `config.yaml`。

## 局限

- 这是基于当前 Hermes Gateway 源码结构的补丁。Hermes upstream 大改时，anchor 可能找不到，需要手工适配。
- 删除是 best-effort：如果 Telegram API 返回失败、消息过旧、bot 权限异常，进度气泡可能残留。
- 只处理 gateway tool-progress 气泡，不处理：最终回复、审批提示、媒体消息、agent 主动发出的自然语言中间态。
- Feishu/Lark 不会自动获得相同行为；需要平台 adapter 实现 `delete_message(...)`。

## 推荐仓库名

```text
hermes-transient-progress-cleanup
```

## License

MIT
