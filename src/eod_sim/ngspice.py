"""ngspice batch CLI runner."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from eod_sim.stages.registry import Stage
from eod_sim.validation import scan_ngspice_output


class NgspiceNotFoundError(RuntimeError):
    """Raised when the ngspice binary cannot be located."""


class NgspiceSimulationError(RuntimeError):
    """Raised when ngspice exits with an error."""


DEFAULT_TIMEOUT_S = 300.0
"""Kill ngspice after this many seconds; a healthy stage run takes well
under two minutes, while convergence-stuck runs can hang indefinitely."""


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
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> subprocess.CompletedProcess[str]:
    """Run ngspice in batch mode and write output to a raw file."""
    ngspice = find_ngspice()
    raw_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [ngspice, "-b", "-r", str(raw_path), str(netlist_path)]
    env = os.environ.copy()
    if ascii_raw:
        env["SPICE_ASCIIRAWFILE"] = "1"

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            cwd=netlist_path.parent,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        if log_path:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(
                f"Command: {' '.join(cmd)}\n"
                f"TIMED OUT after {timeout_s:.0f} s (killed)\n\n"
                f"--- stdout ---\n{stdout}\n\n"
                f"--- stderr ---\n{stderr}\n"
            )
        raise NgspiceSimulationError(
            f"ngspice did not finish within {timeout_s:.0f} s and was killed — "
            "the simulation is likely stuck at a convergence failure.\n"
            "Check the run netlist and component values; the behavioral "
            "detector benches are expected to converge on the first try."
        ) from exc

    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            f"Command: {' '.join(cmd)}\n"
            f"Exit code: {result.returncode}\n\n"
            f"--- stdout ---\n{result.stdout}\n\n"
            f"--- stderr ---\n{result.stderr}\n"
        )

    log_hint = f"See log: {log_path}" if log_path else ""
    findings = scan_ngspice_output(result.stdout, result.stderr)
    advice = ""
    if findings:
        advice = (
            f"Detected: {', '.join(findings)}.\n"
            "Check the run netlist and component values; the behavioral "
            "detector benches are expected to converge on the first try.\n"
        )

    if result.returncode != 0:
        raise NgspiceSimulationError(
            f"ngspice failed (exit {result.returncode}).\n"
            f"{advice}"
            f"stderr:\n{result.stderr}\n"
            f"{log_hint}"
        )

    # ngspice can exit 0 after aborting the transient; scan output for
    # convergence failures so partial results are never treated as success.
    if findings:
        raise NgspiceSimulationError(
            f"ngspice reported simulation problems despite exit code 0.\n"
            f"{advice}{log_hint}"
        )

    if not raw_path.is_file():
        raise NgspiceSimulationError(
            f"ngspice completed but raw file not found: {raw_path}\n"
            f"stderr:\n{result.stderr}\n"
            f"{log_hint}"
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
