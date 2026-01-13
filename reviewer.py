"""
Code review logic using Zhipu GLM-4.7 via OpenAI-compatible API.
"""

import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Configure logging to write to stderr
logging.basicConfig(
    level=logging.INFO, format="[%(name)s] %(message)s", stream=sys.stderr
)
logger = logging.getLogger("ReviewMCP")

# File patterns to exclude from diffs (lockfiles, binaries, etc.)
EXCLUDE_PATTERNS = [
    "*.lock",
    "*.json",
    "*.svg",
    "*.png",
    "*.jpg",
    "*.woff",
    "*.woff2",
    "uv.lock",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
]


def get_git_diff(target: str = "staged") -> str:
    """
    Get git diff output.

    Args:
        target: 'staged' for staged changes, 'unstaged' for working tree,
                or a git ref like 'HEAD~1' for comparing against a commit.

    Returns:
        The diff output as a string.
    """
    try:
        if target == "staged":
            args = ["git", "diff", "--staged"]
        elif target == "unstaged":
            args = ["git", "diff"]
        else:
            # Assume it's a ref like HEAD~1
            args = ["git", "diff", target]

        # Add exclusion patterns
        for pattern in EXCLUDE_PATTERNS:
            args.extend(["--", f":!{pattern}"])

        result = subprocess.run(
            args, capture_output=True, text=True, check=True, encoding="utf-8"
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error running git diff: {e.stderr}"
    except FileNotFoundError:
        return "Error: git is not installed or not in PATH"


def get_changed_files() -> list[str]:
    """Get list of changed files (staged + unstaged)."""
    try:
        # Get staged files
        staged = subprocess.run(
            ["git", "diff", "--staged", "--name-only"],
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
        )
        # Get unstaged files
        unstaged = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
        )
        files = set(
            staged.stdout.strip().split("\n") + unstaged.stdout.strip().split("\n")
        )
        return [f for f in files if f]  # Filter empty strings
    except subprocess.CalledProcessError:
        return []


def read_context_files(filepaths: list[str]) -> str:
    """
    Read multiple context files and format them for the prompt.

    Args:
        filepaths: List of file paths to read.

    Returns:
        Formatted string with file contents.
    """
    context = ""
    for filepath in filepaths:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                # Truncate very large files
                if len(content) > 50000:
                    content = content[:50000] + "\n\n... [TRUNCATED] ..."
                context += f"\n\n--- FILE: {filepath} ---\n{content}"
        except FileNotFoundError:
            context += f"\n\n(Note: Context file '{filepath}' not found)\n"
        except Exception as e:
            context += f"\n\n(Error reading '{filepath}': {e})\n"
    return context


def normalize_file_uri_path(path: str) -> str:
    """
    Normalize a path extracted from a file:// URI.

    Handles:
    - Windows paths: file:///C:/foo -> C:/foo
    - Unix paths: file:///foo -> /foo
    - Already normalized paths
    """
    # Check for Windows drive letter (e.g., C:/)
    if len(path) > 1 and path[1] == ":":
        return path
    # Unix path - ensure it starts with /
    if not path.startswith("/"):
        return "/" + path
    return path


def parse_file_links(content: str) -> tuple[list[str], list[str]]:
    """
    Parse markdown content for render_diffs() and file:// links.

    Args:
        content: Markdown content to parse.

    Returns:
        Tuple of (diff_files, read_files):
        - diff_files: Files mentioned in render_diffs() that need diffs generated
        - read_files: Files in markdown links that should be read for context
    """
    diff_files = []
    read_files = []

    # Pattern for render_diffs(file:///path/to/file)
    render_diff_pattern = r"render_diffs\s*\(\s*file:///([^)]+)\s*\)"
    for match in re.finditer(render_diff_pattern, content):
        path = unquote(match.group(1))
        diff_files.append(normalize_file_uri_path(path))

    # Pattern for markdown links: [text](file:///path)
    # But exclude render_diffs matches
    link_pattern = r"\[([^\]]*)\]\(file:///([^)]+)\)"
    for match in re.finditer(link_pattern, content):
        path = unquote(match.group(2))
        full_path = normalize_file_uri_path(path)
        # Don't duplicate files already in diff_files
        if full_path not in diff_files:
            read_files.append(full_path)

    return diff_files, read_files


def get_scoped_diff(files: list[str], target: str = "staged") -> str:
    """
    Get git diff for specific files only.

    Args:
        files: List of file paths to diff.
        target: 'staged', 'unstaged', or a git ref.

    Returns:
        Combined diff output for the specified files.
    """
    if not files:
        return ""

    diffs = []
    for filepath in files:
        try:
            # Normalize path for git
            normalized = Path(filepath).as_posix()

            if target == "staged":
                args = ["git", "diff", "--staged", "--", normalized]
            elif target == "unstaged":
                args = ["git", "diff", "--", normalized]
            else:
                args = ["git", "diff", target, "--", normalized]

            result = subprocess.run(
                args, capture_output=True, text=True, check=True, encoding="utf-8"
            )
            if result.stdout.strip():
                diffs.append(f"# Diff for: {filepath}\n{result.stdout}")
        except subprocess.CalledProcessError:
            diffs.append(f"# No diff available for: {filepath}")
        except Exception as e:
            diffs.append(f"# Error getting diff for {filepath}: {e}")

    return "\n\n".join(diffs)


