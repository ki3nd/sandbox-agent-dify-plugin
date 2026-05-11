# Sandbox Agent

**Author:** [ki3nd](https://github.com/ki3nd)   
**Type:** Agent Strategy   
**Github Repo:** https://github.com/ki3nd/sandbox-agent-dify-plugin   
**Github Issues:** https://github.com/ki3nd/sandbox-agent-dify-plugin/issues    

A Dify plugin that provides a ReAct agent strategy with remote sandbox execution capabilities.

## Features

- **Remote Sandbox Execution**: Execute shell commands in isolated sandbox environments (E2B, Daytona)
- **Skills System**: Load and use agent skills from configurable paths
- **Conversation History**: Persistent conversation memory with configurable turn limits
- **Function Calling**: Support for parallel tool execution with LLM function calling
- **Built-in Tools**: `exec_command` for shell execution (more coming: `view_image`, `apply_patch`)

## Configuration

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `model` | model-selector | Yes | - | LLM model for reasoning |
| `tools` | array[tools] | No | [] | Additional Dify tools |
| `query` | string | Yes | - | User query / input |
| `instruction` | string | Yes | - | System prompt / instruction for the agent |
| `sandbox_id` | string | Yes | - | ID of the sandbox to connect |
| `sandbox_config` | string | No | - | YAML configuration for sandbox |
| `sandbox_api_key` | secret | Yes | - | API key for sandbox provider |
| `maximum_iterations` | number | No | 20 | Max ReAct loop iterations |
| `memory_turns` | number | No | 10 | Number of conversation turns to remember |

### Sandbox Configuration (YAML)

```yaml
provider: daytona      # or "e2b"
api_url: ""            # self-hosted Daytona only
workspace_root: /home/daytona/workspace
skills_paths:
  - /home/daytona/workspace/.skills
exec_timeout: 30       # Command timeout in seconds
connect_timeout: 60    # Connection timeout in seconds
max_output_chars: 8000 # Max output characters before truncation
```

## Supported Sandbox Providers

### E2B
- Cloud-based sandbox with auto-resume
- Requires E2B API key
- [E2B Documentation](https://e2b.dev/docs)

### Daytona
- Self-hosted or cloud sandbox
- Supports custom API URL
- [Daytona Documentation](https://daytona.io/docs)

## Skills System

Skills are stored in directories with a `SKILL.md` file containing YAML frontmatter:

```
.skills/
├── web-search/
│   └── SKILL.md
├── code-review/
│   └── SKILL.md
└── data-analysis/
    └── SKILL.md
```

Example `SKILL.md`:
```markdown
---
name: web-search
description: Search the web for information
tags: [search, research]
---

# Web Search Skill

Instructions for using this skill...
```

## Usage

1. Create a sandbox in your provider (E2B or Daytona)
2. Configure the plugin with your sandbox ID and API key
3. Add the Sandbox Agent strategy to your Dify workflow
4. The agent will execute commands in the sandbox and reason about results

## License

MIT License
