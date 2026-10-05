FORMAT_NAME = "world-map-interchange"
FORMAT_VERSION = "0.1.0"
SUPPORTED_SERIES = ("0", "1")
SIDECAR_FORMAT = "world-map-interchange-sidecar"
MANIFEST_NAME = "manifest.json"
SIDECAR_SUFFIX = ".json"

CORE_KINDS = ("scalar", "categorical", "mask", "reference")
DATA_KINDS = ("scalar", "categorical", "mask")
KIND_DIRECTORY = {
    "scalar": "maps/",
    "categorical": "maps/",
    "mask": "maps/",
    "reference": "previews/",
}
VALIDITY_DIRECTORY = "masks/"
EXTENSION_KIND_DIRECTORY = "maps/"
RESERVED_NAMESPACES = ("wmi",)

INTERPOLATING_RESAMPLING = ("bilinear", "bicubic", "area_mean")
