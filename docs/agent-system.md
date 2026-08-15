# Agent plans, todos, and memory

Plans, todos, and memories are scoped to a project and persisted separately. Todo transitions are explicit. Memory can be searched by project and deleted by identifier; the system does not retain inaccessible hidden state as user memory.

`frontierctl agent-workspace` exposes typed `list`, `read`, and `write` operations. Each operation receives an explicit project and workspace directory, accepts only relative non-traversing paths, and requires a matching active folder grant. The agent ledger retains an inspectable record of successful and failed calls. These tools do not provide unrestricted filesystem or shell access.

`frontierctl agent-run --project-id ID --model MODEL --prompt TEXT` runs the explicitly named installed local Ollama model for an active project. `frontierctl agent-activity --project-id ID` returns the durable plan, todos, and tool-call ledger for that active project. Runtime failures are recorded in that ledger and are not converted into output.

The desktop Agent surface selects an active local project and displays the same plan, todo, output, and activity records. It cannot select an archived project.
