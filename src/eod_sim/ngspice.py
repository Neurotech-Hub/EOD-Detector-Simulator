"""ngspice batch CLI runner."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from eod_sim.stages.registry import Stage


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


def patch_netlist_params(content: str, params: dict[str, str]) -> str:
    """Return netlist content with updated .param values."""
    lines = []
    for line in content.splitlines():
        updated = line
        for name, value in params.items():
            if line.strip().startswith(f".param {name}="):
                updated = f".param {name}={value}"
                break
        lines.append(updated)
    return "\n".join(lines) + "\n"


def patch_netlist_for_output_dir(
    content: str,
    stage_dir: Path,
    output_dir: Path,
) -> str:
    """Rewrite .include and waveform file paths for a netlist run from output_dir."""

    def replace_include(match: re.Match[str]) -> str:
        rel_include = match.group(1)
        abs_path = (stage_dir / rel_include).resolve()
        patched = Path(os.path.relpath(abs_path, output_dir)).as_posix()
        return f'.include "{patched}"'

    content = re.sub(r'\.include\s+"([^"]+)"', replace_include, content)

    wave_path = output_dir / "input_diff.txt"
    wave_rel = Path(os.path.relpath(wave_path, output_dir)).as_posix()
    content = re.sub(
        r'file="[^"]*input_diff\.txt"',
        f'file="{wave_rel}"',
        content,
    )
    return content


def write_patched_netlist(
    template_path: Path,
    output_path: Path,
    stage: Stage,
    params: dict[str, str] | None = None,
) -> Path:
    """Write a netlist copy with parameters and paths updated for batch run."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    content = template_path.read_text()
    if params:
        content = patch_netlist_params(content, params)
    content = patch_netlist_for_output_dir(content, template_path.parent, output_path.parent)
    output_path.write_text(content)
    return output_path


def bench_template_path(circuits_dir: Path, stage: Stage, bench_variant: str) -> Path:
    """Return the bench netlist template for a stage and bench variant."""
    return stage.bench_path(circuits_dir, bench_variant)
