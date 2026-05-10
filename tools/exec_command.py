"""exec_command built-in tool for sandbox agent."""

from pydantic import BaseModel, Field


class ExecCommandArgs(BaseModel):
    """Arguments for exec_command tool."""

    command: str = Field(
        description="Shell command to execute. May be multi-line.",
        min_length=1,
    )
    cwd: str | None = Field(
        default=None,
        description=(
            "Working directory. Relative paths are resolved from workspace_root. "
            "Defaults to workspace_root."
        ),
    )


# Tool schema for LLM
EXEC_COMMAND_SCHEMA = {
    "type": "object",
    "properties": {
        "command": {
            "type": "string",
            "description": "Shell command to execute. May be multi-line.",
        },
        "cwd": {
            "type": "string",
            "description": (
                "Working directory. Relative paths (e.g., 'src', './tests') are resolved "
                "from workspace_root. Absolute paths (e.g., '/tmp') are used as-is. "
                "Default: workspace_root."
            ),
        },
    },
    "required": ["command"],
}

EXEC_COMMAND_DESCRIPTION = """Run a shell command in the sandbox.
- Use `cwd` to set working directory (relative paths resolved from workspace_root)
- Check exit_code in the result — non-zero means failure
- Long output may be truncated"""
