"""layout_ecc: placement-aware strike-kernel proxy (M3 viewer + geometry)."""

__version__ = "0.1.0"

from .kernel import kernel_axes
from .geometry import ellipse_intersects_rect, point_in_ellipse, classify_hits
from .layout_import import load_primitive_map
from .layout_synth import synthesize
from .stage_tags import tag
from .strike import run_strike, g4_presets
from .functional import inject_and_classify, ensure_golden
from .functional_mapper import map_flipped

__all__ = [
    "kernel_axes", "ellipse_intersects_rect", "point_in_ellipse",
    "classify_hits", "synthesize", "load_primitive_map", "tag",
    "run_strike", "g4_presets", "inject_and_classify", "ensure_golden",
    "map_flipped", "__version__",
]
