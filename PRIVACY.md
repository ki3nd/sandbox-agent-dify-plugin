# Sandbox Agent - Privacy Policy

## Data Collection and Usage

### Information Collected

This plugin collects and processes the following information to operate:

#### Required Information
- **Sandbox API Key**: Used to authenticate with the sandbox provider (E2B or Daytona). Stored securely within the Dify platform and never logged or transmitted elsewhere.
- **User Queries**: The input messages you send to the agent, forwarded to your configured LLM for reasoning.
- **Shell Command Output**: Stdout/stderr from commands executed inside your sandbox environment.

#### Optional Information
- **Sandbox Configuration**: Provider settings, workspace paths, and timeout values you provide.
- **Agent Skills**: Skill metadata read from your sandbox filesystem (SKILL.md files).

### Information Usage

Collected information is used solely for:
- Authenticating with your sandbox provider (E2B or Daytona)
- Executing shell commands in your sandbox on your behalf
- Sending queries and command results to your configured LLM for reasoning
- Storing conversation history in Dify session storage for multi-turn memory

## Data Storage

### Conversation History
- Conversation turns (user queries, assistant responses, tool results) are stored in **Dify session storage** scoped to your workflow session.
- History is capped at 100 turns and 900 KB per session.
- No conversation data is sent to external services other than your configured LLM provider.

### API Keys
- Sandbox API keys are stored as Dify secret inputs and handled entirely within the Dify platform.
- This plugin does not store or log API keys independently.

## Third-Party Services

This plugin connects to external services you configure:

- **E2B** (https://e2b.dev) — if using E2B as sandbox provider
- **Daytona** (https://daytona.io) — if using Daytona as sandbox provider
- **Your configured LLM provider** — for agent reasoning

Please review the privacy policies of these services independently.

## Data Retention

This plugin does not retain any data beyond the Dify session storage lifecycle. Clearing a session or conversation removes all associated history.

## Contact

For privacy concerns, open an issue at the plugin repository.
