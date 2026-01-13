# Code Review MCP

AI-powered code review using Zhipu GLM-4.7. GLM autonomously gathers context (diffs, artifacts) and provides thorough reviews.

## Setup

1. **Install dependencies:**

   ```bash
   uv sync
   ```

2. **Configure API Key:**

   ```bash
   cp .env.example .env
   # Edit .env and add your Zhipu API key
   ```

3. **Add to your IDE's MCP config:**

   ```json
   {
     "mcpServers": {
       "review-mcp": {
         "command": "uv",
         "args": [
           "run",
           "--directory",
           "/absolute/path/to/review_mcp",
           "python",
           "server.py"
         ]
       }
     }
   }
   ```

   > Replace `/absolute/path/to/review_mcp` with the actual path to this project.

4. **Restart your IDE** to load the new MCP server.

## Configuration

Environment variables (in `.env`):

- `ZHIPU_API_KEY` (required): Your Zhipu API key
- `ZHIPU_BASE_URL` (optional): Override API endpoint
- `MAX_REVIEW_ITERATIONS` (optional): Max tool-calling iterations (default: 10)

## Usage

The MCP exposes **1 tool**: `review_with_context`

When called, it automatically:

1. Pre-reads `implementation_plan.md`, `task.md`, `walkthrough.md` (if they exist)
2. Resolves `render_diffs()` and `file:///` links in artifacts
3. Sends context to GLM-4.7
4. GLM gathers additional info as needed using its tools
5. Returns the final review

Example prompt to your AI assistant:

> "Review my staged changes"

## Security Note

The reviewer agent can read any file accessible from the working directory. This is by design for comprehensive reviews, but be aware of this when using in sensitive environments.
