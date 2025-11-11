---
title: 2025-11-11 Supervisor Session - MCP Server Init Fix
permalink: 2025-11-11-supervisor-session
type: session
tags:
  - supervisor-session
  - bug-fix
  - tdd-cycle
  - mcp-protocol
date: 2025-11-11
---

# 2025-11-11 Supervisor Session - MCP Server Init Fix

## Context

Supervisor session focused on fixing MCP server initialization issues: JSON parse errors from MCP client and test fixture hanging. Successfully completed 1 TDD cycle resolving stdout pollution.

## Session Summary

### Goal

Fix MCP server initialization issues causing JSON parse errors and test fixture hanging.

### Cycles Completed

1 TDD cycle: stdout pollution fix

### Commits Created

- aaea54f: "fix: Configure structlog to write to stderr to prevent stdout pollution"
- 73c84bb: "update(bmem): Document MCP server stdout pollution fix and async blocking findings"

### Tests Added

- test_stdout_clean_during_startup (validates no stdout pollution during server init)

### Files Modified

- src/main.py: Added structlog stderr configuration
- src/tests/test_async_init.py: Added stdout validation test
- data/: Created bmem documentation files

## Success Criteria Status

1. No JSON parse errors from MCP client during startup: ✅ RESOLVED
2. Integration tests pass: ✅ PASSING (10.7s)
3. Server responsiveness during ChromaDB init: ⏸️ DEFERRED (requires buttermilk changes)

## Key Findings

### Root Cause Analysis

1. **User keypresses**: The 'h', 'd', 'h' characters observed were terminal keypresses testing responsiveness, NOT server output
2. **Stdout pollution**: Structlog was writing to stdout by default, polluting JSON-RPC stream
3. **Fix**: Configure PrintLoggerFactory(file=sys.stderr) to redirect all logs to stderr
4. **Test fixture blocking**: Conftest.py changes calling await ensure_cache_initialized() blocked tests - reverted
5. **Buttermilk blocking**: ensure_cache_initialized() performs synchronous ChromaDB operations (collection.count() takes 10+ seconds)

### Architectural Insights

- MCP protocol requires clean stdout - only JSON-RPC messages allowed
- ChromaDB synchronous operations block asyncio event loop
- Buttermilk needs asyncio.run_in_executor() wrapper for sync operations

## Follow-up Tasks

Created task: [[Buttermilk Async Refactoring]]

- Modify buttermilk library to use asyncio.run_in_executor() for synchronous ChromaDB operations
- Alternative: Implement lazy initialization (defer ChromaDB init until first search request)

## Observations

- [process] Successfully completed 1 TDD cycle with test-first approach #tdd-methodology
- [debugging] User keypresses during debugging revealed misinterpretation of output source #debugging-insight
- [protocol] MCP protocol stdio requirements are strict - no logging to stdout allowed #protocol-constraint
- [performance] ChromaDB initialization is significant bottleneck (10+ seconds) #performance-issue
- [decision] Deferred responsiveness optimization to focus on working server first #pragmatic-decision
- [upstream] Blocking behavior requires upstream buttermilk changes, not application-level fixes #dependency-management
- [testing] Integration test validates stdout cleanliness during server initialization #test-coverage
- [commit-quality] Created atomic commit with clear message and co-authorship attribution #git-best-practices

## Relations

- completed [[Commit aaea54f]]
- created [[Buttermilk Async Refactoring]]
- documented [[ZotMCP MCP Server]]
- discovered [[MCP Stdout Requirements]]
- identified [[Buttermilk Async Blocking Issue]]
