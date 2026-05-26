"""Internal building blocks for the installer commands.

Each module owns one concern:
- markers:  managed/refreshable markers + .env scanner
- files:    rendering managed file content and applying writes
- gitignore: merging the managed .gitignore block
- bootstrap: invoking the target's tool/setup/setup.{sh,ps1}
- profiles: enumerating sources that ship into a target repo
- paths:    resolving bundled vs source-checkout asset roots
"""
