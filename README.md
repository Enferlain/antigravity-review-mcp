# Code Review MCP

AI-powered code review using Zhipu GLM-4.7. GLM autonomously gathers context (diffs, artifacts) and provides thorough reviews.

## Installation

Add to your IDE's MCP config:

```json
{
  "mcpServers": {
    "review-mcp": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/Enferlain/antigravity-review-mcp",
        "review-mcp"
      ]
    }
  }
}
```

**Or** clone and run locally:

```bash
git clone https://github.com/Enferlain/antigravity-review-mcp.git
cd antigravity-review-mcp
cp .env.example .env
# Edit .env and add your Zhipu API key
```

## Configuration

Environment variables (in `.env`):

- `ZHIPU_API_KEY` (required): Your Zhipu API key
- `ZHIPU_BASE_URL` (optional): Override API endpoint
- `MAX_REVIEW_ITERATIONS` (optional): Max tool-calling iterations (default: 10)

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
3. Sends context to GLM-4.7
4. GLM gathers additional info as needed using its tools
5. Returns the final review

## Antigravity/Windsurf IDE Note

These IDEs don't support `${workspaceFolder}` variables in MCP config. Two options:

1. **Hardcode the path** in your MCP config:

   ```json
   "args": ["--from", "...", "review-mcp", "--workspace-dir", "D:/Projects/myrepo"]
   ```

2. **Pass it when calling**: The agent can pass `working_directory` parameter

Example prompt to your AI assistant:

> "Review my staged changes"

## Security Note

The reviewer agent can read any file accessible from the working directory. This is by design for comprehensive reviews, but be aware of this when using in sensitive environments.
