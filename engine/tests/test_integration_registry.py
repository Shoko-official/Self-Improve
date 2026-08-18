import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from frontier_engine.agent_runner import run_local_agent
from frontier_engine.agent_state import AgentStateStore
from frontier_engine.integration_registry import IntegrationLedger, apply_skill_instructions, call_mcp_tool, discover_extensions, discover_skills, probe_mcp_servers


class IntegrationRegistryTests(unittest.TestCase):
    def test_skills_and_enabled_plugin_extensions_are_validated_and_loadable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            codex = root / "codex"
            skill = codex / "skills" / "review"
            skill.mkdir(parents=True)
            skill.joinpath("SKILL.md").write_text("---\nname: Review\ndescription: Review evidence carefully.\n---\n\nUse exact evidence.\n", encoding="utf-8")
            invalid = codex / "skills" / "invalid"
            invalid.mkdir()
            invalid.joinpath("SKILL.md").write_text("No frontmatter", encoding="utf-8")
            plugin_root = codex / "plugins" / "cache"
            plugin = plugin_root / "market" / "writer" / "2.0.0"
            plugin.joinpath(".codex-plugin").mkdir(parents=True)
            plugin.joinpath("skills", "write").mkdir(parents=True)
            plugin.joinpath(".codex-plugin", "plugin.json").write_text(json.dumps({"name": "writer", "version": "2.0.0", "license": "MIT", "skills": "./skills"}), encoding="utf-8")
            plugin.joinpath("skills", "write", "SKILL.md").write_text("---\nname: Write\ndescription: Write a concise report.\n---\n\nStay concise.\n", encoding="utf-8")
            older = plugin_root / "market" / "writer" / "1.0.0"
            older.joinpath(".codex-plugin").mkdir(parents=True)
            older.joinpath(".codex-plugin", "plugin.json").write_text(json.dumps({"name": "writer", "version": "1.0.0", "license": "MIT"}), encoding="utf-8")
            config = codex / "config.toml"
            config.write_text('[plugins."writer@market"]\nenabled = true\n', encoding="utf-8")

            skills = discover_skills(config_path=config, plugin_root=plugin_root)
            self.assertTrue({"Review", "Write"}.issubset({item["name"] for item in skills}))
            self.assertNotIn("invalid", {item["name"] for item in skills})
            self.assertTrue(all("_path" not in item for item in skills))
            plugin_skill = next(item for item in skills if item["name"] == "Write")
            with patch.dict(os.environ, {"CODEX_HOME": str(codex)}, clear=False):
                compiled, selected = apply_skill_instructions("Draft", [plugin_skill["id"]])
            self.assertIn("Stay concise.", compiled)
            self.assertEqual(selected[0]["sha256"], plugin_skill["sha256"])
            extensions = discover_extensions(config, plugin_root)
            self.assertEqual(extensions[0]["id"], "writer@market")
            self.assertEqual(extensions[0]["version"], "2.0.0")
            self.assertEqual(extensions[0]["availability"], "installed-and-loadable")

    def test_selected_skill_is_recorded_by_a_real_agent_run_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / "skill"
            skill.mkdir()
            skill.joinpath("SKILL.md").write_text("---\nname: Local\ndescription: Local instructions.\n---\n\nBe precise.\n", encoding="utf-8")
            with patch.dict(os.environ, {"SHOKO_SKILLS_ROOTS": str(root)}, clear=False):
                skill_id = str(discover_skills()[0]["id"])
                state = AgentStateStore(root / "agent.sqlite3")
                result = run_local_agent(state, "project", "fixture", "Explain", iter(["done"]), [skill_id])
                request = json.loads(state.tool_calls("project")[0]["request"])
                state.close()
            self.assertEqual(result["skills"][0]["id"], skill_id)
            self.assertEqual(request["skills"][0]["id"], skill_id)

    def test_selected_skills_are_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index in range(5):
                skill = root / f"skill-{index}"
                skill.mkdir()
                skill.joinpath("SKILL.md").write_text(
                    f"---\nname: Skill {index}\ndescription: Bounded instructions.\n---\n\nBe precise.\n",
                    encoding="utf-8",
                )
            with patch.dict(os.environ, {"SHOKO_SKILLS_ROOTS": str(root)}, clear=False):
                skill_ids = [str(item["id"]) for item in discover_skills()]
                with self.assertRaisesRegex(ValueError, "FR-SKILL-SELECTION-LIMIT"):
                    apply_skill_instructions("Draft", skill_ids)

    def test_stdio_mcp_probe_and_tool_call_require_approval_and_return_structured_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            server = root / "server.py"
            server.write_text(
                "import json,sys\n"
                "for line in sys.stdin:\n"
                " request=json.loads(line); method=request.get('method'); identifier=request.get('id')\n"
                " if identifier is None: continue\n"
                " if method=='initialize': result={'protocolVersion':'2025-06-18','capabilities':{'tools':{}},'serverInfo':{'name':'fixture','version':'1'}}\n"
                " elif method=='tools/list': result={'tools':[{'name':'echo','title':'Echo','inputSchema':{'type':'object'},'annotations':{'readOnlyHint':True}}]}\n"
                " elif method=='tools/call': result={'content':[{'type':'text','text':request['params']['arguments']['text']}],'structuredContent':request['params']['arguments']}\n"
                " else: result={}\n"
                " print(json.dumps({'jsonrpc':'2.0','id':identifier,'result':result}),flush=True)\n",
                encoding="utf-8",
            )
            config = root / "config.toml"
            config.write_text(f"[mcp_servers.fixture]\ncommand = {json.dumps(sys.executable)}\nargs = [{json.dumps(str(server))}]\nstartup_timeout_sec = 3\n", encoding="utf-8")
            with self.assertRaises(PermissionError):
                probe_mcp_servers(False, config)
            probe = probe_mcp_servers(True, config)
            self.assertEqual(probe["connectors"][0]["capabilities"], ["echo"])
            with self.assertRaises(PermissionError):
                call_mcp_tool("codex/fixture", "echo", {"text": "hello"}, False, config)
            called = call_mcp_tool("codex/fixture", "echo", {"text": "hello"}, True, config)
            self.assertEqual(called["result"]["structuredContent"], {"text": "hello"})

    def test_streamable_http_mcp_transport_is_initialized_before_listing(self) -> None:
        class Handler(BaseHTTPRequestHandler):
            deleted = False

            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", "0"))
                request = json.loads(self.rfile.read(length))
                if request["method"] != "initialize" and self.headers.get("MCP-Protocol-Version") != "2025-06-18":
                    self.send_response(400)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                if request.get("id") is None:
                    self.send_response(202)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                result = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}, "serverInfo": {"name": "http", "version": "1"}} if request["method"] == "initialize" else {"tools": [{"name": "read", "inputSchema": {"type": "object"}}]}
                body = json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                if request["method"] == "initialize":
                    self.send_header("Mcp-Session-Id", "fixture")
                self.end_headers()
                self.wfile.write(body)

            def do_DELETE(self) -> None:
                Handler.deleted = True
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, format: str, *args: object) -> None:
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                config = Path(directory) / "config.toml"
                config.write_text(f'[mcp_servers.http]\nurl = "http://127.0.0.1:{server.server_port}/mcp"\ntool_timeout_sec = 2\n', encoding="utf-8")
                result = probe_mcp_servers(True, config)
                self.assertEqual(result["connectors"][0]["capabilities"], ["read"])
                self.assertTrue(Handler.deleted)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)

    def test_integration_ledger_persists_only_safe_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = IntegrationLedger(Path(directory) / "integrations.sqlite3")
            ledger.record("codex/example", "probe", "failed", "FR-MCP-TIMEOUT", "project")
            event = ledger.events("project")[0]
            ledger.close()
            self.assertEqual(event["diagnostic_code"], "FR-MCP-TIMEOUT")
            self.assertNotIn("secret", event)


if __name__ == "__main__":
    unittest.main()
