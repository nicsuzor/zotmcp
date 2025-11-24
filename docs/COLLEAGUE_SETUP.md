# ZotMCP Setup Guide for Colleagues

This guide will help you set up ZotMCP to search our shared Zotero academic library from Claude Code.

## Prerequisites

You need:
1. **Claude Code** installed
2. **Python 3.10+** (check with `python --version`)
3. A **Google account** (your personal Gmail works fine)

## Step 1: Install uv (Python package manager)

Open a terminal and run:

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Close and reopen your terminal after installation.

## Step 2: Install Google Cloud CLI

Download and install from: https://cloud.google.com/sdk/docs/install

After installation, authenticate:

```bash
gcloud auth application-default login
```

This opens a browser window. Sign in with your Google account that Nic has granted access to.

## Step 3: Request Access (Contact Nic)

Send Nic your Google email address. He will:
1. Add you to the GCP project
2. Confirm when you're ready to proceed

## Step 4: Download the Zotero Database

Once Nic confirms your access:

```bash
# This downloads ~3GB of vectorized Zotero library data
uvx --from git+https://github.com/nicsuzor/zotmcp.git zotmcp-download
```

This may take 5-10 minutes depending on your connection.

## Step 5: Configure Claude Code

Add ZotMCP to Claude Code:

```bash
claude mcp add-json zot '{"command":"uvx","args":["--from","git+https://github.com/nicsuzor/zotmcp.git","zotmcp"]}'
```

## Step 6: Restart Claude Code

Completely quit and restart Claude Code for the changes to take effect.

## Verify Setup

In Claude Code, try:
- "Search for papers about content moderation"
- "Find works by Gillespie"

If you see search results with citations, you're all set!

## Troubleshooting

### "Not authenticated" error
Run `gcloud auth application-default login` again.

### "Permission denied" error
Contact Nic - your Google account may not have access yet.

### "ChromaDB not found" error
Re-run the download command from Step 4.

### Other issues
Contact Nic with the full error message.

## Available Tools

Once connected, you have access to:
- **search** - Semantic search across the Zotero library
- **get_item** - Get full text of a specific paper
- **get_similar_items** - Find related papers
- **search_papers** - Search OpenAlex for papers beyond our library
- **get_paper_citations** - Get papers citing a specific work

---

*Questions? Contact Nic at nic@suzor.net*
