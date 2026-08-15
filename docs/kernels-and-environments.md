# Kernels and environments

Frontier starts a persistent local Python worker using a line-delimited JSON protocol. Variables persist until restart; restart intentionally clears hidden state. Execution failures return their traceback as a failed result and are not converted to successful output.

R is disabled unless `Rscript` is discovered by a probe. This host currently has no R runtime. Jupyter integration and named scientific environments remain separate future work.
