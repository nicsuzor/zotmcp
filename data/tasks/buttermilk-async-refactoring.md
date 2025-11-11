---
title: Refactor Buttermilk for Async ChromaDB Operations
permalink: buttermilk-async-refactoring
type: task
status: inbox
priority: 2
tags:
  - buttermilk-framework
  - python-asyncio
  - chromadb
  - performance
created: 2025-11-11
project: zotmcp-mcp-server
---

# Refactor Buttermilk for Async ChromaDB Operations

## Context

Buttermilk's ensure_cache_initialized() performs synchronous ChromaDB operations that block the asyncio event loop for 10+ seconds. Need to wrap synchronous operations in asyncio.run_in_executor() to maintain server responsiveness during initialization.

## Observations

- [requirement] Must wrap collection.count() and other synchronous ChromaDB calls in asyncio.run_in_executor() #async-refactoring
- [impact] Currently blocks MCP server for 10+ seconds during ChromaDB initialization #performance-issue
- [scope] Upstream change required in buttermilk library, not zotmcp application #dependency-modification
- [alternative] Could implement lazy initialization to defer ChromaDB init until first search request #design-alternative
- [blocked] ZotMCP server responsiveness during init deferred until this is resolved #blocking-task

## Relations

- blocks [[ZotMCP MCP Server]]
- relates_to [[Buttermilk Async Blocking Issue]]
- enables [[MCP Server Responsiveness]]
