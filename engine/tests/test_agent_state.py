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
 def test_todo_can_be_edited_paused_and_deleted(self)->None:
  with tempfile.TemporaryDirectory() as directory:
   store=AgentStateStore(Path(directory)/"agent.sqlite3");todo=store.add_todo("a","Draft")
   store.update_todo(todo,"Review evidence");store.transition_todo(todo,"paused")
   self.assertEqual(store.todos("a")[0].text,"Review evidence");self.assertEqual(store.todos("a")[0].state,"paused")
   store.delete_todo(todo);self.assertEqual(store.todos("a"),());store.close()
 def test_goal_can_be_edited_paused_completed_and_deleted(self)->None:
  with tempfile.TemporaryDirectory() as directory:
   store=AgentStateStore(Path(directory)/"agent.sqlite3");store.set_plan("a","Collect evidence")
   store.set_plan("a","Review evidence");store.transition_plan("a","paused")
   self.assertEqual(store.plan("a"),"Review evidence");self.assertEqual(store.plan_state("a"),"paused")
   store.transition_plan("a","completed");self.assertEqual(store.plan_state("a"),"completed")
   store.delete_plan("a");self.assertIsNone(store.plan("a"));self.assertIsNone(store.plan_state("a"));store.close()
