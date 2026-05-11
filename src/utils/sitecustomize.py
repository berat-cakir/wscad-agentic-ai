"""
Blocks the optional `powerfx` dependency at import time.

This is required because `agent_framework.declarative` attempts to import
`powerfx` if it is present, which in turn tries to load a .NET runtime via
pythonnet. Azure Functions (Python) do not support loading a .NET runtime,
and PowerFx is not used or supported in this environment.

By raising ModuleNotFoundError during import resolution, the framework
gracefully falls back to its pure-Python execution path without modifying
vendor code.
"""

import sys
import importlib.abc


class _BlockPowerFx(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "powerfx" or fullname.startswith("powerfx."):
            raise ModuleNotFoundError("powerfx is intentionally disabled")
        return None


if not any(isinstance(f, _BlockPowerFx) for f in sys.meta_path):
    sys.meta_path.insert(0, _BlockPowerFx())
