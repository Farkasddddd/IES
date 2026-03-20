import os
import sys


WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from ies_shared.stage1_env import IESBilevelEnv


__all__ = ["IESBilevelEnv"]
