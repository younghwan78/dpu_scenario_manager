"""
DPU Scenario Pydantic Models.

Defines the data model for DPU scenarios with extensible validation.
HW constraint checks are deferred — the schema validates structure only.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class BufferSize(BaseModel):
    """Buffer resolution."""
    width: int
    height: int

    def __str__(self) -> str:
        return f"{self.width}×{self.height}"


class BufferBW(BaseModel):
    """Bandwidth information (GB/s)."""
    original_gbps: float
    compressed_gbps: Optional[float] = None

    def effective(self) -> float:
        """Return compressed BW if available, else original."""
        return self.compressed_gbps if self.compressed_gbps is not None else self.original_gbps


class ClockInfo(BaseModel):
    """Clock frequency table (MHz)."""
    min_pixel_clock_mhz: float
    min_axi_clock_mhz: float
    aclk_mhz: float
    mif_min_freq_mhz: float


class DisplayInfo(BaseModel):
    """Display panel specification."""
    resolution: str          # e.g. "FHD+", "WQHD+"
    width: int
    height: int
    fps: int = 60


# ---------------------------------------------------------------------------
# Layer (one per RDMA port)
# ---------------------------------------------------------------------------

class Layer(BaseModel):
    """
    Single DPU input layer mapped to an RDMA port.

    Attributes kept as ``str`` for extensibility — downstream validators
    can be added later via model_validator / field_validator.
    """
    name: str                                   # e.g. "Wallpaper"
    source: str                                 # "GPU", "ISP", "CODEC"
    format: str                                 # "NV12", "ARGB8888", ...
    format_category: str                        # "YUV" | "ARGB"
    size: BufferSize
    bw: BufferBW
    compression_type: str = "None"              # "SBWC", "SAJC", "None"
    rdma_index: int = Field(ge=0, le=15)        # 0-15 range hint (soft)


# ---------------------------------------------------------------------------
# Top-level scenario
# ---------------------------------------------------------------------------

class DpuScenario(BaseModel):
    """
    Complete DPU scenario definition.

    Contains everything the viewer needs: clock, display, and all
    RDMA layer assignments with their buffer attributes.
    """
    name: str
    description: str = ""
    clock: ClockInfo
    display: DisplayInfo
    layers: list[Layer]

    # -- Convenience helpers ------------------------------------------------

    @property
    def layer_count(self) -> int:
        return len(self.layers)

    def layers_by_source(self) -> dict[str, list[Layer]]:
        """Group layers by their source IP."""
        groups: dict[str, list[Layer]] = {}
        for layer in self.layers:
            groups.setdefault(layer.source, []).append(layer)
        return groups

    def total_bw(self, effective: bool = True) -> float:
        """Sum bandwidth across all layers (GB/s)."""
        if effective:
            return sum(l.bw.effective() for l in self.layers)
        return sum(l.bw.original_gbps for l in self.layers)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_scenario(path: Path) -> DpuScenario:
    """Load and validate a scenario YAML file."""
    with open(path, "r", encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f)
    return DpuScenario(**raw)


def load_all_scenarios(scenario_dir: Path) -> list[DpuScenario]:
    """Load all *.yaml files from a directory, sorted by filename."""
    scenarios: list[DpuScenario] = []
    for yaml_path in sorted(scenario_dir.glob("*.yaml")):
        scenarios.append(load_scenario(yaml_path))
    return scenarios
