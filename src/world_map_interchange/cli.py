"""Command-line interface: ``wmi validate | inspect | pack | rehash | sidecars | encode | decode``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from . import __version__
from . import png as pngmod
from . import scalar as scalarmod
from .bundle import Bundle, pack, rehash, write_sidecars
from .inspect import render, summarize
from .jsonutil import loads_strict, schema_errors
from .package import Limits, PackageError
from .validate import validate

EXIT_OK, EXIT_INVALID, EXIT_USAGE = 0, 1, 2


def _limits(args) -> Limits:
    limits = Limits()
    if getattr(args, "max_pixels", None):
        limits.max_pixels = args.max_pixels
    if getattr(args, "max_file_mb", None):
        limits.max_file_bytes = int(args.max_file_mb * 1024**2)
    return limits


def _capabilities(args) -> dict | None:
    if not getattr(args, "consumer", None):
        return None
    caps = loads_strict(Path(args.consumer).read_bytes())
    errs = schema_errors(caps, "capabilities.schema.json")
    if errs:
        raise SystemExit(f"error: capability profile {args.consumer} is invalid: " + "; ".join(f"{loc or '/'}: {m}" for loc, m in errs))
    return caps


def _print_report(report, out=None) -> None:
    out = out or sys.stdout
    print(f"Validating {report.target} ({report.container or 'unknown container'})", file=out)
    for issue in report.issues:
        print("  " + issue.render(), file=out)
    if report.layers:
        name = report.consumer["name"] if report.consumer else "?"
        print(f"Layer support for consumer: {name}", file=out)
        for s in report.layers:
            reason = f" - {'; '.join(s.reasons)}" if s.reasons else ""
            print(f"  {s.status:11} {s.id} ({s.kind}{', ' + s.quantity if s.quantity else ''}){reason}", file=out)
        if report.consumer and report.consumer["required_quantities_missing"]:
            print("  workflow requirements not met: " + ", ".join(report.consumer["required_quantities_missing"]), file=out)
    verdict = "CONFORMANT" if report.conformant else "NOT CONFORMANT"
    print(f"Result: {verdict} ({len(report.errors)} errors, {len(report.warnings)} warnings)", file=out)


def cmd_validate(args) -> int:
    report = validate(args.path, limits=_limits(args), capabilities=_capabilities(args))
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        _print_report(report)
    if args.strict and report.warnings:
        return EXIT_INVALID
    return EXIT_OK if report.conformant else EXIT_INVALID


def cmd_inspect(args) -> int:
    summary = summarize(args.path, limits=_limits(args), capabilities=_capabilities(args))
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(render(summary))
        if not summary["validation"]["conformant"]:
            print("Run 'wmi validate' for details.")
    return EXIT_OK if summary["validation"]["conformant"] else EXIT_INVALID


def cmd_pack(args) -> int:
    if not Path(args.directory).is_dir():
        print(f"error: {args.directory} is not a directory", file=sys.stderr)
        return EXIT_USAGE
    report = validate(args.directory)
    if not report.conformant:
        _print_report(report, out=sys.stderr)
        print("error: refusing to pack a non-conformant package", file=sys.stderr)
        return EXIT_INVALID
    names = pack(args.directory, args.output, include_sidecars=not args.no_sidecars)
    zreport = validate(args.output)
    if not zreport.conformant:
        _print_report(zreport, out=sys.stderr)
        return EXIT_INVALID
    print(f"Wrote {args.output} ({len(names)} entries)")
    return EXIT_OK


def cmd_rehash(args) -> int:
    changed = rehash(args.directory)
    print(f"Updated {len(changed)} hash(es)" + (": " + ", ".join(changed) if changed else ""))
    return EXIT_OK


def cmd_sidecars(args) -> int:
    written = write_sidecars(args.directory)
    print(f"Wrote {len(written)} sidecar(s) generated from manifest.json")
    return EXIT_OK


def _load_array(path: str) -> np.ndarray:
    p = Path(path)
    if p.suffix == ".npy":
        return np.load(p, allow_pickle=False)
    return np.loadtxt(p, delimiter=",", ndmin=2)


def cmd_encode(args) -> int:
    values = _load_array(args.input).astype(np.float64)
    valid = None
    if args.valid:
        valid = _load_array(args.valid).astype(bool)
    else:
        valid = np.isfinite(values)
    if args.auto_range:
        lo, hi = scalarmod.choose_range(values, valid)
    else:
        if args.min is None or args.max is None:
            print("error: give --min and --max, or --auto-range", file=sys.stderr)
            return EXIT_USAGE
        lo, hi = args.min, args.max
    try:
        pixels = scalarmod.encode(values, lo, hi, valid)
    except scalarmod.EncodingRangeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_INVALID
    Path(args.output).write_bytes(pngmod.write_png(pixels, 16))
    print(json.dumps({"encoding": {"type": "png16_linear", "min": lo, "max": hi},
                      "quantization_step": scalarmod.quantization_step(lo, hi),
                      "invalid_samples": int((~valid).sum())}, indent=2))
    if args.mask_output:
        Path(args.mask_output).write_bytes(pngmod.write_png(np.where(valid, 255, 0).astype(np.uint8), 8))
    return EXIT_OK


def cmd_decode(args) -> int:
    target = Path(args.source)
    if args.layer:
        with Bundle(target) as bundle:
            values, valid = bundle.read(args.layer)
            layer = bundle.layer(args.layer)
        values = values.astype(np.float64)
    else:
        if args.min is None or args.max is None:
            print("error: decoding a bare PNG needs --min and --max", file=sys.stderr)
            return EXIT_USAGE
        values = scalarmod.decode(pngmod.decode_pixels(target.read_bytes()), args.min, args.max)
        valid = np.ones(values.shape, dtype=bool)
        layer = None
    out = np.where(valid, values, np.nan)
    if args.sample:
        row, col = args.sample
        units = f" {layer['units']}" if layer and "units" in layer else ""
        print(f"row {row} col {col}: " + (f"{float(out[row, col])!r}{units}" if valid[row, col] else "invalid"))
    if args.output:
        if args.output.endswith(".npy"):
            np.save(args.output, out)
        else:
            np.savetxt(args.output, out, delimiter=",", fmt="%.10g")
        print(f"Wrote {args.output} ({out.shape[1]}x{out.shape[0]}, invalid samples as NaN)")
    if not args.sample and not args.output:
        finite = out[np.isfinite(out)]
        if finite.size:
            print(f"{out.shape[1]}x{out.shape[0]}; valid {finite.size}; min {finite.min():.6g}; max {finite.max():.6g}; mean {finite.mean():.6g}")
        else:
            print(f"{out.shape[1]}x{out.shape[0]}; no valid samples")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="wmi", description="Reference tools for the experimental World Map Interchange draft.")
    p.add_argument("--version", action="version", version=f"wmi {__version__} (format draft 0.1.0)")
    sub = p.add_subparsers(dest="command", required=True)

    def limits_args(sp):
        sp.add_argument("--max-pixels", type=int, help="maximum pixels per image (default 268435456)")
        sp.add_argument("--max-file-mb", type=float, help="maximum size of one file in MiB (default 2048)")
        sp.add_argument("--consumer", metavar="PROFILE.json", help="consumer capability profile for the support report")

    sp = sub.add_parser("validate", help="validate a package directory or ZIP")
    sp.add_argument("path")
    sp.add_argument("--json", action="store_true", help="emit a machine-readable report")
    sp.add_argument("--strict", action="store_true", help="treat warnings as failures")
    limits_args(sp)
    sp.set_defaults(func=cmd_validate)

    sp = sub.add_parser("inspect", help="summarise a package")
    sp.add_argument("path")
    sp.add_argument("--json", action="store_true")
    limits_args(sp)
    sp.set_defaults(func=cmd_inspect)

    sp = sub.add_parser("pack", help="validate a directory package and write a ZIP")
    sp.add_argument("directory")
    sp.add_argument("output")
    sp.add_argument("--no-sidecars", action="store_true", help="omit per-image sidecar JSON files")
    sp.set_defaults(func=cmd_pack)

    sp = sub.add_parser("rehash", help="recompute SHA-256 values in a directory package's manifest")
    sp.add_argument("directory")
    sp.set_defaults(func=cmd_rehash)

    sp = sub.add_parser("sidecars", help="generate per-image sidecars from the manifest")
    sp.add_argument("directory")
    sp.set_defaults(func=cmd_sidecars)

    sp = sub.add_parser("encode", help="encode a .npy/.csv array of physical values to a PNG16")
    sp.add_argument("input")
    sp.add_argument("output")
    sp.add_argument("--min", type=float)
    sp.add_argument("--max", type=float)
    sp.add_argument("--auto-range", action="store_true", help="use the valid data range (constant fields handled)")
    sp.add_argument("--valid", help=".npy/.csv boolean validity array (default: finite samples)")
    sp.add_argument("--mask-output", help="also write a PNG8 validity mask")
    sp.set_defaults(func=cmd_encode)

    sp = sub.add_parser("decode", help="decode a layer from a package, or a bare PNG16 with --min/--max")
    sp.add_argument("source", help="package directory/ZIP (with --layer) or PNG file")
    sp.add_argument("--layer")
    sp.add_argument("--min", type=float)
    sp.add_argument("--max", type=float)
    sp.add_argument("--sample", type=int, nargs=2, metavar=("ROW", "COL"))
    sp.add_argument("--output", "-o", help="write .npy or .csv (invalid samples as NaN)")
    sp.set_defaults(func=cmd_decode)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except PackageError as exc:
        print(f"error [{exc.code}]: {exc}", file=sys.stderr)
        return EXIT_INVALID
    except (OSError, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
