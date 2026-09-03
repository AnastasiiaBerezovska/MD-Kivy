"""Flask-shaped boundary for sandbox molecules."""

import math
from random import uniform

from kivy.vector import Vector

SIDE = 'side'
TOP  = 'top'

_FLOOR_L, _FLOOR_R = 0.10, 0.90
_NECK_L,  _NECK_R  = 0.28, 0.72
_SHOULDER          = 0.60


class Beaker:

    rect_prop = (0.755, 0.050, 0.230, 0.42)
    wall_prop = 0.055
    restitution = 1.0
    # A gentle visual settling force. The previous value (420 px/s²) heated a
    # nominal solid above the gas preset when it fell into the flask.
    gravity_strength = 10.0

    def __init__(self, layout):
        self.layout = layout
        self.orientation = SIDE
        self.active = True


    @property
    def outer(self):
        """(x, y, w, h) of the flask's bounding box, in window coordinates."""
        lx, ly = self.layout.pos
        lw, lh = self.layout.size
        px, py, pw, ph = self.rect_prop
        return (lx + lw * px, ly + lh * py, lw * pw, lh * ph)

    @property
    def wall(self):
        return max(4.0, self.outer[2] * self.wall_prop)

    def _p(self, u, v):
        """Unit coordinates -> window coordinates."""
        x, y, w, h = self.outer
        return (x + w * u, y + h * v)

    @property
    def outline(self):
        """Flask profile, left rim down round the floor and up to the right rim."""
        return [
            self._p(_NECK_L, 1.0), self._p(_NECK_L, _SHOULDER),
            self._p(_FLOOR_L, 0.0), self._p(_FLOOR_R, 0.0),
            self._p(_NECK_R, _SHOULDER), self._p(_NECK_R, 1.0),
        ]

    @property
    def segments(self):
        """Wall segments molecules collide with."""
        if self.orientation == TOP:
            return []
        pts = self.outline
        return list(zip(pts[:-1], pts[1:]))

    @property
    def top_circle(self):
        """(cx, cy, r) of the bird's-eye boundary."""
        x, y, w, h = self.outer
        r = min(w, h) * 0.46
        return (x + w * 0.5, y + h * 0.5, r)

    @property
    def interior_area(self):
        """Approximate 2-D container area used by the pressure calculation."""
        if self.orientation == TOP:
            _, _, radius = self.top_circle
            return math.pi * radius * radius

        points = self.outline
        twice_area = 0.0
        for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]):
            twice_area += x1 * y2 - x2 * y1
        return abs(twice_area) * 0.5

    def contains(self, cx, cy):
        """Is this point inside the glass?"""
        if self.orientation == TOP:
            ox, oy, r = self.top_circle
            return (cx - ox) ** 2 + (cy - oy) ** 2 <= r * r
        return self._in_profile(cx, cy)

    def _in_profile(self, cx, cy):
        x, y, w, h = self.outer
        if not (y <= cy <= y + h):
            return False
        v = (cy - y) / h if h else 0.0
        if v >= _SHOULDER:
            lo, hi = _NECK_L, _NECK_R
        else:
            f = v / _SHOULDER if _SHOULDER else 0.0
            lo = _FLOOR_L + (_NECK_L - _FLOOR_L) * f
            hi = _FLOOR_R + (_NECK_R - _FLOOR_R) * f
        u = (cx - x) / w if w else 0.0
        return lo <= u <= hi


    def collide(self, mol):
        """Keep a molecule out of the glass, from whichever side it approaches."""
        if self.orientation == TOP:
            return self._resolve_ring(mol)
        hit = False
        half = self.wall * 0.5
        # corners may need another pass
        for _ in range(3):
            moved = False
            for p1, p2 in self.segments:
                if self._resolve_segment(mol, p1, p2, half):
                    moved = hit = True
            if not moved:
                break
        return hit

    def _resolve_segment(self, mol, p1, p2, half):
        """Circle vs. a thick line segment."""
        cx, cy = mol.pos
        r = mol.radius + half
        x1, y1 = p1
        x2, y2 = p2
        dx, dy = x2 - x1, y2 - y1
        seg2 = dx * dx + dy * dy
        t = 0.0 if seg2 < 1e-9 else max(0.0, min(1.0, ((cx - x1) * dx + (cy - y1) * dy) / seg2))
        nx, ny = x1 + t * dx, y1 + t * dy
        ox, oy = cx - nx, cy - ny
        d2 = ox * ox + oy * oy
        if d2 >= r * r:
            return False

        if d2 > 1e-9:
            d = math.sqrt(d2)
            ux, uy = ox / d, oy / d
            push = r - d
        else:
            ln = math.sqrt(seg2) or 1.0
            ux, uy = -dy / ln, dx / ln
            push = r

        mol.pos = (cx + ux * push, cy + uy * push)
        vx, vy = mol.total_velocity.x, mol.total_velocity.y
        vn = vx * ux + vy * uy
        if vn < 0:
            k = (1.0 + self.restitution) * vn
            mol.total_velocity = Vector(vx - k * ux, vy - k * uy)
        return True

    def _resolve_ring(self, mol):
        """Bird's-eye: hold the molecule inside the circular wall."""
        ox, oy, R = self.top_circle
        cx, cy = mol.pos
        dx, dy = cx - ox, cy - oy
        d = math.hypot(dx, dy)
        if d < 1e-9:
            return False
        inner = R - self.wall * 0.5 - mol.radius
        outer = R + self.wall * 0.5 + mol.radius
        if d < R:
            if d <= inner:
                return False
            limit, outward = inner, True
        else:
            if d >= outer:
                return False
            limit, outward = outer, False
        ux, uy = dx / d, dy / d
        mol.pos = (ox + ux * limit, oy + uy * limit)
        vx, vy = mol.total_velocity.x, mol.total_velocity.y
        vn = vx * ux + vy * uy
        if (vn > 0) if outward else (vn < 0):
            k = (1.0 + self.restitution) * vn
            mol.total_velocity = Vector(vx - k * ux, vy - k * uy)
        return True


    def _sample(self, n, min_sep=0.0):
        """Random points well inside the glass."""
        x, y, w, h = self.outer
        # leave room for the glass wall
        pad = self.layout.molecule_radius + self.wall
        out = []
        for _ in range(n * 60):
            if len(out) >= n:
                break
            px, py = uniform(x + pad, x + w - pad), uniform(y + pad, y + h - pad)
            if (self.contains(px, py) and self.contains(px - pad, py)
                    and self.contains(px + pad, py) and self.contains(px, py - pad)
                    and all((px - ox) ** 2 + (py - oy) ** 2 >= min_sep ** 2
                            for ox, oy in out)):
                out.append((px, py))
        return out

    def fill(self, phase):
        """Fill the glass with a solid, liquid or gas.

        Selecting a phase is a true preset reset: old molecules are removed so
        the measurements describe only the selected material and phase.
        """
        layout = self.layout
        off = 50

        layout.clear_molecules()

        eps = layout.SUBSTANCE_EPSILON
        sig = layout.SUBSTANCE_SIGMA
        target_temperature = {
            'solid': layout.SOLID_TEMPERATURE,
            'liquid': layout.LIQUID_TEMPERATURE,
            'gas': layout.GAS_TEMPERATURE,
        }[phase]
        new_molecules = []

        if phase == 'solid':
            spacing = max((2 ** (1 / 6)) * sig * layout.scale,
                          2.0 * layout.molecule_radius)
            x, y, w, h = self.outer
            pad = layout.molecule_radius + self.wall
            dy = spacing * (3 ** 0.5) / 2.0
            row, cy = 0, y + pad
            while cy <= y + h - pad:
                cx = x + pad + (spacing / 2 if row % 2 else 0)
                while cx <= x + w - pad:
                    # The whole molecule, not just its centre, must start clear
                    # of the sloped glass. Otherwise the first wall-resolution
                    # pass pushes edge particles into their neighbours and the
                    # LJ r^-12 term produces an enormous energy/pressure spike.
                    if (self.contains(cx, cy)
                            and self.contains(cx - pad, cy)
                            and self.contains(cx + pad, cy)
                            and self.contains(cx, cy - pad)):
                        layout.create_molecule(cx + off, cy + off, 0, 0,
                                               eps=eps, sig=sig, thermo=False)
                        new_molecules.append(layout.molecules[-1])
                    cx += spacing
                row += 1
                cy = y + pad + row * dy
            layout._set_phase_temperature(new_molecules, target_temperature)
            return

        count = 14 if phase == 'liquid' else 7
        min_sep = max(1.25 * sig * layout.scale, 2.1 * layout.molecule_radius)

        for px, py in self._sample(count, min_sep=min_sep):
            layout.create_molecule(px + off, py + off, 0, 0,
                                   eps=eps, sig=sig, thermo=False)
            new_molecules.append(layout.molecules[-1])
        layout._set_phase_temperature(new_molecules, target_temperature)

    def view_gravity(self):
        """Head-on view supplies its own pull; the gravity slider tops out at
        10 px/s^2, far too gentle to settle molecules into a vessel."""
        if self.active and self.orientation == SIDE:
            return self.gravity_strength
        return 0.0
