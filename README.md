# gitlog_summary

Aggregate all git commits across multiple repositories for a given day and generate a summary.

## GitHub Token Permissions

To use this tool, you need a GitHub fine-grained personal access token with the following permissions:

### Required Fine-Grained Token Permissions
- **Repository access**: Access to the repositories you want to summarize (select "All repositories" or specific ones)
- **Repository permissions**:
  - **Contents**: Read-only
  - **Metadata**: Read-only
- **User permissions**:
  - **Email addresses**: Read-only (optional, for user email matching)

> Note: You do not need classic tokens. Fine-grained tokens are recommended for better security and control.

Set your token in the environment variable `GITHUB_TOKEN` or pass it with the `--github-token` option.
