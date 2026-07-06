"""Parse and normalize recorded EOD differential waveforms from CSV captures."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

DEFAULT_RECORDED_ID = "eod_row_02"
DEFAULT_SAMPLE_RATE_HZ = 195_312.0


@dataclass(frozen=True)
class RecordedSourceSpec:
    """Bundled or user-supplied recorded waveform source."""

    csv_path: Path
    sample_rate_hz: float = DEFAULT_SAMPLE_RATE_HZ
    baseline_samples: int = 200
    """Quiet pre-pulse samples used for baseline median (mV hover ~±0.4)."""

    threshold_fraction: float = 0.01
    """Pulse edge threshold as a fraction of peak |mV| after baseline removal."""

    threshold_floor_mv: float = 0.5
    """Minimum edge threshold in mV."""


@dataclass(frozen=True)
class RecordedPulseTemplate:
    """One baseline-corrected, peak-normalized differential pulse template."""

    time_s: np.ndarray
    shape: np.ndarray
    """Unitless differential shape; max |shape| == 1."""

    baseline_mv: float
    source_id: str
    sample_rate_hz: float
    raw_peak_mv: float
    window_start_idx: int
    window_end_idx: int

    @property
    def duration_s(self) -> float:
        if len(self.time_s) <= 1:
            return 0.0
        return float(self.time_s[-1])

    @property
    def duration_us(self) -> float:
        return self.duration_s * 1e6

    @property
    def native_sample_us(self) -> float:
        return 1e6 / self.sample_rate_hz


def project_data_dir() -> Path:
    """Repository ``data/recorded`` directory."""
    return Path(__file__).resolve().parents[2] / "data" / "recorded"


def default_recorded_sources() -> dict[str, RecordedSourceSpec]:
    data = project_data_dir()
    return {
        DEFAULT_RECORDED_ID: RecordedSourceSpec(
            csv_path=data / "EOD_row_02.csv",
            sample_rate_hz=DEFAULT_SAMPLE_RATE_HZ,
        ),
    }


def parse_recorded_csv(path: Path | str) -> np.ndarray:
    """Load comma-separated differential samples (mV) from a CSV file."""
    text = Path(path).read_text()
    values: list[float] = []
    for token in text.replace("\n", ",").split(","):
        token = token.strip()
        if token:
            values.append(float(token))
    if not values:
        raise ValueError(f"No numeric samples found in {path}")
    return np.asarray(values, dtype=float)


def extract_central_pulse(
    mv: np.ndarray,
    sample_rate_hz: float,
    *,
    baseline_samples: int = 200,
    threshold_fraction: float = 0.01,
    threshold_floor_mv: float = 0.5,
) -> tuple[np.ndarray, np.ndarray, float, int, int, float]:
    """Select the central pulse, subtract baseline, and normalize to peak |mV| = 1.

    Returns ``(time_s, shape, baseline_mv, start_idx, end_idx, raw_peak_mv)``.
    ``time_s`` starts at 0 on the extracted window.
    """
    if sample_rate_hz <= 0:
        raise ValueError("sample_rate_hz must be > 0")
    if len(mv) < 3:
        raise ValueError("Recorded waveform must contain at least 3 samples")

    n_baseline = min(max(baseline_samples, 1), len(mv))
    baseline_mv = float(np.median(mv[:n_baseline]))
    corrected = mv - baseline_mv

    raw_peak_mv = float(np.max(np.abs(corrected)))
    if raw_peak_mv <= 0:
        raise ValueError("Recorded waveform has zero peak after baseline removal")

    threshold_mv = max(threshold_floor_mv, threshold_fraction * raw_peak_mv)
    peak_idx = int(np.argmax(np.abs(corrected)))

    left = peak_idx
    while left > 0 and abs(corrected[left - 1]) > threshold_mv:
        left -= 1

    right = peak_idx
    while right < len(corrected) - 1 and abs(corrected[right + 1]) > threshold_mv:
        right += 1

    window = corrected[left : right + 1]
    shape = window / raw_peak_mv
    dt_s = 1.0 / sample_rate_hz
    time_s = np.arange(len(window), dtype=float) * dt_s
    return time_s, shape, baseline_mv, left, right, raw_peak_mv


def load_recorded_template(spec: RecordedSourceSpec, source_id: str) -> RecordedPulseTemplate:
    """Parse CSV, extract the central pulse, and return a normalized template."""
    if not spec.csv_path.is_file():
        raise FileNotFoundError(f"Recorded waveform CSV not found: {spec.csv_path}")

    mv = parse_recorded_csv(spec.csv_path)
    time_s, shape, baseline_mv, left, right, raw_peak = extract_central_pulse(
        mv,
        spec.sample_rate_hz,
        baseline_samples=spec.baseline_samples,
        threshold_fraction=spec.threshold_fraction,
        threshold_floor_mv=spec.threshold_floor_mv,
    )
    return RecordedPulseTemplate(
        time_s=time_s,
        shape=shape,
        baseline_mv=baseline_mv,
        source_id=source_id,
        sample_rate_hz=spec.sample_rate_hz,
        raw_peak_mv=raw_peak,
        window_start_idx=left,
        window_end_idx=right,
    )


@lru_cache(maxsize=8)
def get_recorded_template(source_id: str = DEFAULT_RECORDED_ID) -> RecordedPulseTemplate:
    """Return a cached recorded pulse template by bundled source id."""
    sources = default_recorded_sources()
    if source_id not in sources:
        known = ", ".join(sorted(sources))
        raise ValueError(f"Unknown recorded source '{source_id}'. Known: {known}")
    return load_recorded_template(sources[source_id], source_id)


def get_recorded_template_from_path(
    csv_path: Path | str,
    sample_rate_hz: float = DEFAULT_SAMPLE_RATE_HZ,
    **extract_kwargs: float | int,
) -> RecordedPulseTemplate:
    """Load a template from an arbitrary CSV path (not cached)."""
    spec = RecordedSourceSpec(
        csv_path=Path(csv_path),
        sample_rate_hz=sample_rate_hz,
        baseline_samples=int(extract_kwargs.get("baseline_samples", 200)),
        threshold_fraction=float(extract_kwargs.get("threshold_fraction", 0.01)),
        threshold_floor_mv=float(extract_kwargs.get("threshold_floor_mv", 0.5)),
    )
    return load_recorded_template(spec, source_id=str(Path(csv_path)))
