"""Sandbox Agent Strategy - ReAct agent with sandbox execution."""

import asyncio
import json
import shlex
import time
import yaml
from collections.abc import Generator
from copy import deepcopy
from typing import Any, Optional, cast

from dify_plugin.entities.agent import AgentInvokeMessage
from dify_plugin.entities.model import ModelFeature
from dify_plugin.entities.model.llm import (
    LLMModelConfig,
    LLMResult,
    LLMResultChunk,
    LLMUsage,
)
from dify_plugin.entities.model.message import (
    AssistantPromptMessage,
    PromptMessage,
    PromptMessageContentType,
    PromptMessageTool,
    SystemPromptMessage,
    ToolPromptMessage,
    UserPromptMessage,
)
from dify_plugin.entities.tool import ToolInvokeMessage, ToolProviderType
from dify_plugin.interfaces.agent import (
    AgentModelConfig,
    AgentStrategy,
    ToolEntity,
    ToolInvokeMeta,
)
from pydantic import BaseModel, Field

# Local imports
from sandbox import SandboxFactory, SandboxProvider, AbstractSandbox
from sandbox.exceptions import SandboxError, SandboxNotFoundError
from tools.exec_command import EXEC_COMMAND_SCHEMA, EXEC_COMMAND_DESCRIPTION
from tools.path_utils import resolve_cwd
from skills import SkillsLoader, SkillsIndex
from history.manager import HistoryManager
from history.models import HistoryData


# ============================================================================
# Constants
# ============================================================================

class LogMetadata:
    """Metadata keys for logging"""
    STARTED_AT = "started_at"
    PROVIDER = "provider"
    FINISHED_AT = "finished_at"
    ELAPSED_TIME = "elapsed_time"
    TOTAL_PRICE = "total_price"
    CURRENCY = "currency"
    TOTAL_TOKENS = "total_tokens"


DEFAULT_SYSTEM_PROMPT = """You are a sandbox agent, an AI assistant with access to a remote sandbox environment for code execution, file operations, and task automation.

## Core Behavior

- Be concise and direct. Don't over-explain unless asked.
- NEVER add unnecessary preamble ("Sure!", "Great question!", "I'll now...").
- Don't say "I'll now do X" — just do it.
- Keep working until the task is fully complete. Don't stop partway to explain what you would do — do it.

## Sandbox Execution

You have access to a sandbox environment with the following tools:

### `exec_command`
Execute shell commands in the sandbox.
- `command`: The shell command to run (required)
- `cwd`: Working directory relative to workspace root (optional)
- `timeout`: Command timeout in seconds (optional)

**Reading results:**
- Check `<exit_code>` - non-zero means failure
- Read `<stdout>` and `<stderr>` for output
- `[truncated]` indicates output was cut off

**Best practices:**
- Use `cwd` parameter instead of `cd` commands when possible
- For long-running commands, consider using `timeout`
- Chain commands with `&&` for dependent operations
- Use `|| true` to ignore non-critical failures

## Task Execution

When the user asks you to do something:

1. **Understand first** — explore the workspace, check existing files and patterns
2. **Act** — implement the solution using sandbox tools
3. **Verify** — check your work against what was asked, not against your own output

**When things go wrong:**
- Read the FULL error output — the root cause is often in the middle
- If something fails repeatedly, stop and analyze *why* — don't keep retrying the same approach
- Address root causes, not symptoms

## Progress Updates

For longer tasks, provide brief progress updates — a concise sentence recapping what you've done and what's next.
"""


WORKSPACE_INFO_TEMPLATE = """
## Workspace

You are working in a sandbox environment.
- **Workspace root**: `{workspace_root}`
- **Provider**: {provider}

All relative paths in `cwd` parameter are resolved relative to the workspace root.
"""


# ============================================================================
# Parameter Models
# ============================================================================

