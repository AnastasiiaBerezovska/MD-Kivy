import math
import os
import random
import unittest


os.environ.setdefault('KIVY_HOME', '/tmp/mdkivy-tests')
os.environ.setdefault('KIVY_NO_ARGS', '1')
os.environ.setdefault('KCFG_KIVY_LOG_LEVEL', 'error')

from kivy.config import Config

Config.set('graphics', 'window_state', 'hidden')

from kivy.uix.label import Label

import mdkivy.simulation.game_layout as game_layout


class _NullMonitor:
    def update_simulation_metrics(self, **_kwargs):
        pass

    def get_cpu_usage(self):
        return 0.0


class _NoArduino:
    def __init__(self):
        raise RuntimeError('disabled in test')


class _NoMakey:
    def __init__(self, **_kwargs):
        pass


class ThermodynamicsTests(unittest.TestCase):
    def setUp(self):
        game_layout.ArduinoReading = _NoArduino
        game_layout.DualMakeyInput = _NoMakey
        self.layout = game_layout.GameLayout(performance_monitor=_NullMonitor())
        self.layout.pos = (0, 0)
        self.layout.size = (1996, 1100)
        self.layout.total_energy_label = Label()
        self.layout.temperature_label = Label()
        self.layout.pressure_label = Label()
        self.layout.beaker.active = False
        for attr in (
            'gravity_slider', 'epsilon_slider', 'sigma_slider',
            'delta_slider', 'speed_slider', 'size_slider',
        ):
            setattr(self.layout, attr, None)

    def test_phase_presets_start_at_declared_temperature(self):
        for phase in ('solid', 'liquid', 'gas'):
            with self.subTest(phase=phase):
                random.seed(7)
                getattr(self.layout, f'generate_{phase}')()
                self.layout.intermolecular_forces = True
                self.layout._refresh_forces()
                _, temperature, _ = self.layout._thermodynamic_metrics()
                expected = getattr(self.layout, f'{phase.upper()}_TEMPERATURE')
                self.assertAlmostEqual(temperature, expected, places=10)

    def test_manual_sandbox_force_toggle_uses_safe_default(self):
        """The blank-board workflow must use the same epsilon as presets.

        This regresses the old epsilon=50 sandbox default: Forces Off concealed
        it, then turning Forces On produced E* near -1000 and T* above 16.
        """
        self.layout.reset_all_params()
        self.assertEqual(self.layout.epsilon,
                         self.layout.SUBSTANCE_EPSILON)

        for y in (350, 500, 650):
            for x in (550, 700, 850, 1000, 1150):
                touch = type('_Touch', (), {'pos': (x, y)})()
                self.assertTrue(self.layout.spawn_molecule_at_touch(touch))

        self.layout.toggle_intermolecular_forces()
        self.assertTrue(self.layout.intermolecular_forces)
        maximum_temperature = 0.0
        maximum_abs_energy = 0.0
        for _ in range(600):
            self.layout.update(1 / 30.0)
            maximum_temperature = max(
                maximum_temperature, self.layout._metric_raw['temperature'])
            maximum_abs_energy = max(
                maximum_abs_energy, abs(self.layout._metric_raw['energy']))

        self.assertLess(maximum_temperature, 2.0)
        self.assertLess(maximum_abs_energy, 100.0)

    def test_force_line_endpoints_follow_molecules_without_rebuild(self):
        self.layout.create_molecule(700, 500, 0, 0)
        self.layout.create_molecule(
            700 + 1.5 * self.layout.scale, 500, 0, 0)
        self.layout.intermolecular_forces = True
        self.layout.bonds_visible = True
        self.layout._update_lj_viz()

        self.assertEqual(len(self.layout._lj_viz_lines), 1)
        line = next(iter(self.layout._lj_viz_lines.values()))[1]
        old_line_id = id(line)

        self.layout.molecules[1].pos = (850, 575)
        self.layout._update_lj_viz_positions()

        self.assertEqual(id(line), old_line_id)
        expected = [*self.layout.molecules[0].pos,
                    *self.layout.molecules[1].pos]
        self.assertEqual(list(line.points), expected)

    def test_lj_force_is_derivative_of_reported_potential(self):
        self.layout.intermolecular_forces = True
        self.layout.epsilon = 1.7
        self.layout.sigma = 1.0
        self.layout.create_molecule(550, 550, 0, 0)
        self.layout.create_molecule(550 + 1.35 * self.layout.scale, 550, 0, 0)
        left = self.layout.molecules[0]

        self.layout._refresh_forces()
        measured_force = left.total_force.x / game_layout.INVERSE_MASS

        x0 = left.x
        h = 1e-3
        left.x = x0 + h
        self.layout._apply_lj_forces_numpy()
        potential_plus = self.layout._lj_potential
        left.x = x0 - h
        self.layout._apply_lj_forces_numpy()
        potential_minus = self.layout._lj_potential
        left.x = x0

        finite_difference_force = -(potential_plus - potential_minus) / (2 * h)
        self.assertAlmostEqual(measured_force, finite_difference_force, places=7)

    def test_ideal_gas_pressure_uses_temperature_and_area(self):
        self.layout.intermolecular_forces = False
        self.layout.create_molecule(500, 500, 50, 0)
        self.layout.create_molecule(900, 700, -50, 0)
        _, temperature, pressure = self.layout._thermodynamic_metrics()

        area = (self.layout.width / game_layout.LENGTH_UNIT
                * self.layout.height / game_layout.LENGTH_UNIT)
        expected_pressure = 2 * game_layout.K_B * temperature / area
        self.assertAlmostEqual(temperature, 0.5, places=10)
        self.assertAlmostEqual(pressure, expected_pressure, places=10)

    def test_gravitational_potential_keeps_total_energy_constant(self):
        self.layout.intermolecular_forces = False
        self.layout.set_gravity(10.0)
        self.layout.create_molecule(800, 850, 40, 0)
        self.layout._refresh_forces()
        initial_energy = self.layout._thermodynamic_metrics()[0]

        for _ in range(120):
            self.layout.update(1 / 30.0)

        final_energy = self.layout._metric_raw['energy']
        self.assertAlmostEqual(final_energy, initial_energy, places=8)

    def test_beaker_phase_is_one_to_one_projection_without_energy_spike(self):
        self.layout.beaker.active = False
        self.layout.generate_gas()
        old_molecules = set(self.layout.molecules)

        self.layout.beaker.active = True
        self.layout.draw_beaker()
        random.seed(7)
        self.layout.fill_beaker('solid')
        self.assertTrue(self.layout.molecules)
        self.assertTrue(old_molecules.isdisjoint(self.layout.molecules))
        self.assertEqual(len(self.layout._beaker_projection),
                         len(self.layout.molecules))
        self.assertTrue(any(not self.layout.beaker.contains(*molecule.pos)
                            for molecule in self.layout.molecules))
        for molecule in self.layout.molecules:
            x, y, radius = self.layout._beaker_projection_geometry(molecule)
            self.assertTrue(self.layout.beaker.contains(x, y))
            self.assertLess(radius, molecule.radius)

        self.layout.intermolecular_forces = True
        self.layout._forces_initialized = False
        self.layout._refresh_forces()
        initial_energy = self.layout._thermodynamic_metrics()[0]
        maximum_pressure = 0.0
        for _ in range(600):
            self.layout.update(1 / 30.0)
            maximum_pressure = max(maximum_pressure,
                                   abs(self.layout._metric_raw['pressure']))

        final_energy = self.layout._metric_raw['energy']
        relative_drift = abs(final_energy - initial_energy) / max(
            abs(initial_energy), 1.0)
        self.assertLess(relative_drift, 0.02)
        self.assertLess(maximum_pressure, 25.0)
        self.assertEqual(len(self.layout._beaker_projection),
                         len(self.layout.molecules))

    def test_beaker_projection_does_not_change_thermodynamics(self):
        from mdkivy.simulation.beaker import TOP

        self.layout.beaker.active = False
        self.layout.create_molecule(800, 600, 50, 0)
        metrics_without_projection = self.layout._thermodynamic_metrics()

        self.layout.beaker.active = True
        self.layout.set_beaker_orientation(TOP)
        metrics_with_projection = self.layout._thermodynamic_metrics()

        self.assertEqual(metrics_with_projection, metrics_without_projection)
        self.assertEqual(len(self.layout._beaker_projection), 1)

    def test_beaker_projection_tracks_molecule_motion_without_duplication(self):
        self.layout.beaker.active = True
        self.layout.draw_beaker()
        self.layout.create_molecule(700, 500, 50, 25)
        molecule = self.layout.molecules[0]
        self.layout._update_beaker_projection()

        cached = self.layout._beaker_projection[molecule]
        core = cached[5]
        old_core_id = id(core)
        old_position = tuple(core.pos)
        molecule.pos = (1000, 750)
        self.layout._update_beaker_projection()

        self.assertEqual(len(self.layout.molecules), 1)
        self.assertEqual(len(self.layout._beaker_projection), 1)
        self.assertEqual(id(self.layout._beaker_projection[molecule][5]),
                         old_core_id)
        self.assertNotEqual(tuple(core.pos), old_position)

    def test_verlet_conserves_phase_energy(self):
        self.layout.use_verlet = True
        self.layout.intermolecular_forces = True
        for phase in ('solid', 'liquid', 'gas'):
            with self.subTest(phase=phase):
                random.seed(7)
                getattr(self.layout, f'generate_{phase}')()
                self.layout.intermolecular_forces = True
                self.layout._forces_initialized = False
                self.layout._refresh_forces()
                initial_energy = self.layout._thermodynamic_metrics()[0]

                for _ in range(600):
                    self.layout.update(1 / 30.0)

                final_energy = self.layout._metric_raw['energy']
                relative_drift = abs(final_energy - initial_energy) / max(
                    abs(initial_energy), 1.0)
                self.assertLess(relative_drift, 0.01)

    def test_smoothing_reduces_readout_jitter(self):
        raw = []
        shown_temperature = []
        shown_pressure = []
        for i in range(180):
            value = 10.0 + math.sin(i * 1.7)
            raw.append(value)
            displayed = self.layout._smooth_metrics({
                'energy': value,
                'temperature': value,
                'pressure': value,
            }, 1 / 30.0)
            shown_temperature.append(displayed['temperature'])
            shown_pressure.append(displayed['pressure'])

        raw_range = max(raw[-60:]) - min(raw[-60:])
        self.assertLess(
            max(shown_temperature[-60:]) - min(shown_temperature[-60:]),
            raw_range * 0.05)
        self.assertLess(
            max(shown_pressure[-60:]) - min(shown_pressure[-60:]),
            raw_range * 0.05)

    def test_touch_spawn_avoids_repulsive_core_and_matches_temperature(self):
        random.seed(7)
        self.layout.generate_solid()
        self.layout.intermolecular_forces = True
        self.layout._refresh_forces()
        initial_energy, initial_temperature, _ = self.layout._thermodynamic_metrics()
        old_molecules = list(self.layout.molecules)

        # Deliberately request the centre of an occupied lattice site. The
        # insertion routine should move the new particle to the nearest gap.
        occupied = old_molecules[len(old_molecules) // 2].pos
        touch = type('_Touch', (), {'pos': occupied})()
        self.assertTrue(self.layout.spawn_molecule_at_touch(touch))
        new_molecule = self.layout.molecules[-1]

        equilibrium_factor = 2.0 ** (1.0 / 6.0)
        for molecule in old_molecules:
            distance = math.dist(new_molecule.pos, molecule.pos)
            sigma = 0.5 * (
                (self.layout.sigma if new_molecule.sig is None else new_molecule.sig) +
                (self.layout.sigma if molecule.sig is None else molecule.sig)
            )
            clearance = equilibrium_factor * sigma * self.layout.scale
            self.assertGreaterEqual(distance, clearance)

        self.layout._refresh_forces()
        final_energy, final_temperature, _ = self.layout._thermodynamic_metrics()
        self.assertAlmostEqual(final_temperature, initial_temperature, places=10)
        self.assertLess(abs(final_energy - initial_energy), 10.0)

        inserted_energy = final_energy
        maximum_temperature = final_temperature
        for _ in range(600):
            self.layout.update(1 / 30.0)
            maximum_temperature = max(
                maximum_temperature, self.layout._metric_raw['temperature'])
        settled_energy = self.layout._metric_raw['energy']
        relative_drift = abs(settled_energy - inserted_energy) / max(
            abs(inserted_energy), 1.0)
        self.assertLess(relative_drift, 0.01)
        self.assertLess(maximum_temperature, 0.5)

if __name__ == '__main__':
    unittest.main()
