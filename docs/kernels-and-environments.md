# Kernels and environments

Frontier starts a persistent local Python or R worker using a line-delimited JSON protocol. Variables persist until restart; restart intentionally clears hidden state. Execution failures return their traceback as a failed result and are not converted to successful output.

The authenticated loopback control plane exposes `kernel.execute`, `kernel.restart`, and `kernel.status` for active projects. Pass `language: "python"` or `language: "r"`; the default is Python. It owns one worker per project and language while the service is running, so sequential calls for the same project share a namespace. Stopping the service stops every managed kernel. An unavailable R runtime returns `FR-KERNEL-R-NOT-FOUND` and is never substituted with Python.

`frontierctl create-environment --name analysis` creates a named local Python virtual environment under Frontier data without contacting a package index. It records the exact interpreter, Python version, empty package fingerprint, location, and creation time. `frontierctl install-packages --name analysis --package numpy==2.0` is the explicit package-install boundary: it uses that environment's interpreter, records the installed name/version map and deterministic fingerprint, and rejects installer flags passed as package specs. A duplicate or unsafe name is rejected before the environment is created. R environments and Jupyter integration remain separate work.

R is disabled unless `Rscript` is discovered by a probe. This host currently has no R runtime.

`frontierctl shell-exec` executes an exact argument vector only after the project has an active write grant for the working directory. It records the command, directory, timeout, exit code, stdout, stderr, or stable timeout/permission diagnostic in a durable job. This is not an operating-system sandbox and does not grant the webview shell access.
