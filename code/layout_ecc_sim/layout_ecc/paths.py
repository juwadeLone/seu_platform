"""Package data locations. Works both from a source checkout and a wheel
(where data/ ships inside the layout_ecc package)."""
import os

_PKG = os.path.dirname(os.path.abspath(__file__))


def data_dir():
    for cand in (os.path.join(_PKG, "data"),
                 os.path.join(_PKG, "..", "data")):
        if os.path.isdir(cand):
            return os.path.normpath(cand)
    return os.path.join(_PKG, "data")
