"""Headless benchmark of the simulation update step.

Drives the real GameLayout.update() in a hidden window and reports the mean
wall time per physics step for a range of molecule counts, with Lennard-Jones
forces off and on. Rendering is excluded, so the numbers isolate the physics
cost that the Computing Load gauge visualizes.

Usage: python3 tools/bench_physics.py
"""
import os
import sys
import time
import math
import random
import statistics
from pathlib import Path

os.environ.setdefault('KIVY_NO_ARGS', '1')
os.environ.setdefault('KCFG_KIVY_LOG_LEVEL', 'error')

from kivy.config import Config
Config.set('graphics', 'window_state', 'hidden')
Config.set('graphics', 'width', '1366')
Config.set('graphics', 'height', '768')

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kivy.uix.label import Label
from mdkivy.simulation.game_layout import GameLayout


class _NullMonitor:
    def update_simulation_metrics(self, **kwargs):
        pass

    def get_cpu_usage(self):
        return 0.0


DT = 1 / 30.0
WARMUP_STEPS = 60
TIMED_STEPS = 300
ARENA = (1366, 768)


def _spawn(layout, count, seed=42):
    random.seed(seed)
    r = layout.molecule_radius
    for _ in range(count):
        x = random.uniform(r * 2, ARENA[0] - r * 2)
        y = random.uniform(r * 2, ARENA[1] - r * 2)
        angle = random.uniform(-math.pi, math.pi)
        layout.create_molecule(x, y, 300 * math.cos(angle), 300 * math.sin(angle))
        layout.molecules[-1].update_color_based_on_speed()


def _bench(layout, count, forces_on):
    for m in layout.molecules:
        layout.remove_widget(m)
    layout.molecules.clear()
    _spawn(layout, count)
    layout.intermolecular_forces = forces_on
    layout.frame_counter = 0

    for _ in range(WARMUP_STEPS):
        layout.update(DT)

    samples = []
    for _ in range(TIMED_STEPS):
        t0 = time.perf_counter()
        layout.update(DT)
        samples.append((time.perf_counter() - t0) * 1000.0)
    samples.sort()
    return statistics.fmean(samples), samples[int(0.95 * len(samples)) - 1]


def main():
    layout = GameLayout(performance_monitor=_NullMonitor())
    layout.pos = (0, 0)
    layout.size = ARENA
    layout.total_energy_label = Label()
    layout.temperature_label = Label()
    layout.pressure_label = Label()
    layout.speed_slider = None

    print(f"{'N':>5} {'forces':>7} {'mean_ms':>9} {'p95_ms':>8} {'max_Hz':>8}")
    for count in (25, 50, 100, 200, 300, 400):
        for forces_on in (False, True):
            mean, p95 = _bench(layout, count, forces_on)
            print(f"{count:>5} {'on' if forces_on else 'off':>7} "
                  f"{mean:>9.2f} {p95:>8.2f} {1000.0 / mean:>8.0f}")


if __name__ == '__main__':
    main()
