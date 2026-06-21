# OpenClaw Agent Turn

systemd 已经负责生成日报。Agent Turn 不应再次运行 ScholarPulse，也不需要使用 Obsidian MCP。

1. 使用 exec 读取 `~/.local/state/scholarpulse/results/YYYY-MM-DD.json`。
2. 输出 JSON 中的 `message` 字段，保持原文，不增加说明。
3. 文件不存在、JSON 无效或 `reports` 为空时，明确输出 ScholarPulse 当日生成失败，不要补跑任务。
