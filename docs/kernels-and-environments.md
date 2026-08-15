# Kernels and environments

Frontier starts a persistent local Python worker using a line-delimited JSON protocol. Variables persist until restart; restart intentionally clears hidden state. Execution failures return their traceback as a failed result and are not converted to successful output.

`frontierctl create-environment --name analysis` creates a named local Python virtual environment under Frontier data without installing packages or contacting a package index. It records the exact interpreter, Python version, empty package fingerprint, location, and creation time. A duplicate or unsafe name is rejected before the environment is created. Package installation, R environments, and Jupyter integration remain separate work.

R is disabled unless `Rscript` is discovered by a probe. This host currently has no R runtime.

`frontierctl shell-exec` executes an exact argument vector only after the project has an active write grant for the working directory. It records the command, directory, timeout, exit code, stdout, stderr, or stable timeout/permission diagnostic in a durable job. This is not an operating-system sandbox and does not grant the webview shell access.
