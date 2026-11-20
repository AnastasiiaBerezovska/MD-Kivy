import math
import os
import unittest
from types import SimpleNamespace

import numpy as np

os.environ.setdefault('KIVY_HOME', '/tmp/mdkivy-tests')
os.environ.setdefault('KIVY_NO_ARGS', '1')
os.environ.setdefault('KCFG_KIVY_LOG_LEVEL', 'error')

from mdkivy.simulation.beaker import Beaker, TOP
from mdkivy.simulation.beaker_dynamics import BeakerDynamics


class _Particle:
    sig = eps = None

    def __init__(self, position, velocity):
        self.pos = position
        self.total_velocity = velocity


class BeakerDynamicsTests(unittest.TestCase):
    def make_sample(self, phase=None, temperature=0.0, count=1):
        rng = np.random.default_rng(7)
        spacing = 2 ** (1 / 6) * (1.16 if phase == 'liquid' else 1.0)
        velocities = rng.normal(size=(count, 2))
        velocities *= math.sqrt(temperature / max(np.mean(velocities ** 2), 1e-12))
        particles = [
            _Particle(((i % 7 + 0.5 * ((i // 7) % 2)) * spacing,
                       (i // 7) * spacing * math.sqrt(3) / 2), velocity * 50)
            for i, velocity in enumerate(velocities)]
        layout = SimpleNamespace(
            pos=(0, 0), size=(1996, 1100), molecules=particles,
            size_factor=0.6, sigma=1.0, epsilon=1.0, scale=1.0,
            gravity=0.0, intermolecular_forces=True,
            _projection_phase=phase, temperature=temperature)
        layout._thermodynamic_metrics = lambda: (0, layout.temperature, 0)
        beaker = Beaker(layout)
        model = BeakerDynamics(beaker, seed=7)
        model.synchronize()
        return layout, beaker, model

    def test_gravity_moves_flask_particle_even_with_board_gravity_zero(self):
        layout, beaker, model = self.make_sample()
        model.positions[0] = (model.width / 2, model.height / 2)
        before = model.positions.copy()
        model.advance(1 / 60)
        self.assertEqual(layout.gravity, 0)
        self.assertLess(model.positions[0, 1], before[0, 1])
        self.assertLess(model.velocities[0, 1], 0)
        ordinary_gravity = beaker.view_gravity()
        layout.gravity = 10
        self.assertGreater(beaker.view_gravity(), ordinary_gravity)

    def test_birds_eye_has_no_downward_gravity_component(self):
        _, beaker, model = self.make_sample()
        beaker.orientation = TOP
        model.synchronize()
        model.positions[0] = (model.width / 2, model.height / 2)
        before = model.positions.copy()
        model.advance(1 / 30)
        np.testing.assert_array_equal(model.positions, before)
        np.testing.assert_array_equal(model.velocities, [[0, 0]])

    def test_unselected_particles_fall_calmly_with_stronger_gravity(self):
        _, _, model = self.make_sample()
        start = model.positions[0, 1]
        self.assertGreater(start, model.height * 0.65)
        for _ in range(120):
            model.advance(1 / 60)
        distance = start - model.positions[0, 1]
        self.assertGreater(distance, 3.0)
        self.assertLess(distance, 6.0)
        self.assertGreater(model.velocities[0, 1], -1.4)

    def test_gas_playback_is_slower_without_changing_its_temperature(self):
        motion = []
        for scale in (2.0, BeakerDynamics.TIME_SCALE):
            layout, _, model = self.make_sample('gas', 3.0, 1)
            model.positions[0] = (model.width * 0.5, model.height * 0.5)
            model.velocities[0] = (2, 0)
            model.bath_temperature = 0  # Isolate playback from random kicks.
            if scale == BeakerDynamics.TIME_SCALE:
                model.time_scale = scale
            before = model.positions[0, 0]
            model.advance(1 / 60)
            motion.append(model.positions[0, 0] - before)
            self.assertEqual(layout.temperature, 3.0)
        self.assertGreater(motion[0] / motion[1], 0.45)
        self.assertLess(motion[0] / motion[1], 0.55)

    def test_unselected_particles_remain_quiet_even_if_the_board_is_hot(self):
        _, _, model = self.make_sample(None, 3.0, 1)
        model.positions[0] = (model.width * 0.5, model.height * 0.7)
        before = model.positions.copy()
        for _ in range(60):
            model.advance(1 / 60)
        self.assertLess(model.positions[0, 1], before[0, 1] - 1.0)
        self.assertLess(abs(model.positions[0, 0] - before[0, 0]), 1.0)

    def test_solid_and_liquid_start_on_the_floor(self):
        for phase, temperature in (('solid', 0.15), ('liquid', 0.65)):
            with self.subTest(phase=phase):
                _, _, model = self.make_sample(phase, temperature, 49)
                floor = model.wall + model.radius
                self.assertAlmostEqual(model.positions[:, 1].min(), floor, places=6)
                self.assertTrue(all(model._fits(p) for p in model.positions))
                if phase == 'liquid':
                    self.assertGreater(np.ptp(model.positions[:, 0]),
                                       2 * np.ptp(model.positions[:, 1]))

    def test_solid_and_liquid_additions_land_quickly(self):
        arrival = {}
        for phase in ('solid', 'liquid'):
            layout, _, model = self.make_sample(phase, 0.0, 1)
            newcomer = _Particle((100, 100), np.zeros(2))
            layout.molecules.append(newcomer)
            model.synchronize()
            model.positions[-1] = (model.width * 0.5, model.height * 0.85)
            for frame in range(70):
                model.synchronize()
                model.advance(1 / 60)
                if newcomer not in model.falling:
                    arrival[phase] = frame
                    break
            self.assertIn(phase, arrival)
            self.assertLess(arrival[phase], 65)
        self.assertLess(arrival['solid'], arrival['liquid'])

    def test_new_solid_molecules_stick_to_the_lattice(self):
        layout, _, model = self.make_sample('solid', 0.5, 49)
        original_bonds = dict(model.solid_bonds)
        additions = []
        for dx in (-1.0, 0.0, 1.0):
            molecule = _Particle((100, 100), np.zeros(2))
            additions.append(molecule)
            layout.molecules.append(molecule)
            model.synchronize()
            model.positions[-1] = (model.width * 0.5 + dx, model.height * 0.85)
        for _ in range(180):
            model.synchronize()
            model.advance(1 / 60)
        self.assertFalse(model.falling)
        for molecule in additions:
            self.assertTrue(any(molecule in pair for pair in model.solid_bonds))
        for pair, rest in original_bonds.items():
            a, b = (model.indices[m] for m in pair)
            self.assertLess(abs(np.linalg.norm(model.positions[a] - model.positions[b]) - rest), 0.2)

    def test_turning_forces_off_releases_solid_bonds(self):
        layout, _, model = self.make_sample('solid', 0.15, 49)
        self.assertTrue(model.solid_bonds)
        layout.intermolecular_forces = False
        model.synchronize()
        self.assertFalse(model.solid_bonds)
        self.assertIsNone(model._solid_springs)

    def test_warm_liquid_drop_descends_smoothly_and_joins_the_pool(self):
        layout, _, model = self.make_sample('liquid', 0.65, 49)
        newcomer = _Particle((100, 100), np.zeros(2))
        layout.molecules.append(newcomer)
        model.synchronize()
        index = model.indices[newcomer]
        model.positions[index] = (model.width * 0.5, model.height * 0.85)
        start = model.positions[index, 1]
        for frame in range(240):
            # Match the app, where synchronization runs every frame.
            model.synchronize()
            was_falling = newcomer in model.falling
            before = model.positions[index].copy()
            model.advance(1 / 60)
            if was_falling and newcomer in model.falling:
                self.assertLess(model.positions[index, 1], before[1])
                self.assertLess(abs(model.positions[index, 0] - before[0]), 0.1)
            if frame == 29:
                self.assertGreater(start - model.positions[index, 1], 7.0)
            if frame == 59:
                self.assertNotIn(newcomer, model.falling)
        self.assertNotIn(newcomer, model.falling)
        self.assertLess(model.positions[index, 1], model.height * 0.35)
        self.assertLess(np.quantile(model.positions[:, 1], 0.95), model.height * 0.4)

    def test_turning_forces_off_removes_attraction(self):
        layout, _, model = self.make_sample('gas', 0.0, 2)
        model.positions[:] = ((10, 10), (11.4, 10))
        self.assertGreater(model._accelerations()[0, 0], 0)
        layout.intermolecular_forces = False
        model.synchronize()
        self.assertAlmostEqual(model._accelerations()[0, 0], 0)

    def test_selected_liquid_stays_pooled_when_adding_molecules_raises_temperature(self):
        layout, _, model = self.make_sample('liquid', 0.65, 49)
        layout.temperature = 3.0
        model.synchronize()
        self.assertTrue(model.liquid)
        for _ in range(300):
            model.synchronize()
            model.advance(1 / 60)
        self.assertTrue(model.liquid)
        self.assertFalse(model.solid_bonds)
        self.assertLess(np.quantile(model.positions[:, 1], 0.95), model.liquid_level + 0.5)
        self.assertLess(model.positions[:, 1].max(), model.liquid_level + 1.0)

    def test_liquid_level_grows_when_a_new_drop_reaches_the_pool(self):
        layout, _, model = self.make_sample('liquid', 0.65, 31)
        original_level = model.liquid_level
        newcomer = _Particle((100, 100), np.zeros(2))
        layout.molecules.append(newcomer)
        model.synchronize()
        self.assertIn(newcomer, model.falling)
        self.assertAlmostEqual(model.liquid_level, original_level)
        for _ in range(90):
            model.synchronize()
            model.advance(1 / 60)
        self.assertNotIn(newcomer, model.falling)
        self.assertGreater(model.liquid_level, original_level)

    def test_nearby_pair_forces_match_potential_gradient(self):
        _, beaker, model = self.make_sample('gas', 3.0, 100)

        def potential():
            delta = model.positions[:, None] - model.positions[None, :]
            distances = np.linalg.norm(delta, axis=2)
            distances = distances[np.triu_indices(100, 1)]
            ratio6 = (1 / distances[distances < 2.5]) ** 6
            shift = 4 * ((1 / 2.5) ** 12 - (1 / 2.5) ** 6)
            return np.sum(4 * (ratio6 ** 2 - ratio6) - shift)

        # Also exercise rebuilding the neighbor list after particles move.
        for shift in (0.0, 0.7):
            model.positions += shift
            acceleration = model._accelerations()
            for i in (0, 37, 99):
                for axis in (0, 1):
                    step = 1e-5
                    model.positions[i, axis] += step
                    plus = potential()
                    model.positions[i, axis] -= 2 * step
                    minus = potential()
                    model.positions[i, axis] += step
                    measured = acceleration[i, axis]
                    if axis == 1:
                        measured += beaker.view_gravity()
                    self.assertAlmostEqual(measured, -(plus - minus) / (2 * step), places=6)

    def test_glass_contains_hot_particles_in_both_views(self):
        _, beaker, model = self.make_sample('gas', 3.0, 49)
        for orientation in ('side', TOP):
            with self.subTest(orientation=orientation):
                beaker.orientation = orientation
                model.synchronize()
                for _ in range(180):
                    model.advance(1 / 60)
                    self.assertTrue(np.all(np.isfinite(model.positions)))
                    self.assertTrue(all(model._fits(p) for p in model.positions))

    def test_add_remove_and_render_preserve_existing_particles(self):
        layout, _, model = self.make_sample('gas', 3.0, 20)
        original_particles = tuple(layout.molecules)
        original_positions = model.positions.copy()
        model.synchronize()
        np.testing.assert_array_equal(model.positions, original_positions)

        extra = _Particle((100, 100), np.array((50, -50)))
        layout.molecules.append(extra)
        model.synchronize()
        self.assertEqual(len(model.indices), 21)
        np.testing.assert_array_equal(model.positions[:-1], original_positions)
        self.assertTrue(all(model._fits(p) for p in model.positions))
        distances = np.linalg.norm(model.positions[:-1] - model.positions[-1], axis=1)
        self.assertGreaterEqual(distances.min(), 1.13)

        layout.molecules.remove(original_particles[3])
        model.synchronize()
        self.assertNotIn(original_particles[3], model.indices)
        self.assertIn(extra, model.indices)
        np.testing.assert_array_equal(model.positions[:3], original_positions[:3])
        layout.molecules.clear()
        model.synchronize()
        self.assertEqual(model.positions.shape, (0, 2))
        self.assertFalse(model.indices)

    def test_flask_physics_does_not_change_board_particles(self):
        layout, _, model = self.make_sample('liquid', 0.65, 48)
        positions = [m.pos for m in layout.molecules]
        velocities = np.array([m.total_velocity.copy() for m in layout.molecules])
        for _ in range(30):
            model.advance(1 / 60)
        self.assertEqual([m.pos for m in layout.molecules], positions)
        np.testing.assert_array_equal(
            np.array([m.total_velocity for m in layout.molecules]), velocities)

    def test_phases_differ_in_mobility_and_vertical_distribution(self):
        observations = {}
        for phase, temperature in (('solid', 0.15), ('liquid', 0.65), ('gas', 3.0)):
            _, _, model = self.make_sample(phase, temperature, 49)
            for _ in range(300):
                model.advance(1 / 60)
            initial = model.positions.copy()
            for _ in range(300):
                model.advance(1 / 60)
            final = model.positions
            initial_distances = np.linalg.norm(initial[:, None] - initial[None, :], axis=2)
            final_distances = np.linalg.norm(final[:, None] - final[None, :], axis=2)
            neighbors = (initial_distances > 0) & (initial_distances < 1.5)
            retention = np.sum(neighbors & (final_distances < 1.5)) / np.sum(neighbors)
            displacement = ((final - final.mean(axis=0))
                            - (initial - initial.mean(axis=0)))
            observations[phase] = (
                retention, np.mean(np.sum(displacement ** 2, axis=1)),
                np.ptp(final[:, 1]))

        # Solid particles keep their neighbors and vibrate in place. Liquid
        # particles exchange neighbors; gas explores much more of the height.
        self.assertGreater(observations['solid'][0], 0.8)
        self.assertLess(observations['liquid'][0], 0.6)
        self.assertGreater(observations['liquid'][1], observations['solid'][1] * 10)
        self.assertGreater(observations['gas'][2], observations['liquid'][2] + 3)

    def test_heating_can_disperse_a_solid_without_changing_its_preset(self):
        layout, _, model = self.make_sample('solid', 0.15, 49)
        cold_height = np.ptp(model.positions[:, 1])
        layout.temperature = 3.0
        model.synchronize()
        self.assertFalse(model.solid_bonds)
        for _ in range(600):
            model.advance(1 / 60)
        self.assertEqual(layout._projection_phase, 'solid')
        self.assertGreater(np.ptp(model.positions[:, 1]), cold_height + 4)


if __name__ == '__main__':
    unittest.main()
