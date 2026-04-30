# ASD Setup

## Install

```bash
cd asd
uv pip install -e .
```

## Join the Shared Bus

```bash
export ADHD_BUS_REPO_SLUG=projects
```

ASD publishes schema announcements to the ADHD bus when knowledge artifacts are ingested or
compiled.

## MCP Server

```json
{
  "mcpServers": {
    "asd": {
      "command": "bash",
      "args": [
        "-c",
        "uv --directory /home/mrrobot0985/work/projects/autism-spectrum-driver run asd-mcp"
      ]
    },
    "adhd": {
      "command": "bash",
      "args": [
        "-c",
        "ADHD_BUS_REPO_SLUG=projects uv --directory /home/mrrobot0985/work/projects/attention-deficit-hyperactivity-driver run adhd-mcp"
      ]
    }
  }
}
```

Full workspace guide: `../SETUP.md`
