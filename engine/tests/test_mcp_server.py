import unittest
from frontier_engine.mcp_server import handle
class McpServerTests(unittest.TestCase):
 def test_initialization_and_tool_listing_are_typed(self)->None:
  initialized=handle({"jsonrpc":"2.0","id":1,"method":"initialize"}); tools=handle({"jsonrpc":"2.0","id":2,"method":"tools/list"})
  self.assertEqual(initialized["result"]["capabilities"]["tools"]["listChanged"],False); self.assertTrue(tools["result"]["tools"][0]["annotations"]["readOnlyHint"])
 def test_call_returns_structured_content_and_rejects_unknown_tool(self)->None:
  result=handle({"id":3,"method":"tools/call","params":{"name":"frontier_get_capability_report","arguments":{}}}); bad=handle({"id":4,"method":"tools/call","params":{"name":"rm_all"}})
  self.assertEqual(result["result"]["structuredContent"]["status"],"healthy"); self.assertEqual(bad["error"]["code"],-32602)

 def test_registry_tools_are_read_only_and_structured(self)->None:
  tools=handle({"id":5,"method":"tools/list"})["result"]["tools"]
  names={tool["name"] for tool in tools}
  self.assertIn("frontier_list_scientific_connectors",names)
  self.assertIn("frontier_list_scientific_skills",names)
  self.assertTrue(all(tool["annotations"]["readOnlyHint"] for tool in tools))
  connectors=handle({"id":6,"method":"tools/call","params":{"name":"frontier_list_scientific_connectors","arguments":{}}})
  skills=handle({"id":7,"method":"tools/call","params":{"name":"frontier_list_scientific_skills","arguments":{}}})
  self.assertTrue(connectors["result"]["structuredContent"]["connectors"])
  self.assertTrue(skills["result"]["structuredContent"]["skills"])
  self.assertEqual(handle({"id":8,"method":"tools/call","params":{"name":"frontier_list_scientific_skills","arguments":{"write":True}}})["error"]["code"],-32602)
