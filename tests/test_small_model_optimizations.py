# SPDX-FileCopyrightText: 2026 Blender Authors
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Unit tests for 7-10B small model optimizations in blender_mcp:
- Traceback truncation
- RST markup cleaning
- Automatic fallback for missing result dict
- Prompt and Tools profiles
"""

import os
import sys
import unittest
from unittest.mock import MagicMock

# Mock bpy for standalone unit testing outside of Blender
if 'bpy' not in sys.modules:
    mock_bpy = MagicMock()
    mock_bpy.app.timers = MagicMock()
    mock_bpy_ops = MagicMock()
    mock_bpy_ops._op_create_function = MagicMock(return_value=lambda m, f: MagicMock())
    mock_bpy.ops = mock_bpy_ops
    sys.modules['bpy'] = mock_bpy
    sys.modules['bpy.ops'] = mock_bpy_ops
    sys.modules['bpy.props'] = MagicMock()
    sys.modules['bpy.types'] = MagicMock()

# Ensure add-on and mcp package are in import path for testing
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(repo_root, "addon"))
sys.path.insert(0, os.path.join(repo_root, "mcp"))


class TestTracebackTruncation(unittest.TestCase):
    def test_format_truncated_traceback(self):
        from blender_mcp_addon.mcp_to_blender_server import format_truncated_traceback

        tb_long = """Traceback (most recent call last):
  File "/path/to/addon/blender_mcp_addon/mcp_to_blender_server.py", line 223, in _execute_code
    exec(code, namespace)
  File "/path/to/addon/blender_mcp_addon/weak_sandbox.py", line 50, in wrapper
    return func(*args, **kwargs)
  File "<string>", line 5, in <module>
AttributeError: 'NoneType' object has no attribute 'name'"""

        truncated = format_truncated_traceback(tb_long)
        self.assertNotIn("mcp_to_blender_server.py", truncated)
        self.assertNotIn("weak_sandbox.py", truncated)
        self.assertIn("Traceback", truncated)
        self.assertIn('File "<string>", line 5, in <module>', truncated)
        self.assertIn("AttributeError: 'NoneType' object has no attribute 'name'", truncated)

    def test_short_traceback_unchanged(self):
        from blender_mcp_addon.mcp_to_blender_server import format_truncated_traceback

        tb_short = """Traceback (most recent call last):
  File "<string>", line 1, in <module>
ZeroDivisionError: division by zero"""

        self.assertEqual(format_truncated_traceback(tb_short), tb_short)


class TestRSTMarkupCleaning(unittest.TestCase):
    def test_clean_rst_markup(self):
        from blmcp.tools_helpers.rst_parse_docs import clean_rst_markup

        raw_rst = """
See :class:`~bpy.types.Object` and :ref:`some-label` for details.
Check :func:`bpy.ops.mesh.primitive_cube_add` or :mod:`bpy.data`.

:param name: The name of the object.
:type name: str
:returns: The created object.
"""
        cleaned = clean_rst_markup(raw_rst)
        self.assertNotIn(":class:", cleaned)
        self.assertNotIn(":ref:", cleaned)
        self.assertNotIn(":func:", cleaned)
        self.assertNotIn(":mod:", cleaned)
        self.assertIn("bpy.types.Object", cleaned)
        self.assertIn("some-label", cleaned)
        self.assertIn("Param name:", cleaned)
        self.assertIn("Type name:", cleaned)
        self.assertIn("Returns:", cleaned)


class TestResultFallback(unittest.TestCase):
    def test_execute_code_result_fallback(self):
        from blender_mcp_addon.mcp_to_blender_server import _execute_code

        # Code that does not set `result`
        code_no_result = "a = 1 + 2"
        exec_res = _execute_code(code_no_result, strict_json=True)
        self.assertEqual(exec_res.response.get("status"), "ok")
        self.assertEqual(exec_res.response.get("result"), {"status": "ok"})

        # Code that sets `result = None`
        code_result_none = "a = 5\nresult = None"
        exec_res = _execute_code(code_result_none, strict_json=True)
        self.assertEqual(exec_res.response.get("status"), "ok")
        self.assertEqual(exec_res.response.get("result"), {"status": "ok"})

        # Code that sets explicit dictionary
        code_explicit_dict = "result = {'count': 42}"
        exec_res = _execute_code(code_explicit_dict, strict_json=True)
        self.assertEqual(exec_res.response.get("status"), "ok")
        self.assertEqual(exec_res.response.get("result"), {"count": 42})

    def test_execute_code_without_import_bpy(self):
        from blender_mcp_addon.mcp_to_blender_server import _execute_code

        # Code that uses `bpy` directly without `import bpy`
        code_no_import = "result = {'has_bpy': bpy is not None}"
        exec_res = _execute_code(code_no_import, strict_json=True)
        self.assertEqual(exec_res.response.get("status"), "ok")
        self.assertEqual(exec_res.response.get("result"), {"has_bpy": True})


if __name__ == "__main__":
    unittest.main(exit=False)
