---
title: MCP Stdout Requirements
permalink: mcp-stdout-requirements
type: note
tags:
  - mcp-protocol
  - json-rpc
  - stdio-communication
  - debugging
created: 2025-11-11
---

# MCP Stdout Requirements

## Context

Model Context Protocol (MCP) uses JSON-RPC over stdio for client-server communication. Stdout must contain ONLY valid JSON-RPC messages - any pollution causes parse errors and client disconnection.

## Observations

- [requirement] MCP clients expect stdout to contain exclusively JSON-RPC formatted messages #protocol-constraint
- [antipattern] Logging frameworks writing to stdout will pollute JSON-RPC stream causing parse errors #common-mistake
- [solution] All logging must be redirected to stderr using structlog PrintLoggerFactory(file=sys.stderr) #logging-configuration
- [debugging] User keypresses appearing in debug output indicate terminal interaction, not server stdout pollution #debug-interpretation
- [validation] Test suite can validate stdout cleanliness by capturing subprocess output during startup #integration-testing
- [impact] Stdout pollution manifests as JSON parse errors from MCP client during initialization #error-symptoms

## Relations

- part_of [[Model Context Protocol]]
- affects [[ZotMCP MCP Server]]
- resolved_by [[Commit aaea54f]]
