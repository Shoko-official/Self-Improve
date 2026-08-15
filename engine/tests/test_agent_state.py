import tempfile,unittest
from pathlib import Path
from frontier_engine.agent_state import AgentStateStore
class AgentStateTests(unittest.TestCase):
 def test_project_scoped_plan_todos_and_memory_lifecycle(self)->None:
  with tempfile.TemporaryDirectory() as directory:
   store=AgentStateStore(Path(directory)/"agent.sqlite3");store.set_plan("a","Test plan");todo=store.add_todo("a","Run check");store.transition_todo(todo,"completed")
   memory=store.remember("a","User prefers local storage")
   self.assertEqual(store.plan("a"),"Test plan");self.assertEqual(store.todos("a")[0].state,"completed");self.assertEqual(store.search_memory("a","local"),("User prefers local storage",));self.assertEqual(store.search_memory("b","local"),())
   store.forget(memory);self.assertEqual(store.search_memory("a","local"),());store.close()
