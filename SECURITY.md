# Security policy

## Secrets

Never commit LLM keys, Abaqus credentials or internal case paths. Store keys in the ignored `.env` file or operating-system environment variables. The example file contains variable names only.

If a key appears in a commit, log, screenshot or chat, revoke it at the provider and issue a replacement. Removing a key from the latest file is not enough once it has entered Git history.

## Reporting

Use GitHub private vulnerability reporting or contact the maintainer listed in `pyproject.toml`. Do not include live credentials, licensed Abaqus files or confidential customer models in a public issue.

## Execution boundary

Natural-language and LLM output is treated as an untrusted plan. Abaqus submission and external API calls require explicit user confirmation. Keep the MCP socket bridge bound to localhost unless a separate authenticated transport is provided.
