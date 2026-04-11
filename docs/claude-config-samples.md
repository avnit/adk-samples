## Claude client config examples — set model to Claude Sonnet 3.5

This short file provides example client configuration snippets that set the
preferred model to `claude-sonnet-3.5`. The repository prefers Claude Sonnet
3.5 for local assistant clients where supported. These are examples only — the
project does not currently contain local client config files.

1) `claude_desktop_config.json` (example)

```json
{
  "mcpServers": {
    "Wiz MCP Server": {
      "command": "/path/to/uv",
      "args": [
        "--directory",
        "./python/agents/wiz/wiz-mcp/src/wiz_mcp_server",
        "run",
        "--with",
        "mcp[cli]",
        "mcp",
        "run",
        "server.py"
      ],
      "model": "claude-sonnet-3.5"
    }
  }
}
```

2) `cline_mcp_settings.json` (example)

```json
{
  "mcpServers": {
    "Wiz MCP Server": {
      "disabled": false,
      "timeout": 60,
      "command": "/path/to/uv",
      "args": [
        "--directory",
        "./python/agents/wiz/wiz-mcp/src/wiz_mcp_server",
        "run",
        "--with",
        "mcp[cli]",
        "mcp",
        "run",
        "server.py"
      ],
      "env": {
        "WIZ_CLIENT_ID": "your_client_id",
        "WIZ_CLIENT_SECRET": "your_client_secret",
        "WIZ_DOTENV_PATH": "/path/to/.env"
      },
      "model": "claude-sonnet-3.5",
      "transportType": "stdio"
    }
  }
}
```

Notes
- These are intentionally minimal examples. Client software may expect the
  `model` key in a different location or under a different name. If you have a
  particular assistant (Claude Desktop, Cline, etc.) and want me to modify a
  real config file, point me at that file and I will patch it.
