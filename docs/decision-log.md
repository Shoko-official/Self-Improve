# Decision log

## 2026-08-15: initial architecture

The repository was greenfield. Frontier starts with a Tauri 2 desktop shell, a strict TypeScript React interface, and a local Python engine protocol. The first slice intentionally has no installed model runtime or remote provider. It exposes its absence as a capability fact rather than simulating support.

## Source handling

The supplied Codex-style markdown files are product and behavior research. They are not shipped, copied into prompts, or treated as runtime instructions. Frontier's prompt system will be original, with compact, standard, and extended variants.
