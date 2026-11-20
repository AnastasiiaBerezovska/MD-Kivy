"""A gravity-driven phase view of the main board's molecules.

Each board molecule has one particle here. These positions and velocities are
separate: compressing the board into a tiny flask must not inject energy into
the board's thermodynamic readouts. Temperature drives the motion, with extra
viscosity and a free surface to keep the selected liquid phase readable.
Solid neighbors stay bonded, while liquid neighbors can slide past each other.
"""

import math

import numpy as np


class BeakerDynamics:
    MAX_STEP = 0.006
    TIME_SCALE = 4.0
    DRAG = 1.0
    VELOCITY_UNIT = 50.0
    SOLID_STIFFNESS = 80.0
    LIQUID_VISCOSITY = 0.8

    def __init__(self, beaker, seed=None):
        self.beaker = beaker
        self.rng = np.random.default_rng(seed)
        self.clear()

    def clear(self):
        self.molecules = ()
        self.indices = {}
        self.positions = np.empty((0, 2))
        self.velocities = np.empty((0, 2))
        self.width = self.height = 22.0
        self.radius = 0.46
        self.orientation = self.beaker.orientation
        self.temperature = 0.0
        self.bath_temperature = 0.0
        self.liquid_level = 0.0
        self.drag = self.DRAG
        self.time_scale = self.TIME_SCALE
        self.unselected = False
        self.drop_speed = 0.1
        self.liquid = False
        self.solid = False
        self.solid_bonds = {}
        self._solid_springs = None
        self._liquid_pairs = None
        self.falling = set()
        self._pairs = None
        self._pair_settings = None

    def synchronize(self):
        """Keep identities and material parameters in sync without moving the board."""
        layout = self.beaker.layout
        molecules = tuple(layout.molecules)
        _, _, pixel_width, pixel_height = self.beaker.outer
        if pixel_width <= 0 or pixel_height <= 0:
            return

        self.radius = 0.46 * math.sqrt(max(layout.size_factor, 0.01) / 0.6)
        size_scale = self.radius / 0.46
        # Zoom out only when the sample would otherwise overcrowd the flask.
        width = max(22.0, 2.3 * math.sqrt(len(molecules))
                    * max(size_scale, layout.sigma * size_scale))
        height = width * pixel_height / pixel_width
        self.positions *= (width / self.width, height / self.height)
        self.width, self.height = width, height
        self.wall = self.beaker.wall / pixel_width * width * 0.5
        self.temperature = max(0.0, layout._thermodynamic_metrics()[1])
        phase = layout._projection_phase
        self.unselected = phase is None
        self.time_scale = 2.0 if phase in (None, 'gas') else self.TIME_SCALE
        # Adding molecules must not silently turn the selected liquid into gas.
        self.liquid = (phase == 'liquid' and layout.intermolecular_forces
                       and layout.epsilon > 0)
        self.solid = (phase == 'solid' and layout.intermolecular_forces
                      and self.temperature < 2 * layout.epsilon)
        self.drag = self.DRAG
        self.bath_temperature = self.temperature
        self.drop_speed = 0.1
        if self.unselected:
            self.drag = 2.0
            self.bath_temperature = min(self.temperature, 0.15)
            self.drop_speed = 0.6
        elif self.liquid:
            self.drag = 3.0
            self.bath_temperature = min(self.temperature, 0.85 * layout.epsilon)
            self.drop_speed = 5.0
        elif self.solid:
            self.drag = 0.35
            self.drop_speed = 4.5
        self.falling.intersection_update(molecules)
        if not (self.liquid or self.solid):
            self.falling.clear()
        present = set(molecules)
        self.solid_bonds = {pair: rest for pair, rest in self.solid_bonds.items()
                            if self.solid and all(m in present for m in pair)}
        if not self.solid:
            self._solid_springs = None

        old_indices = self.indices
        old_positions, old_velocities = self.positions, self.velocities
        self.positions = np.zeros((len(molecules), 2))
        self.velocities = np.zeros((len(molecules), 2))
        self.molecules = molecules
        self.indices = {molecule: i for i, molecule in enumerate(molecules)}
        self.sigmas = np.array([
            (layout.sigma if m.sig is None else m.sig) * size_scale
            for m in molecules])
        self.epsilons = np.array([
            max(0.0, layout.epsilon if m.eps is None else m.eps)
            for m in molecules])
        self.forces_enabled = layout.intermolecular_forces
        pair_settings = (molecules, tuple(self.sigmas), tuple(self.epsilons),
                         bool(self.forces_enabled), self.radius)
        if pair_settings != self._pair_settings:
            self._pairs = None
            self._pair_settings = pair_settings

        switched_view = self.orientation != self.beaker.orientation
        self.orientation = self.beaker.orientation
        if switched_view:
            self.falling.clear()
            self.solid_bonds.clear()
        added = []
        for i, molecule in enumerate(molecules):
            if molecule in old_indices and not switched_view:
                old = old_indices[molecule]
                self.positions[i] = old_positions[old]
                self.velocities[i] = old_velocities[old]
            else:
                added.append(i)

        if not old_indices or switched_view:
            phase = layout._projection_phase
            if (phase in ('solid', 'liquid')
                    and (self.orientation == 'side' or phase == 'solid')):
                self._seed_cluster(molecules, size_scale)
                added = []

        occupied = [i for i in range(len(molecules)) if i not in added]
        dropping = (self.orientation == 'side' and not switched_view
                    and (bool(old_indices) or layout._projection_phase is None))
        for i in added:
            self.positions[i] = self._spawn_position(occupied, i, dropping)
            if dropping:
                self.velocities[i] = (0.0, -self.drop_speed)
                if self.liquid or self.solid:
                    self.falling.add(molecules[i])
            else:
                self.velocities[i] = (
                    np.asarray(molecules[i].total_velocity) / self.VELOCITY_UNIT)
                if self.unselected:
                    self.velocities[i] *= 0.35
            occupied.append(i)
        self._resolve_walls()
        self.liquid_level = self._pool_level() if self.liquid else 0.0
        if self.solid:
            if not self.solid_bonds:
                self._bond_solid()
            else:
                self._cache_solid_bonds()

    def _seed_cluster(self, molecules, size_scale):
        if not molecules:
            return
        layout = self.beaker.layout
        points = np.array([m.pos for m in molecules], dtype=float)
        points -= points.min(axis=0)
        points *= size_scale / max(layout.scale, 1e-9)
        span = np.ptp(points, axis=0)
        if (layout._projection_phase == 'liquid'
                or span[0] > self.width * 0.65 or span[1] > self.height * 0.7):
            self._seed_bottom_rows(len(molecules))
        else:
            points[:, 0] += (self.width - span[0]) * 0.5
            if self.orientation == 'top':
                points[:, 1] += (self.height - span[1]) * 0.5
            else:
                points[:, 1] += self.wall + self.radius + 1e-8
            self.positions[:] = points
        self.velocities[:] = np.array([
            m.total_velocity for m in molecules]) / self.VELOCITY_UNIT
        if self.liquid:
            self.velocities *= 0.4

    def _pool_level(self):
        """Find the surface height from the amount of settled liquid."""
        settled = [i for i, m in enumerate(self.molecules) if m not in self.falling]
        pad = self.wall + self.radius
        if not settled:
            return pad
        heights = np.linspace(pad, self.height - pad, 64)
        bounds = np.array([self.beaker.profile_bounds(y / self.height) for y in heights])
        slopes = np.where(heights < self.height * 0.6, 0.3 * self.width / self.height, 0)
        widths = np.maximum(0, (bounds[:, 1] - bounds[:, 0]) * self.width
                            - 2 * pad * np.sqrt(1 + slopes ** 2))
        areas = np.concatenate(([0], np.cumsum(
            0.5 * (widths[1:] + widths[:-1]) * np.diff(heights))))
        volume = 1.35 * np.sum(self.sigmas[settled] ** 2)
        return float(np.interp(volume, areas, heights))

    def _seed_bottom_rows(self, count):
        """Fill the wide base first so liquid starts as a shallow pool."""
        pad = self.wall + self.radius
        spacing = max(2.1 * self.radius, 1.16 * 2 ** (1 / 6) * max(self.sigmas))
        row_height = spacing * math.sqrt(3) / 2
        points = []
        for y in np.arange(pad + 1e-8, self.height - pad, row_height):
            lo, hi = self.beaker.profile_bounds(y / self.height)
            slope = 0.3 * self.width / self.height if y < self.height * 0.6 else 0
            margin = pad * math.sqrt(1 + slope * slope) + 1e-8
            left, right = lo * self.width + margin, hi * self.width - margin
            columns = min(count - len(points), int((right - left) / spacing) + 1)
            for col in range(columns):
                x = (left + right) * 0.5 + (col - (columns - 1) * 0.5) * spacing
                points.append((x, y))
            if len(points) == count:
                self.positions[:] = points
                return
        raise ValueError('No space for the beaker sample at the bottom')

    def _bond_solid(self):
        """Keep the solid's neighboring molecules at their lattice spacing."""
        first, second = np.triu_indices(len(self.molecules), 1)
        distances = np.linalg.norm(self.positions[first] - self.positions[second], axis=1)
        contact = 1.35 * (self.sigmas[first] + self.sigmas[second]) * 0.5
        for a, b, distance in zip(first[distances < contact],
                                  second[distances < contact], distances[distances < contact]):
            pair = (self.molecules[a], self.molecules[b])
            if not any(m in self.falling for m in pair):
                self.solid_bonds.setdefault(pair, float(distance))
        self._cache_solid_bonds()

    def _cache_solid_bonds(self):
        if not self.solid_bonds:
            self._solid_springs = None
            return
        pairs = np.array([(self.indices[a], self.indices[b]) for a, b in self.solid_bonds])
        self._solid_springs = pairs[:, 0], pairs[:, 1], np.array(list(self.solid_bonds.values()))

    def _stick_to_solid(self, index, settled):
        """Attach an arriving molecule to a free site on the crystal's surface."""
        if not settled:
            return True
        angles = np.arange(6) * math.pi / 3
        directions = np.column_stack((np.cos(angles), np.sin(angles)))
        spacing = 2 ** (1 / 6) * (self.sigmas[settled] + self.sigmas[index]) * 0.5
        sites = (self.positions[settled, None, :]
                 + spacing[:, None, None] * directions).reshape(-1, 2)
        sites = np.array([point for point in sites if self._fits(point)])
        if not len(sites):
            return False
        distances = np.linalg.norm(sites[:, None] - self.positions[settled], axis=2)
        clearance = np.maximum(2 * self.radius, 0.94 * spacing)
        sites = sites[np.all(distances >= clearance, axis=1)]
        if not len(sites):
            return False
        distance2 = np.sum((sites - self.positions[index]) ** 2, axis=1)
        nearest = np.argmin(distance2)
        if distance2[nearest] > (2 * self.sigmas[index]) ** 2:
            return False
        self.positions[index] = sites[nearest]
        self.velocities[index] = np.mean(self.velocities[settled], axis=0)
        return True

    def _spawn_position(self, occupied, index, dropping=False):
        """Insert above a condensed sample, with no overlapping repulsive cores."""
        pad = self.wall + self.radius
        # New particles fall into an existing sample. Initial gas particles
        # occupy the whole vessel, rather than a lattice disguised as a gas.
        low = max(pad, self.height * 0.65) if dropping else pad
        for bottom in (low, pad) if dropping else (pad,):
            for _ in range(250):
                point = self.rng.uniform((self.width * 0.1 + pad, bottom),
                                         (self.width * 0.9 - pad,
                                          max(bottom, self.height - pad)))
                if not self._fits(point):
                    continue
                if occupied:
                    separations = np.maximum(
                        2.0 * self.radius,
                        1.13 * (self.sigmas[occupied] + self.sigmas[index]) * 0.5)
                    distances = np.linalg.norm(self.positions[occupied] - point, axis=1)
                    if np.any(distances < separations):
                        continue
                return point
        # Search the entire vessel if the upper region has filled up.
        step = max(2.05 * self.radius, 1.14 * max(self.sigmas, default=1.0))
        for y in np.arange(pad, self.height - pad, step * math.sqrt(3) / 2):
            for x in np.arange(pad, self.width - pad, step):
                point = np.array((x, y))
                if self._fits(point) and (not occupied or np.all(
                        np.linalg.norm(self.positions[occupied] - point, axis=1)
                        >= step)):
                    return point
        raise ValueError('No non-overlapping space for the beaker sample')

    def _fits(self, point):
        pad = self.wall + self.radius
        x, y = point
        if self.orientation == 'top':
            radius = min(self.width, self.height) * 0.46 - pad
            return math.hypot(x - self.width / 2, y - self.height / 2) <= radius
        if not pad <= y <= self.height - pad:
            return False
        lo, hi = self.beaker.profile_bounds(y / self.height)
        slope = 0.3 * self.width / self.height if y < self.height * 0.6 else 0.0
        margin = pad * math.sqrt(1.0 + slope * slope)
        return lo * self.width + margin <= x <= hi * self.width - margin

    def _find_pairs(self):
        """Cache nearby pairs until a particle has moved half the spare distance."""
        n = len(self.molecules)
        self._pair_reference = self.positions.copy()
        self._pair_skin = max(1.0, 2 * self.radius)
        if n < 80:
            first, second = np.triu_indices(n, 1)
        else:
            cutoff = (2.5 * max(self.sigmas) if self.forces_enabled
                      else 2 * self.radius)
            cell_size = cutoff + self._pair_skin
            cells = {}
            for i, point in enumerate(self.positions):
                key = tuple(np.floor(point / cell_size).astype(int))
                cells.setdefault(key, []).append(i)
            pairs = []
            for (cx, cy), members in cells.items():
                pairs.extend((i, j) for k, i in enumerate(members)
                             for j in members[k + 1:])
                for dx, dy in ((0, 1), (1, -1), (1, 0), (1, 1)):
                    neighbors = cells.get((cx + dx, cy + dy), ())
                    pairs.extend((i, j) for i in members for j in neighbors)
            indices = np.array(pairs, dtype=int).reshape(-1, 2)
            if len(indices):
                displacement = self.positions[indices[:, 0]] - self.positions[indices[:, 1]]
                nearby = np.sum(displacement ** 2, axis=1) < cell_size ** 2
                indices = indices[nearby]
            first, second = indices.T

        if self.forces_enabled:
            sigma = (self.sigmas[first] + self.sigmas[second]) * 0.5
            epsilon = np.sqrt(self.epsilons[first] * self.epsilons[second])
            cutoff2 = (2.5 * sigma) ** 2
        else:
            # With Forces Off, contacts repel but have no cohesive tail.
            sigma = 2 * self.radius / 2 ** (1 / 6)
            epsilon = 1.0
            cutoff2 = (2 * self.radius) ** 2
        self._pairs = first, second, sigma, epsilon, cutoff2

    def _accelerations(self):
        n = len(self.molecules)
        self._liquid_pairs = None
        result = np.zeros((n, 2))
        result[:, 1] = -self.beaker.view_gravity()
        if self.unselected and self.orientation == 'side':
            result[:, 1] -= 2.1
        if self.liquid and self.orientation == 'side':
            result[:, 1] -= 0.3
            settled = np.array([m not in self.falling for m in self.molecules], dtype=bool)
            above_surface = np.maximum(self.positions[:, 1] - self.liquid_level, 0)
            result[settled, 1] -= 18 * above_surface[settled]
        if self.falling and self.orientation == 'side':
            indices = [self.indices[molecule] for molecule in self.falling]
            result[indices, 1] -= 4.2 if self.liquid else 2.7
        if n < 2:
            return result
        if (self._pairs is None or (n >= 80 and np.any(
                np.sum((self.positions - self._pair_reference) ** 2, axis=1)
                > (self._pair_skin * 0.5) ** 2))):
            self._find_pairs()
        first, second, sigma, epsilon, cutoff2 = self._pairs
        diff = self.positions[first] - self.positions[second]
        distance2 = np.sum(diff * diff, axis=1)
        mask = (distance2 > 1e-12) & (distance2 < cutoff2)
        safe2 = np.maximum(distance2, (0.72 * sigma) ** 2)
        ratio6 = (sigma * sigma / safe2) ** 3
        scalar = np.where(mask, 24 * epsilon * (2 * ratio6 ** 2 - ratio6) / safe2, 0.0)
        pair_forces = scalar[:, None] * diff
        if self.liquid:
            distance = np.sqrt(distance2)
            weight = np.maximum(0, 1 - distance / (2 * sigma))
            settled = np.array([m not in self.falling for m in self.molecules], dtype=bool)
            weight *= settled[first] & settled[second]
            relative_velocity = self.velocities[second] - self.velocities[first]
            pair_forces += self.LIQUID_VISCOSITY * weight[:, None] * relative_velocity
            active = weight > 0
            self._liquid_pairs = first[active], second[active], weight[active]
        forces = np.column_stack([
            np.bincount(first, weights=pair_forces[:, axis], minlength=n)
            - np.bincount(second, weights=pair_forces[:, axis], minlength=n)
            for axis in (0, 1)])
        if self._solid_springs is not None:
            a, b, rest = self._solid_springs
            displacement = self.positions[a] - self.positions[b]
            length2 = np.maximum(np.sum(displacement ** 2, axis=1), 1e-12)
            length = np.sqrt(length2)
            relative_velocity = self.velocities[a] - self.velocities[b]
            damping = 2 * np.sum(relative_velocity * displacement, axis=1) / length2
            pull = -self.SOLID_STIFFNESS * (length - rest) / length - damping
            spring_forces = pull[:, None] * displacement
            np.add.at(forces, a, spring_forces)
            np.add.at(forces, b, -spring_forces)
        # Guard against abrupt slider changes pushing particles into a core.
        magnitude = np.linalg.norm(forces, axis=1)
        forces *= np.minimum(1.0, 2000 / np.maximum(magnitude, 1e-12))[:, None]
        return result + forces

    def _reflect(self, hit, normal, penetration):
        if not np.any(hit):
            return
        normals = np.broadcast_to(normal, self.positions.shape)[hit]
        self.positions[hit] += penetration[hit, None] * normals
        incoming = np.sum(self.velocities[hit] * normals, axis=1)
        restitution = np.ones(np.count_nonzero(hit))
        if self.falling:
            for j, i in enumerate(np.flatnonzero(hit)):
                if self.molecules[i] in self.falling:
                    restitution[j] = 0.15
        bounce = (1 + restitution) * np.minimum(incoming, 0)
        self.velocities[hit] -= bounce[:, None] * normals

    def _land_drops(self):
        """Join the liquid pool or attach to the solid when a drop lands."""
        settled = [i for i, molecule in enumerate(self.molecules)
                   if molecule not in self.falling]
        attached = False
        for molecule in self.molecules:
            if molecule not in self.falling:
                continue
            i = self.indices[molecule]
            on_floor = self.positions[i, 1] <= self.wall + self.radius + 1e-6
            touching_pool = False
            if settled:
                distance = np.linalg.norm(self.positions[settled] - self.positions[i], axis=1)
                contact = np.maximum(2 * self.radius,
                                     1.35 * (self.sigmas[settled] + self.sigmas[i]) * 0.5)
                touching_pool = np.any(distance <= contact)
            if on_floor or touching_pool:
                if self.solid and not self._stick_to_solid(i, settled):
                    continue
                self.falling.remove(molecule)
                if self.liquid:
                    self.velocities[i] *= 0.2
                settled.append(i)
                attached = True
        if self.solid and attached:
            self._bond_solid()
        if self.liquid and attached:
            self.liquid_level = self._pool_level()

    def _resolve_walls(self):
        """Reflect from the actual sloped glass, including its finite thickness."""
        if not len(self.molecules):
            return
        pad = self.radius + self.wall + 1e-9
        if self.orientation == 'top':
            center = np.array((self.width, self.height)) * 0.5
            displacement = self.positions - center
            distance = np.linalg.norm(displacement, axis=1)
            limit = min(self.width, self.height) * 0.46 - pad
            normals = -displacement / np.maximum(distance[:, None], 1e-12)
            self._reflect(distance > limit, normals, distance - limit)
            return
        for _ in range(3):
            y = self.positions[:, 1]
            self._reflect(y < pad, (0, 1), pad - y)
            y = self.positions[:, 1]
            # Keep the observed gas sample within the rim, as in the inset's
            # original count-preserving projection.
            self._reflect(y > self.height - pad, (0, -1), y - self.height + pad)
            for sign in (1, -1):
                x, y = self.positions.T
                v = np.clip(y / self.height, 0, 1)
                left = np.where(v < 0.6, 0.1 + 0.3 * v, 0.28) * self.width
                slope = np.where(v < 0.6, 0.3 * self.width / self.height, 0.0)
                norm = np.sqrt(1 + slope * slope)
                wall_x = left if sign == 1 else self.width - left
                distance = sign * (x - wall_x) / norm
                normals = np.column_stack((sign / norm, -slope / norm))
                self._reflect(distance < pad, normals, pad - distance)

    def advance(self, dt):
        """Substepped Langevin/Verlet motion; called only by the running simulation."""
        if not self.molecules or dt <= 0:
            return
        duration = min(float(dt), 0.1) * self.time_scale
        steps = max(1, math.ceil(duration / self.MAX_STEP))
        step = duration / steps
        decay = math.exp(-self.drag * step)
        noise = math.sqrt(self.bath_temperature * (1 - decay * decay))
        drop_decay = math.exp(-1.2 * step) if self.liquid else decay
        acceleration = self._accelerations()
        for _ in range(steps):
            self.velocities += acceleration * (step * 0.5)
            self.positions += self.velocities * (step * 0.5)
            self._resolve_walls()
            self.velocities *= decay
            kicks = self.rng.normal(0, noise, self.velocities.shape)
            if self.falling:
                indices = [self.indices[molecule] for molecule in self.falling]
                self.velocities[indices] *= drop_decay / decay
                kicks[indices] = 0
            self.velocities += kicks
            if self._liquid_pairs is not None:
                # Balance the neighbor drag so liquid can flow without freezing.
                a, b, weight = self._liquid_pairs
                scale = np.sqrt(2 * self.LIQUID_VISCOSITY
                                * weight * self.bath_temperature * step)
                exchange = self.rng.normal(size=(len(a), 2)) * scale[:, None]
                np.add.at(self.velocities, a, exchange)
                np.add.at(self.velocities, b, -exchange)
            self.positions += self.velocities * (step * 0.5)
            self._resolve_walls()
            if self.falling:
                self._land_drops()
            acceleration = self._accelerations()
            self.velocities += acceleration * (step * 0.5)

    def geometry(self, molecule):
        x, y, pixel_width, _ = self.beaker.outer
        scale = pixel_width / self.width
        px, py = self.positions[self.indices[molecule]]
        return x + px * scale, y + py * scale, self.radius * scale
