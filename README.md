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

---

# Sandbox Agent (中文)

一个 Dify 插件，提供具有远程沙箱执行能力的 ReAct 代理策略。

## 功能特性

- **远程沙箱执行**：在隔离的沙箱环境中执行 shell 命令（E2B、Daytona）
- **技能系统**：从可配置路径加载和使用代理技能
- **对话历史**：具有可配置轮次限制的持久对话记忆
- **函数调用**：支持使用 LLM 函数调用进行并行工具执行
- **内置工具**：用于 shell 执行的 `exec_command`（即将推出：`view_image`、`apply_patch`）

## 配置

### 参数

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| `model` | model-selector | 是 | - | 用于推理的 LLM 模型 |
| `tools` | array[tools] | 否 | [] | 额外的 Dify 工具 |
| `query` | string | 是 | - | 用户查询 / 输入 |
| `instruction` | string | 是 | - | 代理的系统提示 / 指令 |
| `sandbox_id` | string | 是 | - | 要连接的沙箱 ID |
| `sandbox_config` | string | 否 | - | 沙箱的 YAML 配置 |
| `sandbox_api_key` | secret | 是 | - | 沙箱提供商的 API 密钥 |
| `maximum_iterations` | number | 否 | 20 | ReAct 循环最大迭代次数 |
| `memory_turns` | number | 否 | 10 | 要记住的对话轮次数 |

### 沙箱配置（YAML）

```yaml
provider: daytona          # 或 "e2b"
api_url: ""                # 仅限自托管 Daytona
workspace_root: /home/daytona/workspace
skills_paths:
  - /home/daytona/workspace/.skills
exec_timeout: 30       # 命令超时（秒）
connect_timeout: 60    # 连接超时（秒）
max_output_chars: 8000 # 截断前的最大输出字符数
```

## 支持的沙箱提供商

### E2B
- 具有自动恢复功能的云端沙箱
- 需要 E2B API 密钥
- [E2B 文档](https://e2b.dev/docs)

### Daytona
- 自托管或云端沙箱
- 支持自定义 API URL
- [Daytona 文档](https://daytona.io/docs)

## 技能系统

技能存储在包含 `SKILL.md` 文件的目录中，该文件包含 YAML 前置元数据：

```
.skills/
├── web-search/
│   └── SKILL.md
├── code-review/
│   └── SKILL.md
└── data-analysis/
    └── SKILL.md
```

`SKILL.md` 示例：
```markdown
---
name: web-search
description: 在网上搜索信息
tags: [search, research]
---

# 网络搜索技能

使用此技能的说明...
```

## 使用方法

1. 在您的提供商（E2B 或 Daytona）中创建沙箱
2. 使用您的沙箱 ID 和 API 密钥配置插件
3. 将 Sandbox Agent 策略添加到您的 Dify 工作流
4. 代理将在沙箱中执行命令并对结果进行推理

## 许可证

MIT 许可证
