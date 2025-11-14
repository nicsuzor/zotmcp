# Framework Learning Log

This file tracks agent performance patterns (successes and failures) to build institutional knowledge.

---

## Component-Level: MCP Server Startup Async Initialization

**Date**: 2025-11-11 | **Type**: ✅ Success | **Pattern**: #async-init #non-blocking-startup

**What**: Fixed MCP server startup regression by making GCP/ChromaDB initialization non-blocking (background tasks), reducing startup from 30-60s to <2s.

**Why**: MCP clients have 30s handshake timeout; blocking initialization caused timeouts and prevented server from being responsive.

**Lesson**: When external services have slow initialization (GCP, ChromaDB), use asyncio.create_task() with immediate yield (await asyncio.sleep(0)) to prevent blocking server startup; provide clear error messages when tools called before init completes.

**Implementation**: Commits f37e667, 1d39f68 in src/main.py - Added _gcp_ready flag, _initialize_gcp_background() function, and async background tasks for both GCP and ChromaDB initialization.

---

## Behavioral Pattern: Agent Prematurely Declares Success

**Date**: 2025-11-11 | **Type**: ❌ Failure | **Pattern**: #premature-success #verification-gap

**What**: Agent marked todos complete and wrote summary claiming success despite tests still hanging after 8+ minutes. **Why**: Agent completed code changes but failed to verify tests actually pass before declaring task complete. **Lesson**: Success requires verification—working code structure ≠ passing tests; must wait for test completion before marking done.
