---
name: rtk
description: RTK token optimizer integration. Auto-applied via Bash hook in Claude Code; reduces shell output token consumption.
kind: content
links:
  - skills/rtk
---

# RTK — Rust Token Killer

RTK reduces shell output token consumption. It is installed by `tool/setup/setup.sh` / `tool/setup/setup.ps1`.

Claude Code sessions handle RTK automatically through the Bash hook; no manual command prefix is required.

Do not call raw `fab`. Use `tool/setup/fab-sandbox.ps1` on Windows or `bash tool/setup/fab-sandbox` on Linux/Mac for Fabric CLI checks.

For the full RTK command reference and analytics commands, see [[skills/rtk]].
