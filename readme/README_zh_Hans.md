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
| `maximum_iterations` | number | 否 | 20 | ReAct 循环最大迭代次数 |
| `sandbox_id` | string | 是 | - | 要连接的沙箱 ID |
| `sandbox_config` | string | 否 | - | 沙箱的 YAML 配置 |
| `sandbox_api_key` | secret | 是 | - | 沙箱提供商的 API 密钥 |
| `memory_turns` | number | 否 | 10 | 要记住的对话轮次数 |

### 沙箱配置（YAML）

```yaml
provider: daytona      # 或 "e2b"
api_url: ""            # 仅限自托管 Daytona
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
