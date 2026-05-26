"""Internal building blocks for the installer commands.

Each module owns one concern:
- markers:  managed/refreshable markers + .env scanner
- files:    rendering managed file content and applying writes
- gitignore: merging the managed .gitignore block
- bootstrap: invoking the package-owned `fabric-vibe setup`
- profiles: enumerating sources that ship into a target repo
- paths:    resolving bundled vs source-checkout asset roots
"""
