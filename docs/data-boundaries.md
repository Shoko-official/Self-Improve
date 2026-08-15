# Data boundaries

Remote provider calls never occur implicitly. Before chat streaming, Frontier derives an egress preview with the provider, endpoint, text bytes, attachment names, and attachment bytes. The call is rejected until the caller sets an explicit approval.

Provider configuration does not write API keys to the store. The production shell must obtain them from the operating-system keychain.
