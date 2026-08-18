# Host integrations

Shoko's LLM discovers integrations already installed on the host. It does not copy remote system prompts or claim that a configured integration is connected.

## Skills

The engine scans bounded Codex and agent skill roots plus enabled plugin skill folders. A skill appears only when `SKILL.md` stays inside an approved root, is valid UTF-8, remains below 256 KiB, and contains bounded `name` and `description` frontmatter. The public catalog exposes a relative source identity and SHA-256, never an unrestricted filesystem path.

A user may select one validated skill in the chat composer. The engine reloads that exact manifest, records its identifier and hash, and contributes its instructions to the local model prompt. Referenced files and tools remain unavailable unless another runtime capability provides them. Skill content is not sent to a remote provider by this path.

## Extensions

The extension catalog reads enabled Codex plugin manifests from the installed plugin cache. It shows only the newest installed version of a plugin that contributes at least one validated skill. The catalog reports only the capability Shoko's LLM can currently use, `skill.instructions`. Apps, tools, or connectors that Shoko's LLM cannot execute stay hidden.

## MCP clients

The engine reads configured Codex MCP servers and enabled plugin MCP manifests. Configuration discovery never returns command arguments, environment values, bearer tokens, request headers, or credential-bearing URLs.

Verification requires explicit approval because it may start a configured process or access the network. Each candidate must complete MCP `initialize` and `tools/list` within a bounded timeout. Only successful servers and their sanitized tool schemas appear in the desktop registry. Failed candidates remain hidden and produce a stable diagnostic code.

Every MCP tool call starts a fresh verified session, checks that the requested tool is currently listed, requires a separate approval, bounds the response to 1 MiB, and records only safe event metadata. Both newline-delimited stdio and Streamable HTTP transports are supported. HTTP requests preserve the returned `Mcp-Session-Id`, send the negotiated `MCP-Protocol-Version`, and attempt to close stateful sessions after use.

## Current host evidence

On 2026-08-18, the local probe detected seven configured servers. `codex/node_repl` verified three tools and `codex/openaiDeveloperDocs` verified five tools. Five candidates were hidden because their process, credential, or HTTP contract was unavailable. This evidence is host-specific and is not a cross-platform availability claim.
