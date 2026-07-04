"""ngspice batch CLI runner."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Literal

ModelType = Literal["ideal", "ti"]

_MODEL_CONFIG: dict[ModelType, dict[str, str]] = {
    "ideal": {
        "bench": "ina333_bench.cir",
        "include": "models/ina333_ideal.sub",
    },
    "ti": {
        "bench": "ina333_bench_ti.cir",
        "include": "models/ina333_ti.lib",
    },
}


class NgspiceNotFoundError(RuntimeError):
    """Raised when the ngspice binary cannot be located."""


class NgspiceSimulationError(RuntimeError):
    """Raised when ngspice exits with an error."""


def find_ngspice() -> str:
    """Resolve ngspice binary from NGSPICE env var or PATH."""
    env_path = os.environ.get("NGSPICE")
    if env_path and Path(env_path).is_file():
        return env_path
    found = shutil.which("ngspice")
    if found:
        return found
    raise NgspiceNotFoundError(
        "ngspice not found. Install with 'brew install ngspice' "
        "or set the NGSPICE environment variable to the binary path."
    )


def run_batch(
    netlist_path: Path,
    raw_path: Path,
    log_path: Path | None = None,
    ascii_raw: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run ngspice in batch mode and write output to a raw file."""
    ngspice = find_ngspice()
    raw_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [ngspice, "-b", "-r", str(raw_path), str(netlist_path)]
    env = os.environ.copy()
    if ascii_raw:
        env["SPICE_ASCIIRAWFILE"] = "1"

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        cwd=netlist_path.parent,
    )

    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            f"Command: {' '.join(cmd)}\n"
            f"Exit code: {result.returncode}\n\n"
            f"--- stdout ---\n{result.stdout}\n\n"
            f"--- stderr ---\n{result.stderr}\n"
        )

    if result.returncode != 0:
        raise NgspiceSimulationError(
            f"ngspice failed (exit {result.returncode}).\n"
            f"stderr:\n{result.stderr}\n"
            f"stdout:\n{result.stdout}"
        )

    if not raw_path.is_file():
        raise NgspiceSimulationError(
            f"ngspice completed but raw file not found: {raw_path}\n"
            f"stderr:\n{result.stderr}"
        )

    return result


def bench_template_path(circuits_dir: Path, model: ModelType) -> Path:
    """Return the bench netlist template for the selected model."""
    return circuits_dir / _MODEL_CONFIG[model]["bench"]


def patch_netlist_rg(content: str, rg_value: str) -> str:
    """Return netlist content with updated RGVAL parameter."""
    lines = []
    for line in content.splitlines():
        if line.strip().startswith(".param RGVAL="):
            lines.append(f".param RGVAL={rg_value}")
        else:
            lines.append(line)
    return "\n".join(lines) + "\n"


def patch_netlist_for_output_dir(
    content: str,
    project_root: Path,
    output_dir: Path,
    model: ModelType,
) -> str:
    """Rewrite include and waveform file paths for a netlist run from output_dir."""
    circuits_dir = project_root / "circuits"
    include_rel = _MODEL_CONFIG[model]["include"]
    rel_include = Path(os.path.relpath(circuits_dir / include_rel, output_dir))
    rel_diff = Path(os.path.relpath(output_dir / "input_diff.txt", output_dir))

    content = content.replace(
        f'.include "{include_rel}"',
        f'.include "{rel_include.as_posix()}"',
    )
    content = content.replace(
        'file="../outputs/input_diff.txt"',
        f'file="{rel_diff.as_posix()}"',
    )
    return content


def write_patched_netlist(
    template_path: Path,
    output_path: Path,
    rg_value: str,
    project_root: Path | None = None,
    model: ModelType = "ideal",
) -> Path:
    """Write a netlist copy with the RGVAL parameter and paths updated."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    content = patch_netlist_rg(template_path.read_text(), rg_value)
    if project_root is not None:
        content = patch_netlist_for_output_dir(content, project_root, output_path.parent, model)
    output_path.write_text(content)
    return output_path
