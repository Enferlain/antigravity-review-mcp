# Code Review MCP

AI-powered code review using Zhipu GLM. The server gathers git diffs, project artifacts, and source context, then asks the model for a focused review.

## Installation

Install dependencies:

```bash
git clone https://github.com/Enferlain/antigravity-review-mcp.git
cd antigravity-review-mcp
cp .env.example .env
# Optional: edit .env and add your API key
uv sync
```

Then add it to your MCP client.

For local Codex / VS Code usage, a direct `uv run` command is the most reliable option:

```json
{
  "mcpServers": {
    "review-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/antigravity-review-mcp",
        "run",
        "review-mcp",
        "--workspace-dir",
        "/absolute/path/to/the-repo-you-want-reviewed"
      ]
    }
  }
}
```

You can still use `uvx` if you prefer installing from Git:

```json
{
  "mcpServers": {
    "review-mcp": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/Enferlain/antigravity-review-mcp",
        "review-mcp",
        "--workspace-dir",
        "/absolute/path/to/the-repo-you-want-reviewed"
      ]
    }
  }
}
```

## Configuration

Environment variables (in `.env`):

- `AI_API_KEY` (required): Your API key
- `ZHIPU_API_KEY` (optional): Backward-compatible fallback key name
- `ZHIPU_BASE_URL` (optional): Override API endpoint
- `MAX_REVIEW_ITERATIONS` (optional): Max tool-calling iterations (default: 20)

## Usage

The MCP exposes **1 tool**: `review_with_context`

Parameters:

- `diff_target`: 'staged' (default), 'unstaged', or a git ref like 'HEAD~1'
- `context_files`: Additional files to include as context
- `focus_files`: Specific files to focus the review on
- `task_description`: Description of what you're trying to accomplish
- `working_directory`: Git repository root (optional, falls back to config)

When called, it automatically:

1. Pre-reads `implementation_plan.md`, `task.md`, `walkthrough.md` (if they exist)
2. Resolves `render_diffs()` and `file:///` links in artifacts
3. Sends context to GLM
4. GLM gathers additional info as needed using its tools
5. Returns the final review

## Codex / VS Code Notes

This server now starts cleanly under MCP hosts because it avoids doing heavy work at import time. A few setup notes still matter:

1. Use absolute paths for both the MCP project and the reviewed repository.
2. If your MCP client cannot inject the current repo automatically, set `--workspace-dir` in the config.
3. Prefer setting `AI_API_KEY` as a system/user environment variable instead of storing it in MCP config.
4. The tool-level `working_directory` argument still overrides the configured workspace when your agent provides it.

Example Windows path:

```json
"args": [
  "--directory",
  "D:/Projects/antigravity-review-mcp",
  "run",
  "review-mcp",
  "--workspace-dir",
  "D:/Projects/myrepo"
]
```

Example prompt to your AI assistant:

> "Review my staged changes"

## Security Note

The reviewer agent can read any file accessible from the working directory. This is by design for comprehensive reviews, but be aware of this when using in sensitive environments.
