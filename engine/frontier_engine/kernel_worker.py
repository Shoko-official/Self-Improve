"""Line-delimited JSON worker preserving a Python namespace between requests."""

from __future__ import annotations

import contextlib
import io
import json
import traceback

namespace: dict[str, object] = {"__name__": "__frontier_kernel__"}

for line in iter(input, ""):
    request = json.loads(line)
    stdout, stderr = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exec(request["code"], namespace)
        response = {"id": request["id"], "state": "succeeded", "stdout": stdout.getvalue(), "stderr": stderr.getvalue()}
    except BaseException:
        response = {"id": request["id"], "state": "failed", "stdout": stdout.getvalue(), "stderr": stderr.getvalue(), "error": traceback.format_exc()}
    print(json.dumps(response), flush=True)
