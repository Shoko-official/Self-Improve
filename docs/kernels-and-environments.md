# Kernels and environments

Frontier starts a persistent local Python worker using a line-delimited JSON protocol. Variables persist until restart; restart intentionally clears hidden state. Execution failures return their traceback as a failed result and are not converted to successful output.

R is disabled unless `Rscript` is discovered by a probe. This host currently has no R runtime. Jupyter integration and named scientific environments remain separate future work.

`frontierctl shell-exec` executes an exact argument vector only after the project has an active write grant for the working directory. It records the command, directory, timeout, exit code, stdout, stderr, or stable timeout/permission diagnostic in a durable job. This is not an operating-system sandbox and does not grant the webview shell access.
