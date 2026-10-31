import runpy
from pathlib import Path
import unittest


class LuaPolicyTests(unittest.TestCase):
    def test_policy_and_actual_callbacks(self):
        result = runpy.run_path(str(Path(__file__).with_name("lua_scenarios.py")))
        self.assertEqual(result["result"]["passed"], 30)
