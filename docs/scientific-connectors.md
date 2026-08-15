# Scientific connectors and MCP

Frontier's initial local MCP server uses stdio JSON-RPC and declares a read-only capability-report tool with input/output schemas and behavior annotations. Connector invocation must still pass Frontier's scoped permission ledger before any operation with data or side effects is introduced.