class SandboxConfig(BaseModel):
    """Parsed sandbox configuration."""
    provider: str = "daytona"
    api_url: str = ""
    api_key: str = ""  # Merged from sandbox_api_key
    workspace_root: str = "/home/daytona/workspace"
    skills_paths: list[str] = Field(default_factory=list)
    max_output_chars: int = 8000
    exec_timeout: int = 30
    connect_timeout: int = 60  # Timeout for sandbox connection in seconds
    sandbox_template: str = ""
    env_vars: dict[str, str] = Field(default_factory=dict)
    auto_reconnect: bool = True

    @classmethod
    def from_yaml(cls, yaml_str: str | None, api_key: str | None = None) -> "SandboxConfig":
        """Parse from YAML string and merge API key."""
        config_dict = {}
        if yaml_str:
            try:
                config_dict = yaml.safe_load(yaml_str) or {}
            except yaml.YAMLError:
                pass
        
        if api_key:
            config_dict["api_key"] = api_key
        
        return cls(**config_dict)


class ContextItem(BaseModel):
    """Knowledge base context item."""
    content: str
    title: str
    metadata: dict[str, Any]


class SandboxAgentParams(BaseModel):
    """All parameters for sandbox agent."""
    query: str
    instruction: str | None = None
    model: AgentModelConfig
    tools: list[ToolEntity] | None = None
    context: list[ContextItem] | None = None
    maximum_iterations: int = 20
    
    # Sandbox
    sandbox_id: str
    sandbox_config: str | None = None
    sandbox_api_key: str | None = None
    
    # Memory
    memory_turns: int = 10


class ExecutionMetadata(BaseModel):
    """Execution metadata with default values"""
    total_price: float = 0.0
    currency: str = ""
    total_tokens: int = 0
    prompt_tokens: int = 0
    prompt_unit_price: float = 0.0
    prompt_price_unit: float = 0.0
    prompt_price: float = 0.0
    completion_tokens: int = 0
    completion_unit_price: float = 0.0
    completion_price_unit: float = 0.0
    completion_price: float = 0.0
    latency: float = 0.0
    
    @classmethod
    def from_llm_usage(cls, usage: Optional[LLMUsage]) -> "ExecutionMetadata":
        """Create ExecutionMetadata from LLMUsage, handling None case"""
        if usage is None:
            return cls()
        
        return cls(
            total_price=float(usage.total_price),
            currency=usage.currency,
            total_tokens=usage.total_tokens,
            prompt_tokens=usage.prompt_tokens,
            prompt_unit_price=float(usage.prompt_unit_price),
            prompt_price_unit=float(usage.prompt_price_unit),
            prompt_price=float(usage.prompt_price),
            completion_tokens=usage.completion_tokens,
            completion_unit_price=float(usage.completion_unit_price),
            completion_price_unit=float(usage.completion_price_unit),
            completion_price=float(usage.completion_price),
            latency=usage.latency
        )


# ============================================================================
# Sandbox Agent Strategy
# ============================================================================

