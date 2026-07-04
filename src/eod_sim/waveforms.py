"""EOD-like biphasic differential pulse train waveform generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np

PulseShape = Literal["square", "rounded"]
DriveMode = Literal["diff_inputs", "electrodes"]


@dataclass
class LFOffsetParams:
    """Drawn low-frequency differential offset parameters for one simulation."""

    frequency_hz: float
    phase_rad: float
    amplitude_mv: float
    center_hz: float
    span_hz: float


@dataclass
class EODPulseConfig:
    """Parameters for a biphasic differential pulse train."""

    pulse_mv: float = 1.0
    """Peak differential amplitude in millivolts."""

    pulse_shape: PulseShape = "square"
    """Pulse envelope: square (ideal) or rounded (smooth lobes)."""

    pulse_width_us: float = 200.0
    """Total biphasic pulse width in microseconds (both lobes)."""

    phase_ms: float = 0.5
    """Square-pulse lobe duration in ms (legacy; used when pulse_shape='square')."""

    isi_ms: float = 20.0
    """Inter-pulse interval in milliseconds."""

    num_pulses: int = 4
    """Number of pulses in the train."""

    vcm: float = 2.5
    """Common-mode voltage in volts."""

    start_ms: float = 5.0
    """Time of first pulse onset in milliseconds."""

    duration_ms: float = 100.0
    """Total waveform duration in milliseconds."""

    sample_us: float = 10.0
    """Sample interval in microseconds."""

    drive_mode: DriveMode = "diff_inputs"
    """diff_inputs: V+ / V- at amp inputs; electrodes: ELEC_A / ELEC_B anti-phase."""

    lf_offset_enabled: bool = False
    """Add slow sinusoidal differential offset (water-recording artifact)."""

    lf_offset_amplitude_mv: float = 100.0
    """Peak LF differential offset amplitude in millivolts."""

    lf_offset_center_hz: float = 20.0
    """Center frequency for per-run LF offset draw (Hz)."""

    lf_offset_span_hz: float = 10.0
    """Uniform draw span: frequency in [center - span, center + span] Hz."""

    lf_offset_seed: int | None = None
    """Optional RNG seed; None draws fresh f and phase each simulation."""

    def lobe_duration_s(self) -> float:
        """Duration of one lobe (positive or negative) in seconds."""
        if self.pulse_shape == "square":
            return self.phase_ms * 1e-3
        return (self.pulse_width_us * 1e-6) / 2

    def pulse_duration_s(self) -> float:
        """Total duration of one biphasic pulse in seconds."""
        return 2 * self.lobe_duration_s()

    def pulse_onset_s(self, pulse_index: int = 0) -> float:
        """Absolute time of pulse onset in seconds."""
        return self.start_ms * 1e-3 + pulse_index * self.isi_ms * 1e-3

    def pulse_view_window_s(
        self,
        pulse_index: int = 0,
        window_scale: float = 2.0,
        margin_us: float | None = None,
    ) -> tuple[float, float]:
        """Return (t_start, t_end) for a single-pulse zoom view.

        Default span is window_scale × biphasic pulse width (2.0 shows pulse + equal tail).
        Pass margin_us to use legacy padding instead of window_scale.
        """
        t0 = self.pulse_onset_s(pulse_index)
        pulse_s = self.pulse_duration_s()
        if margin_us is not None:
            margin_s = margin_us * 1e-6
            return t0 - margin_s, t0 + pulse_s + margin_s
        return t0, t0 + window_scale * pulse_s


def format_timestep_spice(sample_us: float) -> str:
    """Format a sample interval in microseconds for SPICE netlists."""
    if sample_us >= 1:
        return f"{sample_us:g}u"
    return f"{sample_us * 1000:g}n"


def format_duration_spice(duration_ms: float) -> str:
    """Format a simulation duration in milliseconds for SPICE netlists."""
    return f"{duration_ms:g}m"


def default_sample_us(pulse_shape: PulseShape) -> float:
    """Default waveform/sample interval: finer for short rounded pulses."""
    return 1.0 if pulse_shape == "rounded" else 10.0


def isi_ms_from_khz(pulse_rate_khz: float) -> float:
    """Convert pulse repetition rate (kHz) to inter-pulse interval (ms)."""
    if pulse_rate_khz <= 0:
        raise ValueError("Pulse rate must be > 0 kHz")
    return 1.0 / pulse_rate_khz


def pulse_rate_khz(isi_ms: float) -> float:
    """Convert inter-pulse interval (ms) to pulse repetition rate (kHz)."""
    if isi_ms <= 0:
        raise ValueError("ISI must be > 0 ms")
    return 1.0 / isi_ms


def _single_pulse_square(t: np.ndarray, t0: float, amp: float, lobe_s: float) -> np.ndarray:
    """Biphasic square differential pulse: +amp, -amp, return to 0."""
    vin = np.zeros_like(t)
    t_rel = t - t0
    pos_mask = (t_rel >= 0) & (t_rel < lobe_s)
    neg_mask = (t_rel >= lobe_s) & (t_rel < 2 * lobe_s)
    vin[pos_mask] = amp
    vin[neg_mask] = -amp
    return vin


def _single_pulse_rounded(t: np.ndarray, t0: float, amp: float, lobe_s: float) -> np.ndarray:
    """Biphasic rounded pulse using half-sine lobes (smooth at edges and peak)."""
    vin = np.zeros_like(t)
    t_rel = t - t0
    pulse_s = 2 * lobe_s

    pos_mask = (t_rel >= 0) & (t_rel < lobe_s)
    if np.any(pos_mask):
        vin[pos_mask] = amp * np.sin(np.pi * t_rel[pos_mask] / lobe_s)

    neg_mask = (t_rel >= lobe_s) & (t_rel < pulse_s)
    if np.any(neg_mask):
        t_neg = t_rel[neg_mask] - lobe_s
        vin[neg_mask] = -amp * np.sin(np.pi * t_neg / lobe_s)

    return vin


def single_pulse_diff(
    t: np.ndarray,
    t0: float,
    amp: float,
    cfg: EODPulseConfig,
) -> np.ndarray:
    """Generate one biphasic differential pulse at time t0."""
    lobe_s = cfg.lobe_duration_s()
    if cfg.pulse_shape == "square":
        return _single_pulse_square(t, t0, amp, lobe_s)
    if cfg.pulse_shape == "rounded":
        return _single_pulse_rounded(t, t0, amp, lobe_s)
    raise ValueError(f"Unknown pulse shape: {cfg.pulse_shape}")


def sample_lf_offset_params(cfg: EODPulseConfig) -> LFOffsetParams | None:
    """Draw LF offset frequency and phase for one simulation."""
    if not cfg.lf_offset_enabled:
        return None
    if cfg.lf_offset_span_hz < 0:
        raise ValueError("LF offset span must be >= 0 Hz")
    if cfg.lf_offset_amplitude_mv < 0:
        raise ValueError("LF offset amplitude must be >= 0 mV")

    rng = np.random.default_rng(cfg.lf_offset_seed)
    f_min = cfg.lf_offset_center_hz - cfg.lf_offset_span_hz
    f_max = cfg.lf_offset_center_hz + cfg.lf_offset_span_hz
    if f_min <= 0:
        raise ValueError("LF offset frequency range must be > 0 Hz")

    return LFOffsetParams(
        frequency_hz=float(rng.uniform(f_min, f_max)),
        phase_rad=float(rng.uniform(0.0, 2.0 * np.pi)),
        amplitude_mv=cfg.lf_offset_amplitude_mv,
        center_hz=cfg.lf_offset_center_hz,
        span_hz=cfg.lf_offset_span_hz,
    )


def lf_offset_waveform(
    time_s: np.ndarray,
    params: LFOffsetParams,
    t_ref_s: float,
) -> np.ndarray:
    """Sinusoidal differential offset with phase referenced to t_ref_s."""
    amp_v = params.amplitude_mv * 1e-3
    return amp_v * np.sin(2.0 * np.pi * params.frequency_hz * (time_s - t_ref_s) + params.phase_rad)


def generate_eod_pulse_train(
    config: EODPulseConfig | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, LFOffsetParams | None]:
    """Generate time, V+, V-, and optional LF offset draw for an EOD-like pulse train."""
    cfg = config or EODPulseConfig()
    dt = cfg.sample_us * 1e-6
    duration_s = cfg.duration_ms * 1e-3
    time_s = np.arange(0, duration_s + dt / 2, dt)

    amp_v = cfg.pulse_mv * 1e-3
    isi_s = cfg.isi_ms * 1e-3
    start_s = cfg.start_ms * 1e-3

    vin_diff = np.zeros_like(time_s)
    for i in range(cfg.num_pulses):
        t0 = start_s + i * isi_s
        vin_diff += single_pulse_diff(time_s, t0, amp_v, cfg)

    lf_offset = sample_lf_offset_params(cfg)
    if lf_offset is not None:
        vin_diff += lf_offset_waveform(time_s, lf_offset, start_s)

    if cfg.drive_mode == "electrodes":
        vp = vin_diff / 2
        vn = -vin_diff / 2
    else:
        vp = cfg.vcm + vin_diff / 2
        vn = cfg.vcm - vin_diff / 2
    return time_s, vp, vn, lf_offset


def write_diff_file(time_s: np.ndarray, vp: np.ndarray, vn: np.ndarray, path: Path) -> None:
    """Write ngspice filesource input: time V+ V- per line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        f.write("# time V+ V-\n")
        for t, v_p, v_n in zip(time_s, vp, vn):
            f.write(f"{t:.9e} {v_p:.9e} {v_n:.9e}\n")


