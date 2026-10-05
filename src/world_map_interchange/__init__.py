"""Reference tools for the experimental World Map Interchange (WMI) draft format."""

from .constants import FORMAT_VERSION
from .scalar import (
    EncodingRangeError,
    choose_range,
    decode,
    encode,
    quantization_step,
)
from .validate import validate

__all__ = [
    "EncodingRangeError",
    "choose_range",
    "decode",
    "encode",
    "quantization_step",
    "validate",
    "__version__",
    "FORMAT_VERSION",
]

__version__ = "0.1.0"
