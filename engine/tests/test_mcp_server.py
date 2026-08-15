import unittest
from frontier_engine.mcp_server import handle
class McpServerTests(unittest.TestCase):
 def test_initialization_and_tool_listing_are_typed(self)->None:
  initialized=handle({"jsonrpc":"2.0","id":1,"method":"initialize"}); tools=handle({"jsonrpc":"2.0","id":2,"method":"tools/list"})
  self.assertEqual(initialized["result"]["capabilities"]["tools"]["listChanged"],False); self.assertTrue(tools["result"]["tools"][0]["annotations"]["readOnlyHint"])
 def test_call_returns_structured_content_and_rejects_unknown_tool(self)->None:
  result=handle({"id":3,"method":"tools/call","params":{"name":"frontier_get_capability_report","arguments":{}}}); bad=handle({"id":4,"method":"tools/call","params":{"name":"rm_all"}})
  self.assertEqual(result["result"]["structuredContent"]["status"],"healthy"); self.assertEqual(bad["error"]["code"],-32602)
