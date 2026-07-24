# Security Policy

## Supported versions

Security fixes are applied to the latest published ArcVellum release. At the time of writing, that line is `v0.95.x`.

## Reporting a vulnerability

Do not include credentials, access tokens, private manuscripts, full local paths, or reproducible exploit details in a public issue.

Use GitHub's private vulnerability reporting flow for this repository when it is available. If private reporting is unavailable, contact the repository owner through the GitHub profile first and provide only a short impact summary. Include the affected version, operating system, a minimal non-sensitive reproduction, and whether the issue can expose local project data, execute commands, bypass an approval gate, or affect update verification.

## Scope

The most sensitive surfaces are the local HTTP sidecar, desktop session bootstrap, task sandbox/writeback contracts, OpenCode and external runner process execution, updater signatures, diagnostics redaction, and local project directories. Reports about prompt quality alone should use a normal issue unless they also cause a security boundary to fail.