def write_pwl(time_s: np.ndarray, voltage: np.ndarray, path: Path) -> None:
    """Write single-column PWL file (time voltage per line)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for t, v in zip(time_s, voltage):
            f.write(f"{t:.9e} {v:.9e}\n")


def gain_to_rg(gain: float) -> float:
    """Convert INA333 gain to RG value: G = 1 + 100k/RG."""
    if gain <= 1:
        raise ValueError("Gain must be > 1 for finite RG")
    return 100_000.0 / (gain - 1)


def format_rg_spice(rg_ohms: float) -> str:
    """Format RG value for SPICE netlist."""
    if rg_ohms >= 1000:
        return f"{rg_ohms / 1000:.4f}k"
    return f"{rg_ohms:.2f}"


@dataclass
class WaveformResult:
    """Generated differential waveform and metadata."""

    time_s: np.ndarray
    vp: np.ndarray
    vn: np.ndarray
    vin_diff: np.ndarray
    config: EODPulseConfig
    diff_path: Path
    lf_offset: LFOffsetParams | None = None


def generate_and_write_pwl(
    output_dir: Path,
    config: EODPulseConfig | None = None,
) -> WaveformResult:
    """Generate EOD pulse train and write filesource waveform file."""
    cfg = config or EODPulseConfig()
    time_s, vp, vn, lf_offset = generate_eod_pulse_train(cfg)

    diff_path = output_dir / "input_diff.txt"
    write_diff_file(time_s, vp, vn, diff_path)

    return WaveformResult(
        time_s=time_s,
        vp=vp,
        vn=vn,
        vin_diff=vp - vn,
        config=cfg,
        diff_path=diff_path,
        lf_offset=lf_offset,
    )


