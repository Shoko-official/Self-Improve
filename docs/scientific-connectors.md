# Scientific connectors and MCP

Frontier's local MCP server uses stdio JSON-RPC and declares typed read-only tools for the host capability report, scientific connector registry, and scientific skill registry. Each descriptor states capabilities, availability, and network boundary. Connector invocation must still pass Frontier's scoped permission ledger before any operation with data or side effects is introduced; the registry itself never performs network access or writes.
