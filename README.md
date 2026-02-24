# Temporal MCP Server

An MCP (Model Context Protocol) server for debugging Temporal workflows. This server enables LLM-assisted debugging by exposing Temporal workflow inspection tools.

## Features

- **list_workflows** - List workflow executions with optional query filter
- **describe_workflow** - Get detailed info about a specific workflow
- **get_workflow_history** - Fetch event history for debugging

## Requirements

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) for dependency management
- A running Temporal server (local or cloud)

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd temporal-mcp

# Create virtual environment and install
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

## Configuration

Set environment variables to configure the Temporal connection:

| Variable | Description | Default |
|----------|-------------|---------|
| `TEMPORAL_ADDRESS` | Temporal server address | `localhost:7233` |
| `TEMPORAL_NAMESPACE` | Temporal namespace | `default` |
| `TEMPORAL_TLS_CERT` | Path to TLS certificate (for Cloud) | - |
| `TEMPORAL_TLS_KEY` | Path to TLS key (for Cloud) | - |
| `TEMPORAL_API_KEY` | API key (for Cloud) | - |

### Docker

#### Connect to External Temporal Server

If you already have Temporal running (locally or remotely):

```bash
# Connect to Temporal on host machine
docker compose up

# Or specify a custom address
TEMPORAL_ADDRESS=my-temporal:7233 docker compose up
```

#### Local Development with Bundled Temporal

To run a complete local setup including Temporal server and UI:

```bash
docker compose -f docker-compose.local.yml up
```

This starts:
- Temporal server on `localhost:7233`
- Temporal UI on `http://localhost:8080`
- MCP server connected to the local Temporal

#### Connect to Temporal Cloud

For Temporal Cloud with mTLS certificates:

```bash
# Place your certificates in a certs/ directory, then:
docker compose up
# After uncommenting the TLS environment variables in docker-compose.yml
```

Or with API key:

```bash
TEMPORAL_ADDRESS=your-ns.tmprl.cloud:7233 \
TEMPORAL_NAMESPACE=your-ns \
TEMPORAL_API_KEY=your-key \
docker compose up
```

### Local Development (without Docker)

Install and run directly with Python:

For Temporal Cloud, set the appropriate environment variables:

```bash
export TEMPORAL_ADDRESS="your-namespace.tmprl.cloud:7233"
export TEMPORAL_NAMESPACE="your-namespace"
export TEMPORAL_API_KEY="your-api-key"
```

Or with TLS certificates:

```bash
export TEMPORAL_ADDRESS="your-namespace.tmprl.cloud:7233"
export TEMPORAL_NAMESPACE="your-namespace"
export TEMPORAL_TLS_CERT="/path/to/cert.pem"
export TEMPORAL_TLS_KEY="/path/to/key.pem"
```

## Usage

### With Cursor

Add to your Cursor MCP settings (`~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "temporal": {
      "command": "uv",
      "args": ["run", "temporal-mcp"],
      "cwd": "/path/to/temporal-mcp",
      "env": {
        "TEMPORAL_ADDRESS": "localhost:7233",
        "TEMPORAL_NAMESPACE": "default"
      }
    }
  }
}
```

### Standalone

```bash
temporal-mcp
```

## Available Tools

### list_workflows

List workflow executions with optional filtering.

```
list_workflows(query="", limit=10)
```

- `query`: Optional Temporal list filter syntax (e.g., `WorkflowType="MyWorkflow" AND ExecutionStatus="Running"`)
- `limit`: Maximum workflows to return (default 10, max 100)

### describe_workflow

Get detailed information about a specific workflow.

```
describe_workflow(workflow_id, run_id="")
```

- `workflow_id`: The workflow ID to describe
- `run_id`: Optional run ID (uses latest if not specified)

### get_workflow_history

Fetch the event history for a workflow execution.

```
get_workflow_history(workflow_id, run_id="", max_events=100)
```

- `workflow_id`: The workflow ID
- `run_id`: Optional run ID (uses latest if not specified)
- `max_events`: Maximum events to return (default 100, max 1000)

## Development

### Setup

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

### Commands

```bash
# Format code
black src tests

# Lint
ruff check src tests

# Type check
mypy src

# Run tests
pytest

# Run all checks
black src tests && ruff check src tests && mypy src && pytest
```

### Project Structure

```
temporal-mcp/
├── pyproject.toml          # Project config and dependencies
├── Dockerfile
├── docker-compose.yml       # MCP server (external Temporal)
├── docker-compose.local.yml # Full local setup with Temporal
├── README.md
├── src/temporal_mcp/
│   ├── __init__.py
│   ├── server.py           # MCP server and tool definitions
│   ├── client.py           # Temporal client wrapper
│   ├── config.py           # Environment-based configuration
│   └── models.py           # Pydantic models
├── tests/
│   ├── conftest.py         # Test fixtures
│   ├── test_config.py
│   ├── test_client.py
│   └── test_server.py
└── docs/
    └── PLAN.txt
```

## License

MIT