def process_artifact_with_links(
    filepath: str, diff_target: str = "staged"
) -> tuple[str, str]:
    """
    Read an artifact file and resolve its links.

    Args:
        filepath: Path to the artifact (e.g., walkthrough.md).
        diff_target: Target for generating diffs.

    Returns:
        Tuple of (processed_content, scoped_diff):
        - processed_content: The artifact with render_diffs replaced by actual diffs
        - scoped_diff: Combined diff for all files mentioned in render_diffs
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return f"(Artifact not found: {filepath})", ""

    diff_files, read_files = parse_file_links(content)

    # Generate scoped diff for render_diffs files
    scoped_diff = get_scoped_diff(diff_files, diff_target)

    # Replace render_diffs() calls with actual diff content
    def replace_render_diff(match):
        path = unquote(match.group(1))
        full_path = normalize_file_uri_path(path)
        # Get diff for this specific file
        file_diff = get_scoped_diff([full_path], diff_target)
        if file_diff:
            return f"```diff\n{file_diff}\n```"
        return f"(No changes in {full_path})"

    processed = re.sub(
        r"render_diffs\s*\(\s*file:///([^)]+)\s*\)", replace_render_diff, content
    )

    # Read linked files for additional context
    linked_context = ""
    for read_path in read_files[:5]:  # Limit to 5 linked files
        try:
            with open(read_path, "r", encoding="utf-8") as f:
                file_content = f.read()
                if len(file_content) > 10000:
                    file_content = file_content[:10000] + "\n... [TRUNCATED]"
                linked_context += (
                    f"\n\n--- LINKED FILE: {read_path} ---\n{file_content}"
                )
        except Exception:
            pass

    return processed + linked_context, scoped_diff


def generate_critique(diff: str, context: str = "") -> str:
    """
    Send diff and context to GLM-4.7 for review.

    Args:
        diff: The git diff output.
        context: Optional context from artifact files.

    Returns:
        The code review from GLM-4.7.
    """
    api_key = os.getenv("ZHIPU_API_KEY")
    if not api_key:
        return "Error: ZHIPU_API_KEY environment variable is not set."

    # Use the Z.AI coding endpoint as per docs
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.z.ai/api/coding/paas/v4",
    )

    system_prompt = """You are a Senior Code Reviewer. Your goal is to verify if the code changes
match the intent described in the provided documentation.

1. If 'implementation_plan.md' is provided, check if the planned steps were actually executed.
2. If 'task.md' is provided, check for any missed requirements.
3. Highlight LOGIC errors, SECURITY risks, or potential BUGS.
4. Ignore minor style issues unless they impact readability significantly.
5. Be concise but thorough. Focus on what matters."""

    user_prompt = f"""# CONTEXT ARTIFACTS
{context if context else "(No context files provided)"}

# CODE CHANGES (DIFF)
```diff
{diff if diff else "(No changes detected)"}
```

