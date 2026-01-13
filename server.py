"""
MCP Server for Code Review using GLM-4.7.

Exposes a SINGLE tool that triggers an agentic review where
GLM-4.7 decides what information to gather (diffs, files, context).
"""

import argparse
import os
import sys
import anyio
from mcp.server.fastmcp import FastMCP
import reviewer

# Parse command-line arguments BEFORE creating the server
parser = argparse.ArgumentParser()
parser.add_argument("-w", "--workspace", dest="workspace_dir", 
                    default=os.getcwd(),
                    help="Workspace directory (git repository root)")
args, unknown = parser.parse_known_args()

WORKSPACE_DIR = args.workspace_dir

# Log the workspace dir for debugging
print(f"[ReviewMCP] Using workspace: {WORKSPACE_DIR}", file=sys.stderr)

mcp = FastMCP(name="Code Review MCP")


@mcp.tool()
async def review_with_context(
    diff_target: str = "staged",
    context_files: list[str] | None = None,
    focus_files: list[str] | None = None,
    task_description: str = "",
) -> str:
    """
    Review code changes against project context using GLM-4.7.

    This is the main tool. It fetches the git diff, reads context files
    (like implementation_plan.md or task.md), and sends everything to
    GLM-4.7 for a thorough code review.

    Args:
        diff_target: What to diff. Options:
            - 'staged' (default): Review staged changes
            - 'unstaged': Review unstaged changes
            - A git ref like 'HEAD~1': Compare against that ref
        context_files: List of file paths to include as context.
            Defaults to common artifact files if not specified.
        focus_files: Optional list of specific files to focus the review on.
            If provided, only diffs for these files will be reviewed.
        task_description: Optional description of what you're trying to accomplish.
            Helps the reviewer understand the intent behind the changes.

    Returns:
        The code review from GLM-4.7.
    """
    # Run blocking I/O in a thread to avoid blocking the event loop
    return await anyio.to_thread.run_sync(
        lambda: reviewer.run_agentic_review(
            working_dir=WORKSPACE_DIR,
            diff_target=diff_target,
            context_files=context_files,
            focus_files=focus_files,
            task_description=task_description,
        )
    )


def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
