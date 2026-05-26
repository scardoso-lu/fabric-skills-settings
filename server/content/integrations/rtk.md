---
name: rtk
description: RTK token optimizer integration. Auto-applied via Bash hook in Claude Code; reduces shell output token consumption.
kind: content
links:
  - skills/rtk
---

# RTK — Rust Token Killer

RTK reduces shell output token consumption. It is installed by `fabric-vibe setup`.

Claude Code sessions handle RTK automatically through the Bash hook; no manual command prefix is required.

Drive Fabric work through the `fabric-vibe` proxy (e.g. `fabric-vibe workspace init`, `fabric-vibe notebook deploy`) and the `fabric-server` MCP tools rather than ad-hoc `fab` calls. The setup gate's `fab --version` / `fab api workspaces` probes are the only direct `fab` use.

For the full RTK command reference and analytics commands, see [[skills/rtk]].
