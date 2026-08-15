# Remote compute

Every plan contains an exact command, target, CPU, memory, timeout, cost estimate, and data-egress estimate. A remote SSH, SLURM, or cloud plan is rejected until explicitly approved. Approved SSH plans use an argument-vector `ssh endpoint -- command...`; approved SLURM plans use `sbatch --parsable` with explicit CPU, memory, timeout, working directory, and a quoted command payload. Local and remote execution records terminal state, stdout, stderr, timeout, executor, or exit diagnostics.

SSH and SLURM execution are available when their host executors are installed; tests mock the subprocess boundary and never contact a cluster. Cloud remains explicitly unconfigured and returns `FR-REMOTE-CLOUD-NOT-CONFIGURED`.
