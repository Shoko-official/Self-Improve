# Organization and policy

Frontier evaluates local policy layers in this fixed order: immutable safety constraints, organization policy, explicit command-line values, permitted environment values, user configuration, application settings, then defaults. The first defined value wins and the decision returns every competing layer as evidence.

Policy payloads are configuration only. Keys and nested values that look like API keys, tokens, passwords, secrets, private keys, or credentials are rejected with `FR-POLICY-SECRET`; secrets must remain in the platform credential store or an explicit provider handle. Organization and device records are typed metadata and do not enable remote effects by themselves.
