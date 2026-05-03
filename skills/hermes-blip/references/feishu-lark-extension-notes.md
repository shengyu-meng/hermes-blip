# Feishu/Lark Extension Notes

The Telegram transient progress cleanup patch relies on two pieces:

1. Hermes Gateway core tracks transient tool-progress message IDs.
2. The platform adapter implements `delete_message(chat_id, message_id)`.

Telegram has a Bot API deletion endpoint, so the cleanup can delete the bot's own progress message.

For Feishu/Lark, the same user-facing behavior is possible, but it requires adapter work first:

- implement `FeishuAdapter.delete_message(...)`;
- call Feishu/Lark message recall/delete API for bot-owned transient messages;
- enable platform config such as:

```yaml
display:
  platforms:
    feishu:
      tool_progress_cleanup: delete_on_complete
      tool_progress_message_style: recent
      tool_progress_max_lines: 3
```

Do not assume the Telegram patch alone enables Feishu/Lark cleanup. Also verify the bot has permission to recall messages it sent and that enterprise recall time limits allow the operation.
