---
title: Buttermilk Async Blocking Issue
permalink: buttermilk-async-blocking
type: note
tags:
  - python-asyncio
  - chromadb
  - performance
  - technical-debt
created: 2025-11-11
---

# Buttermilk Async Blocking Issue

## Context

Buttermilk framework's ensure_cache_initialized() function performs synchronous ChromaDB operations (collection.count()) that block the asyncio event loop for 10+ seconds during initialization, preventing server responsiveness.

## Observations

- [root-cause] ensure_cache_initialized() calls synchronous ChromaDB collection.count() operation #blocking-operation
- [performance] ChromaDB collection.count() takes 10+ seconds on large collections #performance-measurement
- [impact] Calling ensure_cache_initialized() in async context blocks entire event loop #event-loop-blocking
- [antipattern] Awaiting ensure_cache_initialized() in conftest.py caused integration tests to hang #test-fixture-issue
- [solution-required] Needs asyncio.run_in_executor() wrapper for synchronous ChromaDB operations #refactoring-needed
- [alternative] Lazy initialization - defer ChromaDB init until first search request #design-alternative
- [upstream] Requires changes to buttermilk library, not fixable in zotmcp application code #dependency-issue
- [workaround] Reverted conftest.py changes, avoiding await ensure_cache_initialized() in test fixtures #temporary-workaround

## Relations

- blocks [[ZotMCP MCP Server]]
- requires [[Buttermilk Async Refactoring]]
- affects [[ChromaDB Semantic Search]]
- relates_to [[Python Asyncio Event Loop]]
