# Agent plans, todos, and memory

Plans, todos, and memories are scoped to a project and persisted separately. Todo transitions are explicit. Memory can be searched by project and deleted by identifier; the system does not retain inaccessible hidden state as user memory.

`frontierctl agent-workspace` exposes typed `list`, `read`, and `write` operations. Each operation receives an explicit project and workspace directory, accepts only relative non-traversing paths, and requires a matching active folder grant. The agent ledger retains an inspectable record of successful and failed calls. These tools do not provide unrestricted filesystem or shell access.
