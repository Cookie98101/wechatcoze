# DouDian greetings + Feishu reminder changes

## Files changed
- `static_src/index.html`
  - Show greetings/username/password/Feishu fields for both PDD and DD in the add-platform dialog.

- `main.py`
  - Pass greetings/Feishu config into `dd_task` and send Feishu notification on errors.
  - When asking for current product without any product context, reply with a prompt to send a link/card.
  - Suppress image upload errors from UI log, keep them in file logs only.

- `doudian/DouDian.py`
  - Add greetings parameters to message polling and send greetings when missing.
  - Add Feishu config + notify helper; trigger on launch failure.
  - Parse right-side product panel and append as `from_info` message.
  - Parse product links in text messages and enrich with title/price/id when possible.
  - Avoid using stale product panel text by requiring panel content to change.
  - Add greeting cooldown window and suppress "图片未找到" user-facing message.
  - Restore original image upload behavior (no "图片链接" text injection).