Based on the artifacts and diff above, provide a code review. If there are no issues, say so briefly."""

    try:
        response = client.chat.completions.create(
            model="GLM-4.7",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error calling GLM-4.7 API: {e}"


# =============================================================================
# AGENTIC REVIEW - GLM-4.7 decides what info to gather
# =============================================================================

# Define tools that GLM-4.7 can use
REVIEWER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_uncommitted_changes",
            "description": "Get git diff output for uncommitted changes. Use this to see what code has been modified.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "'staged' for staged changes, 'unstaged' for working tree changes, or a git ref like 'HEAD~1'",
                        "default": "staged",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_files",
            "description": "Read the contents of one or more files. Use this to read source files, documentation, or any relevant context. You can request multiple files at once to be efficient.",
            "parameters": {
                "type": "object",
                "properties": {
                    "paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of file paths to read (absolute or relative to cwd)",
                    }
                },
                "required": ["paths"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_changed_files",
            "description": "List all files with uncommitted changes (staged + unstaged). Use this to know which files have been modified.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]


def _execute_tool(name: str, arguments: dict) -> str:
    """Execute a tool and return its result as a string."""
    if name == "get_uncommitted_changes":
        target = arguments.get("target", "staged")
        return get_git_diff(target)
    elif name == "read_files":
        paths = arguments.get("paths", [])
        return read_context_files(paths)
    elif name == "read_file":
        # Backwards compatibility
        path = arguments.get("path", "")
        return read_context_files([path])
    elif name == "list_changed_files":
        files = get_changed_files()
        return "\n".join(files) if files else "No changed files found."
    else:
        return f"Unknown tool: {name}"


def run_agentic_review(
    diff_target: str = "staged",
    context_files: list[str] | None = None,
    focus_files: list[str] | None = None,
    task_description: str = "",
) -> str:
    """
    Run an agentic review where GLM-4.7 decides what information to gather.

    Args:
        diff_target: 'staged', 'unstaged', or a git ref.
        context_files: Optional list of context files. If None, uses defaults.
        focus_files: Optional list of files to focus the review on.
        task_description: Optional description of the task being reviewed.

    Returns:
        The final code review from GLM-4.7.
    """
    import json

    api_key = os.getenv("ZHIPU_API_KEY")
    if not api_key:
        return "Error: ZHIPU_API_KEY environment variable is not set."

    # Configurable API endpoint
    base_url = os.getenv("ZHIPU_BASE_URL", "https://api.z.ai/api/coding/paas/v4")

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
    )

    # Default artifacts to ALWAYS check
    default_artifacts = [
        "implementation_plan.md",
        "task.md",
        "walkthrough.md",
    ]
    artifacts_to_read = default_artifacts + (context_files or [])

    # Pre-read artifacts that exist AND resolve their links
    artifact_context = ""
    all_diff_files = []

    logger.info("Loading artifacts...")
    for artifact in artifacts_to_read:
        try:
            with open(artifact, "r", encoding="utf-8") as f:
                content = f.read()
                logger.info(f"  ✓ Loaded {artifact}")

                # Parse for render_diffs and file links
                diff_files, linked_files = parse_file_links(content)
                all_diff_files.extend(diff_files)

                # Process the artifact - resolve render_diffs inline
                processed_content, _ = process_artifact_with_links(
                    artifact, diff_target
                )
                artifact_context += (
                    f"\n\n--- ARTIFACT: {artifact} ---\n{processed_content}"
                )

        except FileNotFoundError:
            pass  # Silently skip missing artifacts
        except Exception as e:
            logger.error(f"  ✗ Error loading {artifact}: {e}")

    # Determine which files to diff
    # Priority: focus_files > files from artifacts > all changed files
    if focus_files:
        files_to_diff = focus_files
        logger.info(f"Focusing on {len(files_to_diff)} specified files")
    elif all_diff_files:
        files_to_diff = all_diff_files
        logger.info(f"Found {len(files_to_diff)} files in artifacts")
    else:
        files_to_diff = None  # Let reviewer fetch what it needs
        logger.info("No specific files - reviewer will decide")

    # Pre-fetch diffs if we have specific files
    if files_to_diff:
        diff_content = get_scoped_diff(files_to_diff, diff_target)
        changed_files = files_to_diff
    else:
        diff_content = ""
        changed_files = []

    system_prompt = """You are a Senior Code Reviewer with access to tools.

Your job is to review code changes. You have access to these tools:
- get_uncommitted_changes: Get git diffs (staged, unstaged, or vs specific refs)
- read_files: Read multiple source files at once (efficient - use this to batch file reads)
- list_changed_files: See which files have been modified

The user will provide you with context about what to review. Use your tools
to gather any additional information you need. Be efficient - batch file reads together.

REVIEW FOCUS:
1. Does the code match the stated intent (if provided)?
2. Are there logic errors, bugs, or security risks?
3. Any missed requirements?
4. Does it follow best practices?

Be concise but thorough. Ignore minor style issues."""

    # Build initial user message with pre-fetched context
    sections = []

    if task_description:
        sections.append(f"## Task Description\n{task_description}")

    if artifact_context.strip():
        sections.append(f"## Project Artifacts\n{artifact_context}")

    if changed_files:
        sections.append(f"## Files to Review\n{chr(10).join(changed_files)}")

    if diff_content.strip():
        sections.append(f"## Git Diff ({diff_target})\n```diff\n{diff_content}\n```")

    if sections:
        user_message = "Please review the following:\n\n" + "\n\n".join(sections)
        user_message += "\n\n---\nProvide a thorough code review. Use your tools if you need more information."
    else:
        user_message = "Please review the current code changes. Use list_changed_files and get_uncommitted_changes to see what's been modified."

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    # Configurable max iterations
    max_iterations = int(os.getenv("MAX_REVIEW_ITERATIONS", "10"))
    iteration = 0
    logger.info("Starting review...")
    logger.info(f"Found {len(changed_files)} changed files")
    logger.info(f"Loaded {len(artifacts_to_read)} artifacts")

    for iteration in range(max_iterations):
        logger.info(f"Iteration {iteration + 1}: Calling GLM-4.7...")
        try:
            response = client.chat.completions.create(
                model="GLM-4.7",
                messages=messages,
                tools=REVIEWER_TOOLS,
                tool_choice="auto",
                temperature=0.2,
            )
        except Exception as e:
            return f"Error calling GLM-4.7 API: {e}"

        message = response.choices[0].message

        # If no tool calls, we're done - return the final message
        if not message.tool_calls:
            logger.info("Review complete!")
            return message.content or "No review generated."

        # Process tool calls
        messages.append(message)
        logger.info(f"GLM requested {len(message.tool_calls)} tool(s)")

        for tool_call in message.tool_calls:
            func_name = tool_call.function.name
            try:
                func_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                func_args = {}

            logger.info(f"  → {func_name}({func_args})")

            # Execute the tool
            result = _execute_tool(func_name, func_args)

            # Add tool result to messages
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )

    return "Error: Maximum iterations reached without completing review."
