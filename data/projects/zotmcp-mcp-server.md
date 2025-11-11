---
title: ZotMCP MCP Server
permalink: zotmcp-mcp-server
type: project
tags:
  - mcp-protocol
  - zotero-integration
  - research-tools
  - python-asyncio
created: 2025-11-11
updated: 2025-11-11
---

# ZotMCP MCP Server

## Context

MCP server implementation providing Zotero library access via Model Context Protocol. Integrates ChromaDB for semantic search and GCP Cloud Storage for attachment retrieval. Built with Python asyncio and Buttermilk framework.

## Observations

- [architecture] Uses Model Context Protocol (MCP) JSON-RPC over stdio for communication #mcp-protocol
- [requirement] MCP protocol requires clean stdout - only valid JSON-RPC messages allowed #stdio-requirements
- [implementation] Uses Buttermilk framework for ChromaDB integration and caching #buttermilk-framework
- [performance] ChromaDB initialization synchronous operations cause 10+ second blocking during startup #performance-bottleneck
- [integration] Integrates with GCP Cloud Storage for PDF attachment retrieval #gcp-integration
- [testing] Integration test suite validates MCP protocol compliance and server behavior #test-coverage
- [bug-fixed] Structlog was polluting stdout with log messages, breaking JSON-RPC stream (fixed in aaea54f) #stdout-pollution
- [finding] User keypresses ('h', 'd', 'h') during debugging were testing responsiveness, not server output #debugging-insight
- [technical-debt] Buttermilk's ensure_cache_initialized() performs synchronous ChromaDB operations blocking event loop #async-refactoring-needed
- [decision] Deferred server responsiveness during ChromaDB init - requires upstream buttermilk library changes #deferred-optimization

## Relations

- implements [[Model Context Protocol]]
- integrates_with [[Zotero Research Library]]
- uses [[ChromaDB Semantic Search]]
- uses [[GCP Cloud Storage]]
- uses [[Buttermilk Framework]]
- blocked_by [[Buttermilk Async Refactoring]]