class SandboxAgentStrategy(AgentStrategy):
    """ReAct agent with sandbox execution capabilities."""
    
    # Instance state
    query: str = ""
    instruction: str | None = ""
    sandbox: AbstractSandbox | None = None
    sandbox_config: SandboxConfig | None = None
    skills_index: SkillsIndex | None = None
    history_manager: HistoryManager | None = None

    def _build_system_prompt(self, skills_context: str = "") -> str:
        """Build system prompt with optional skills context."""
        parts = []
        
        # User instruction first
        if self.instruction:
            parts.append(self.instruction)
        
        # Default sandbox instructions
        parts.append(DEFAULT_SYSTEM_PROMPT)
        
        # Workspace info
        if self.sandbox_config:
            workspace_info = WORKSPACE_INFO_TEMPLATE.format(
                workspace_root=self.sandbox_config.workspace_root,
                provider=self.sandbox_config.provider.upper(),
            )
            parts.append(workspace_info)
        
        # Skills context
        if skills_context:
            parts.append(skills_context)
        
        return "\n\n".join(parts)

    def _get_builtin_tool_schemas(self) -> list[PromptMessageTool]:
        """Get schemas for built-in sandbox tools."""
        return [
            PromptMessageTool(
                name="exec_command",
                description=EXEC_COMMAND_DESCRIPTION,
                parameters=EXEC_COMMAND_SCHEMA,
            ),
            # TODO: Add view_image and apply_patch when implemented
        ]

    async def _execute_builtin_tool(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
    ) -> str:
        """Execute a built-in sandbox tool."""
        if tool_name == "exec_command":
            if not self.sandbox or not self.sandbox_config:
                return "Error: Sandbox not connected"
            
            command = tool_args.get("command", "")
            cwd = resolve_cwd(
                tool_args.get("cwd"),
                self.sandbox_config.workspace_root,
            )
            full_command = f"cd {shlex.quote(cwd)} && {command}"
            result = await self.sandbox.exec(
                full_command, timeout=float(self.sandbox_config.exec_timeout)
            )
            return result.format(max_chars=self.sandbox_config.max_output_chars)
        
        return f"Unknown built-in tool: {tool_name}"

    def _invoke(
        self, parameters: dict[str, Any]
    ) -> Generator[AgentInvokeMessage, None, None]:
        """Run sandbox agent."""
        # Parse parameters
        params = SandboxAgentParams(**parameters)
        self.query = params.query
        self.instruction = params.instruction
        
        # Parse sandbox config
        self.sandbox_config = SandboxConfig.from_yaml(
            params.sandbox_config,
            params.sandbox_api_key,
        )
        
        # Initialize history manager
        session_id = getattr(self.session, 'conversation_id', None) or "global"
        self.history_manager = HistoryManager(
            storage=self.session.storage,
            session_id=session_id,
        )

        loop = asyncio.new_event_loop()

        # Connect to sandbox
        connect_started_at = time.perf_counter()
        connect_log = self.create_log_message(
            label="Connecting to sandbox",
            data={"sandbox_id": params.sandbox_id, "provider": self.sandbox_config.provider},
            status=ToolInvokeMessage.LogMessage.LogStatus.START,
        )
        yield connect_log
        
        try:
            # Connect with timeout (default 60s)
            connect_timeout = self.sandbox_config.connect_timeout
            self.sandbox = loop.run_until_complete(
                asyncio.wait_for(
                    SandboxFactory.connect(
                        provider=self.sandbox_config.provider,
                        sandbox_id=params.sandbox_id,
                        api_key=self.sandbox_config.api_key,
                        api_url=self.sandbox_config.api_url or None,
                    ),
                    timeout=connect_timeout,
                )
            )
            yield self.finish_log_message(
                log=connect_log,
                data={"status": "connected"},
                metadata={
                    LogMetadata.ELAPSED_TIME: time.perf_counter() - connect_started_at,
                },
            )
        except asyncio.TimeoutError:
            yield self.finish_log_message(
                log=connect_log,
                data={"status": "timeout"},
                metadata={
                    LogMetadata.ELAPSED_TIME: time.perf_counter() - connect_started_at,
                },
            )
            yield self.create_text_message(
                f"Error: Sandbox connection timed out after {connect_timeout}s. "
                f"Please check if sandbox '{params.sandbox_id}' is running."
            )
            return
        except SandboxNotFoundError as e:
            yield self.finish_log_message(
                log=connect_log,
                data={"status": "not_found"},
            )
            yield self.create_text_message(f"Error: {e}")
            return
        except SandboxError as e:
            yield self.finish_log_message(
                log=connect_log,
                data={"status": "error", "error": str(e)},
            )
            yield self.create_text_message(f"Sandbox error: {e}")
            return
        
        # Load skills
        skills_context = ""
        if self.sandbox_config.skills_paths:
            resolved_skills_paths = [
                resolve_cwd(p, self.sandbox_config.workspace_root)
                for p in self.sandbox_config.skills_paths
            ]
            loader = SkillsLoader(
                skills_paths=resolved_skills_paths,
                sandbox=self.sandbox,
            )
            self.skills_index = loop.run_until_complete(
                loader.load()
            )
            if not self.skills_index.is_empty():
                skills_context = self.skills_index.to_prompt_context()
        
        # Build system prompt
        system_prompt = self._build_system_prompt(skills_context)
        
        # Load history
        history_messages = self.history_manager.to_prompt_messages(
            memory_turns=params.memory_turns,
        )
        
        # Build initial prompt messages
        base_messages: list[PromptMessage] = [
            SystemPromptMessage(content=system_prompt),
            *history_messages,
            UserPromptMessage(content=params.query),
        ]
        
        # Setup tools
        tools = params.tools or []
        tool_instances = {tool.identity.name: tool for tool in tools}
        
        # Get tool schemas (Dify tools + built-in)
        prompt_messages_tools = self._init_prompt_tools(tools)
        prompt_messages_tools.extend(self._get_builtin_tool_schemas())
        
        # Track built-in tool names
        builtin_tool_names = {"exec_command"}  # TODO: add view_image, apply_patch
        
        # Model config
        model = params.model
        stream = (
            ModelFeature.STREAM_TOOL_CALL in model.entity.features
            if model.entity and model.entity.features
            else False
        )
        stop = model.completion_params.get("stop", []) if model.completion_params else []
        
        # ReAct loop state
        iteration_step = 1
        max_iteration_steps = params.maximum_iterations
        current_thoughts: list[PromptMessage] = []
        function_call_state = True
        llm_usage: dict[str, Optional[LLMUsage]] = {"usage": None}
        final_answer = ""

        while function_call_state and iteration_step <= max_iteration_steps:
            # start a new round
            function_call_state = False
            round_started_at = time.perf_counter()
            round_log = self.create_log_message(
                label=f"ROUND {iteration_step}",
                data={},
                metadata={
                    LogMetadata.STARTED_AT: round_started_at,
                },
                status=ToolInvokeMessage.LogMessage.LogStatus.START,
            )
            yield round_log

            # recalc llm max tokens
            prompt_messages = self._organize_prompt_messages(
                history_prompt_messages=base_messages,
                current_thoughts=current_thoughts,
                model=model,
            )
            if model.entity and model.completion_params:
                self.recalc_llm_max_tokens(
                    model.entity, prompt_messages, model.completion_params
                )
            # invoke model
            model_started_at = time.perf_counter()
            model_log = self.create_log_message(
                label=f"{model.model} Thought",
                data={},
                metadata={
                    LogMetadata.STARTED_AT: model_started_at,
                    LogMetadata.PROVIDER: model.provider,
                },
                parent=round_log,
                status=ToolInvokeMessage.LogMessage.LogStatus.START,
            )
            yield model_log
            model_config = LLMModelConfig(**model.model_dump(mode="json"))
            chunks: Generator[LLMResultChunk, None, None] | LLMResult = (
                self.session.model.llm.invoke(
                    model_config=model_config,
                    prompt_messages=prompt_messages,
                    stop=stop,
                    stream=stream,
                    tools=prompt_messages_tools,
                )
            )

            tool_calls: list[tuple[str, str, dict[str, Any]]] = []

            # save full response
            response = ""

            # save tool call names and inputs
            tool_call_names = ""

            current_llm_usage = None

            if isinstance(chunks, Generator):
                for chunk in chunks:
                    # check if there is any tool call
                    if self.check_tool_calls(chunk):
                        function_call_state = True
                        tool_calls.extend(self.extract_tool_calls(chunk) or [])
                        tool_call_names = ";".join(
                            [tool_call[1] for tool_call in tool_calls]
                        )

                    if chunk.delta.message and chunk.delta.message.content:
                        if isinstance(chunk.delta.message.content, list):
                            for content in chunk.delta.message.content:
                                response += content.data
                                if (
                                    not function_call_state
                                    or iteration_step == max_iteration_steps
                                ):
                                    yield self.create_text_message(content.data)
                        else:
                            response += str(chunk.delta.message.content)
                            if (
                                not function_call_state
                                or iteration_step == max_iteration_steps
                            ):
                                yield self.create_text_message(
                                    str(chunk.delta.message.content)
                                )

                    if chunk.delta.usage:
                        self.increase_usage(llm_usage, chunk.delta.usage)
                        current_llm_usage = chunk.delta.usage

            else:
                result = chunks
                result = cast(LLMResult, result)
                # check if there is any tool call
                if self.check_blocking_tool_calls(result):
                    function_call_state = True
                    tool_calls.extend(self.extract_blocking_tool_calls(result) or [])
                    tool_call_names = ";".join(
                        [tool_call[1] for tool_call in tool_calls]
                    )

                if result.usage:
                    self.increase_usage(llm_usage, result.usage)
                    current_llm_usage = result.usage

                if result.message and result.message.content:
                    if isinstance(result.message.content, list):
                        for content in result.message.content:
                            response += content.data
                    else:
                        response += str(result.message.content)

                if not result.message.content:
                    result.message.content = ""
                if isinstance(result.message.content, str):
                    yield self.create_text_message(result.message.content)
                elif isinstance(result.message.content, list):
                    for content in result.message.content:
                        yield self.create_text_message(content.data)

            yield self.finish_log_message(
                log=model_log,
                data={
                    "output": response,
                    "tool_name": tool_call_names,
                    "tool_input": [
                        {"name": tool_call[1], "args": tool_call[2]}
                        for tool_call in tool_calls
                    ],
                },
                metadata={
                    LogMetadata.STARTED_AT: model_started_at,
                    LogMetadata.FINISHED_AT: time.perf_counter(),
                    LogMetadata.ELAPSED_TIME: time.perf_counter() - model_started_at,
                    LogMetadata.PROVIDER: model.provider,
                    LogMetadata.TOTAL_PRICE: current_llm_usage.total_price
                    if current_llm_usage
                    else 0,
                    LogMetadata.CURRENCY: current_llm_usage.currency
                    if current_llm_usage
                    else "",
                    LogMetadata.TOTAL_TOKENS: current_llm_usage.total_tokens
                    if current_llm_usage
                    else 0,
                },
            )

            # If there are tool calls, merge all tool calls into a single assistant message
            if tool_calls:
                tool_call_objects = [
                    AssistantPromptMessage.ToolCall(
                        id=tool_call_id,
                        type="function",
                        function=AssistantPromptMessage.ToolCall.ToolCallFunction(
                            name=tool_call_name,
                            arguments=json.dumps(
                                tool_call_args, ensure_ascii=False
                            ),
                        ),
                    )
                    for tool_call_id, tool_call_name, tool_call_args in tool_calls
                ]
                assistant_message = AssistantPromptMessage(
                    content=response,  # Preserve LLM returned content, even if empty
                    tool_calls=tool_call_objects
                )
                current_thoughts.append(assistant_message)
            elif response.strip():
                # If no tool calls but has response, add a regular assistant message
                assistant_message = AssistantPromptMessage(
                    content=response, tool_calls=[]
                )
                current_thoughts.append(assistant_message)

            final_answer += response + "\n"

            # call tools
            tool_responses = []
            # Check if max iterations reached (but allow tool calls when max_iteration_steps == 1)
            if tool_calls and iteration_step == max_iteration_steps and max_iteration_steps > 1:
                # Max iterations reached, return message instead of calling tools
                for tool_call_id, tool_call_name, tool_call_args in tool_calls:
                    # Create log entry for the skipped tool call
                    tool_call_started_at = time.perf_counter()
                    tool_call_log = self.create_log_message(
                        label=f"CALL {tool_call_name}",
                        data={},
                        metadata={
                            LogMetadata.STARTED_AT: time.perf_counter(),
                            LogMetadata.PROVIDER: tool_instances[tool_call_name].identity.provider
                            if tool_instances.get(tool_call_name)
                            else "",
                        },
                        parent=round_log,
                        status=ToolInvokeMessage.LogMessage.LogStatus.START,
                    )
                    yield tool_call_log

                    # Return error message instead of calling tool
                    tool_response = {
                        "tool_call_id": tool_call_id,
                        "tool_call_name": tool_call_name,
                        "tool_response": (
                            f"Maximum iteration limit ({max_iteration_steps}) reached. "
                            f"Cannot call tool '{tool_call_name}'. "
                            f"Please consider increasing the iteration limit."
                        ),
                    }
                    tool_responses.append(tool_response)

                    yield self.finish_log_message(
                        log=tool_call_log,
                        data={"output": tool_response},
                        metadata={
                            LogMetadata.STARTED_AT: tool_call_started_at,
                            LogMetadata.PROVIDER: tool_instances[tool_call_name].identity.provider
                            if tool_instances.get(tool_call_name)
                            else "",
                            LogMetadata.FINISHED_AT: time.perf_counter(),
                            LogMetadata.ELAPSED_TIME: time.perf_counter() - tool_call_started_at,
                        },
                    )

                    current_thoughts.append(
                        ToolPromptMessage(
                            content=tool_response["tool_response"],
                            tool_call_id=tool_call_id,
                            name=tool_call_name,
                        )
                    )
            else:
                for tool_call_id, tool_call_name, tool_call_args in tool_calls:
                    tool_instance = tool_instances.get(tool_call_name)
                    is_builtin = tool_call_name in builtin_tool_names
                    
                    tool_call_started_at = time.perf_counter()
                    tool_call_log = self.create_log_message(
                        label=f"CALL {tool_call_name}",
                        data={},
                        metadata={
                            LogMetadata.STARTED_AT: time.perf_counter(),
                            LogMetadata.PROVIDER: "sandbox" if is_builtin else (
                                tool_instance.identity.provider if tool_instance else ""
                            ),
                        },
                        parent=round_log,
                        status=ToolInvokeMessage.LogMessage.LogStatus.START,
                    )
                    yield tool_call_log
                    
                    # Handle built-in sandbox tools
                    if is_builtin:
                        try:
                            tool_result = loop.run_until_complete(
                                self._execute_builtin_tool(tool_call_name, tool_call_args)
                            )
                        except Exception as e:
                            tool_result = f"Error executing {tool_call_name}: {e}"
                        
                        tool_response = {
                            "tool_call_id": tool_call_id,
                            "tool_call_name": tool_call_name,
                            "tool_call_input": tool_call_args,
                            "tool_response": tool_result,
                        }
                    elif not tool_instance:
                        tool_response = {
                            "tool_call_id": tool_call_id,
                            "tool_call_name": tool_call_name,
                            "tool_response": f"there is not a tool named {tool_call_name}",
                            "meta": ToolInvokeMeta.error_instance(
                                f"there is not a tool named {tool_call_name}"
                            ).to_dict(),
                        }
                    else:
                        # invoke tool
                        try:
                            tool_invoke_responses = self.session.tool.invoke(
                                provider_type=ToolProviderType(tool_instance.provider_type),
                                provider=tool_instance.identity.provider,
                                tool_name=tool_instance.identity.name,
                                parameters={
                                    **tool_instance.runtime_parameters,
                                    **tool_call_args,
                                },
                            )
                            tool_result = ""
                            for tool_invoke_response in tool_invoke_responses:
                                if (
                                    tool_invoke_response.type
                                    == ToolInvokeMessage.MessageType.TEXT
                                ):
                                    tool_result += cast(
                                        ToolInvokeMessage.TextMessage,
                                        tool_invoke_response.message,
                                    ).text
                                elif (
                                    tool_invoke_response.type
                                    == ToolInvokeMessage.MessageType.LINK
                                ):
                                    tool_result += (
                                        "result link: "
                                        + cast(
                                            ToolInvokeMessage.TextMessage,
                                            tool_invoke_response.message,
                                        ).text
                                        + "."
                                        + " please tell user to check it."
                                    )
                                elif tool_invoke_response.type in {
                                    ToolInvokeMessage.MessageType.IMAGE_LINK,
                                    ToolInvokeMessage.MessageType.IMAGE,
                                }:
                                    # Extract the file path or URL from the message
                                    if hasattr(tool_invoke_response.message, "text"):
                                        file_info = cast(
                                            ToolInvokeMessage.TextMessage,
                                            tool_invoke_response.message,
                                        ).text
                                        # Try to create a blob message with the file content
                                        try:
                                            # If it's a local file path, try to read it
                                            if file_info.startswith("/files/"):
                                                import os

                                                if os.path.exists(file_info):
                                                    with open(file_info, "rb") as f:
                                                        file_content = f.read()
                                                    # Create a blob message with the file content
                                                    blob_response = self.create_blob_message(
                                                        blob=file_content,
                                                        meta={
                                                            "mime_type": "image/png",
                                                            "filename": os.path.basename(
                                                                file_info
                                                            ),
                                                        },
                                                    )
                                                    yield blob_response
                                        except Exception as e:
                                            yield self.create_text_message(
                                                f"Failed to create blob message: {e}"
                                            )
                                    tool_result += (
                                        "image has been created and sent to user already, "
                                        + "you do not need to create it, just tell the user to check it now."
                                    )
                                    # TODO: convert to agent invoke message
                                    yield tool_invoke_response
                                elif (
                                    tool_invoke_response.type
                                    == ToolInvokeMessage.MessageType.JSON
                                ):
                                    text = json.dumps(
                                        cast(
                                            ToolInvokeMessage.JsonMessage,
                                            tool_invoke_response.message,
                                        ).json_object,
                                        ensure_ascii=False,
                                    )
                                    tool_result += f"tool response: {text}."
                                elif (
                                    tool_invoke_response.type
                                    == ToolInvokeMessage.MessageType.BLOB
                                ):
                                    tool_result += "Generated file ... "
                                    # TODO: convert to agent invoke message
                                    yield tool_invoke_response
                                else:
                                    tool_result += (
                                        f"tool response: {tool_invoke_response.message!r}."
                                    )
                        except Exception as e:
                            tool_result = f"tool invoke error: {e!s}"
                        tool_response = {
                            "tool_call_id": tool_call_id,
                            "tool_call_name": tool_call_name,
                            "tool_call_input": {
                                **tool_instance.runtime_parameters,
                                **tool_call_args,
                            },
                            "tool_response": tool_result,
                        }

                    yield self.finish_log_message(
                        log=tool_call_log,
                        data={
                            "output": tool_response,
                        },
                        metadata={
                            LogMetadata.STARTED_AT: tool_call_started_at,
                            LogMetadata.PROVIDER: "sandbox" if is_builtin else (
                                tool_instance.identity.provider if tool_instance else ""
                            ),
                            LogMetadata.FINISHED_AT: time.perf_counter(),
                            LogMetadata.ELAPSED_TIME: time.perf_counter()
                            - tool_call_started_at,
                        },
                    )
                    tool_responses.append(tool_response)
                    if tool_response["tool_response"] is not None:
                        current_thoughts.append(
                            ToolPromptMessage(
                                content=str(tool_response["tool_response"]),
                                tool_call_id=tool_call_id,
                                name=tool_call_name,
                            )
                        )
            # After handling all tool calls, insert a blank line so the next assistant thought
            # appears on a new line in the user interface.
            if tool_calls:
                yield self.create_text_message("\n")

            # update prompt tool (only for Dify tools, not built-in)
            for prompt_tool in prompt_messages_tools:
                if prompt_tool.name in tool_instances:
                    self.update_prompt_message_tool(
                        tool_instances[prompt_tool.name], prompt_tool
                    )
            yield self.finish_log_message(
                log=round_log,
                data={
                    "output": {
                        "llm_response": response,
                        "tool_responses": tool_responses,
                    },
                },
                metadata={
                    LogMetadata.STARTED_AT: round_started_at,
                    LogMetadata.FINISHED_AT: time.perf_counter(),
                    LogMetadata.ELAPSED_TIME: time.perf_counter() - round_started_at,
                    LogMetadata.TOTAL_PRICE: current_llm_usage.total_price
                    if current_llm_usage
                    else 0,
                    LogMetadata.CURRENCY: current_llm_usage.currency
                    if current_llm_usage
                    else "",
                    LogMetadata.TOTAL_TOKENS: current_llm_usage.total_tokens
                    if current_llm_usage
                    else 0,
                },
            )
            # If max_iteration_steps=1, need to return tool responses
            if tool_responses and max_iteration_steps == 1:
                for resp in tool_responses:
                    yield self.create_text_message(str(resp["tool_response"]))
            iteration_step += 1

        # Save turn to history
        if self.history_manager:
            usage_dict = None
            if llm_usage.get("usage"):
                usage = llm_usage["usage"]
                usage_dict = {
                    "total_tokens": usage.total_tokens,
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                }
            self.history_manager.save_turn(
                user_query=params.query,
                messages=current_thoughts,
                iteration_count=iteration_step - 1,
                usage=usage_dict,
            )

        # If context is a list of dict, create retriever resource message
        if isinstance(params.context, list):
            yield self.create_retriever_resource_message(
                retriever_resources=[
                    ToolInvokeMessage.RetrieverResourceMessage.RetrieverResource(
                        content=ctx.content,
                        position=ctx.metadata.get("position"),
                        dataset_id=ctx.metadata.get("dataset_id"),
                        dataset_name=ctx.metadata.get("dataset_name"),
                        document_id=ctx.metadata.get("document_id"),
                        document_name=ctx.metadata.get("document_name"),
                        data_source_type=ctx.metadata.get("document_data_source_type"),
                        segment_id=ctx.metadata.get("segment_id"),
                        retriever_from=ctx.metadata.get("retriever_from"),
                        score=ctx.metadata.get("score"),
                        hit_count=ctx.metadata.get("segment_hit_count"),
                        word_count=ctx.metadata.get("segment_word_count"),
                        segment_position=ctx.metadata.get("segment_position"),
                        index_node_hash=ctx.metadata.get("segment_index_node_hash"),
                        page=ctx.metadata.get("page"),
                        doc_metadata=ctx.metadata.get("doc_metadata"),
                    )
                    for ctx in params.context
                ],
                context="",
            )

        # Cleanup sandbox connection
        if self.sandbox:
            try:
                loop.run_until_complete(self.sandbox.close())
            except Exception:
                pass
        loop.close()

        metadata = ExecutionMetadata.from_llm_usage(llm_usage["usage"])
        yield self.create_json_message(
            {
                "execution_metadata": metadata.model_dump()
            }
        )

    def check_tool_calls(self, llm_result_chunk: LLMResultChunk) -> bool:
        """
        Check if there is any tool call in llm result chunk
        """
        return bool(llm_result_chunk.delta.message.tool_calls)

    def check_blocking_tool_calls(self, llm_result: LLMResult) -> bool:
        """
        Check if there is any blocking tool call in llm result
        """
        return bool(llm_result.message.tool_calls)

    def extract_tool_calls(
        self, llm_result_chunk: LLMResultChunk
    ) -> list[tuple[str, str, dict[str, Any]]]:
        """
        Extract tool calls from llm result chunk

        Returns:
            List[Tuple[str, str, Dict[str, Any]]]: [(tool_call_id, tool_call_name, tool_call_args)]
        """
        tool_calls = []
        for prompt_message in llm_result_chunk.delta.message.tool_calls:
            args = {}
            if prompt_message.function.arguments != "":
                args = json.loads(prompt_message.function.arguments)

            tool_calls.append(
                (
                    prompt_message.id,
                    prompt_message.function.name,
                    args,
                )
            )

        return tool_calls

    def extract_blocking_tool_calls(
        self, llm_result: LLMResult
    ) -> list[tuple[str, str, dict[str, Any]]]:
        """
        Extract blocking tool calls from llm result

        Returns:
            List[Tuple[str, str, Dict[str, Any]]]: [(tool_call_id, tool_call_name, tool_call_args)]
        """
        tool_calls = []
        for prompt_message in llm_result.message.tool_calls:
            args = {}
            if prompt_message.function.arguments != "":
                args = json.loads(prompt_message.function.arguments)

            tool_calls.append(
                (
                    prompt_message.id,
                    prompt_message.function.name,
                    args,
                )
            )

        return tool_calls

    def _init_system_message(
        self, prompt_template: str, prompt_messages: list[PromptMessage]
    ) -> list[PromptMessage]:
        """
        Initialize system message
        """
        if not prompt_messages and prompt_template:
            return [
                SystemPromptMessage(content=prompt_template),
            ]

        if (
            prompt_messages
            and not isinstance(prompt_messages[0], SystemPromptMessage)
            and prompt_template
        ):
            prompt_messages.insert(0, SystemPromptMessage(content=prompt_template))

        return prompt_messages or []

    def _clear_user_prompt_image_messages(
        self, prompt_messages: list[PromptMessage]
    ) -> list[PromptMessage]:
        """
        Clear image messages from prompt messages.
        Converts image content to "[image]" placeholder text.

        This is needed because:
        1. Some models don't support vision at all
        2. Some models support vision in the first iteration but not in subsequent iterations
            (when tool calls are involved)
        """
        prompt_messages = deepcopy(prompt_messages)

        for prompt_message in prompt_messages:
            if isinstance(prompt_message, UserPromptMessage) and isinstance(
                prompt_message.content, list
            ):
                prompt_message.content = "\n".join(
                    [
                        content.data
                        if content.type == PromptMessageContentType.TEXT
                        else "[image]"
                        if content.type == PromptMessageContentType.IMAGE
                        else "[file]"
                        for content in prompt_message.content
                    ]
                )

        return prompt_messages

    def _organize_prompt_messages(
        self,
        current_thoughts: list[PromptMessage],
        history_prompt_messages: list[PromptMessage],
        model: AgentModelConfig | None = None,
    ) -> list[PromptMessage]:
        prompt_messages = [
            *history_prompt_messages,
            *current_thoughts,
        ]

        # Check if model supports vision
        supports_vision = (
            ModelFeature.VISION in model.entity.features
            if model and model.entity and model.entity.features
            else False
        )

        # Clear images if: model doesn't support vision OR it's not the first iteration
        if not supports_vision or len(current_thoughts) != 0:
            prompt_messages = self._clear_user_prompt_image_messages(prompt_messages)

        return prompt_messages
