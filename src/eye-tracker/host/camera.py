"""Camera module - re-exported from common."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from common.camera import Camera

__all__ = ["Camera"]
