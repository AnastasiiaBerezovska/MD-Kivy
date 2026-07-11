from kivy.uix.widget import Widget
from kivy.vector import Vector
from kivy.graphics import Color, Ellipse, Rectangle, Line
from kivy.properties import NumericProperty, ListProperty, BooleanProperty

class Molecule(Widget):
    color_slow = [5, 0, 102, 255]
    color_fast = [255, 81, 220, 255]
    color = ListProperty([x / 255 for x in color_fast])
    speed_cap = 500
    force_cap = 30000

    def __init__(self, **kwargs):
        self.center = kwargs.pop("molecule_center")
        self.radius = kwargs.pop("molecule_radius")
        self.total_velocity = Vector(kwargs.pop("molecule_vx"), kwargs.pop("molecule_vy"))
        self.parentpos = kwargs.pop("parent_pos")
        self.parentsize = kwargs.pop("parent_size")
        self.forces_visible = kwargs.pop("forces_visible")

        super().__init__(**kwargs)

        self.size = (self.radius * 2, self.radius * 2)
        self.total_force = Vector(0, 0)

        self._draw_sphere()

    def _draw_sphere(self):
        # Draws the molecule as a pseudo-3D sphere using stacked circles.
        # Note: self.pos is the visual center of the molecule
        # (a quirk of this codebase - Kivy normally uses bottom-left).
        r, g, b = self.color[0], self.color[1], self.color[2]
        cx, cy = self.pos[0], self.pos[1]
        rad = self.radius

        with self.canvas:
        # Glow around the molecule, matching its color
            self.glow_color = Color(r, g, b, 0.18)
            gr = rad * 1.55
            self.glow_shape = Ellipse(pos=(cx - gr, cy - gr), size=(gr * 2, gr * 2))

            # Dark base so the molecule doesn't look like a flat circle
            self.base_color = Color(r * 0.15, g * 0.15, b * 0.15, 1.0)
            self.base_shape = Ellipse(pos=(cx - rad, cy - rad), size=(rad * 2, rad * 2))

            # Main color of the ball - slightly smaller and shifted to fake a curved surface
            self.color_instruction = Color(r, g, b, 1.0)
            mr = rad * 0.85
            self.molecule_shape = Ellipse(
                pos=(cx - mr + rad * 0.04, cy - mr + rad * 0.06),
                size=(mr * 2, mr * 2)
            )

            self.arrow_color = Color(0, 0.8, 1, 0)  # alpha 0 = hidden until toggled on
            self.arrow_line = Line(points=[], width=max(1.0, 1.2 * rad / 10), cap='none')

    def _update_shape_positions(self):
        # Move all sphere layers to follow the molecule
        cx, cy = self.pos[0], self.pos[1]
        rad = self.radius

        gr = rad * 1.55
        self.glow_shape.pos  = (cx - gr, cy - gr)
        self.glow_shape.size = (gr * 2, gr * 2)

        self.base_shape.pos  = (cx - rad, cy - rad)
        self.base_shape.size = (rad * 2, rad * 2)
        

        mr = rad * 0.85
        self.molecule_shape.pos  = (cx - mr + rad * 0.04, cy - mr + rad * 0.06)
        self.molecule_shape.size = (mr * 2, mr * 2)

    def fix_speed(self):
        try:
            spd = self.total_velocity.length()
        except (OverflowError, ValueError):
            self.total_velocity = Vector(0, 0)
            return
        if spd > self.speed_cap:
            self.total_velocity *= self.speed_cap / spd

    def fix_force(self):
        try:
            fx, fy = self.total_force
            if not (abs(fx) < 1e15 and abs(fy) < 1e15):
                self.total_force = Vector(0, 0)
                return
            fl = self.total_force.length()
            if fl > self.force_cap:
                self.total_force *= self.force_cap / fl
        except (OverflowError, ValueError):
            self.total_force = Vector(0, 0)

    def fix_radius(self, new_radius):
        self.pos = (self.pos[0] - new_radius + self.radius, self.pos[1] - new_radius + self.radius)
        self.radius = new_radius
        self.size = (self.radius * 2, self.radius * 2)
        # clear and redraw everything when the size actually changes
        self.canvas.clear()
        self._draw_sphere()

    def move(self, delta):
        self.fix_force()
        self.pos = self.total_velocity * delta + 0.5 * self.total_force * (delta ** 2) + self.pos
        self._update_shape_positions()
        self.bounce_off_walls()
        self.total_velocity += self.total_force * delta
        self.fix_speed()
        self.update_color_based_on_speed()
        self.update_force_arrow()

    def move_nonVerlet(self, delta):
        self.fix_force()
        self.total_velocity += self.total_force * delta   # Euler: v += a*dt
        self.fix_speed()
        self.pos = self.total_velocity * delta + self.pos  # Euler: x += v*dt (less stable than Verlet)
        self._update_shape_positions()
        self.bounce_off_walls()
        self.update_color_based_on_speed()
        self.update_force_arrow()

    def move_verlet_a(self, delta):
        """Velocity Verlet step 1: half-kick velocity with OLD forces, then advance position."""
        self.fix_force()
        self.total_velocity += 0.5 * self.total_force * delta   # first half-kick
        self.fix_speed()
        self.pos = (self.pos[0] + self.total_velocity.x * delta,
                    self.pos[1] + self.total_velocity.y * delta)
        self._update_shape_positions()
        self.bounce_off_walls()

    def move_verlet_b(self, delta):
        """Velocity Verlet step 2: second half-kick with NEW forces computed since step A."""
        self.fix_force()
        self.total_velocity += 0.5 * self.total_force * delta   # second half-kick
        self.fix_speed()
        self.update_color_based_on_speed()
        self.update_force_arrow()

    def bounce_off_walls(self):
        cx, cy = self.pos[0], self.pos[1]
        r = self.radius
        left   = self.parentpos[0]
        right  = self.parentpos[0] + self.parentsize[0]
        bottom = self.parentpos[1]
        top    = self.parentpos[1] + self.parentsize[1]
        if cx - r <= left or cx + r >= right:
            self.total_velocity = Vector(-self.total_velocity.x, self.total_velocity.y) # bounce x velocity
        if cy - r <= bottom or cy + r >= top:
            self.total_velocity = Vector(self.total_velocity.x, -self.total_velocity.y) # bounce y velocity
        self.keep_within_bounds()

    def rescale_position(self, new_pos, new_size):
        # move molecule to follow the window
        proportion_x = (self.pos[0] - self.parentpos[0]) / self.parentsize[0]
        proportion_y = (self.pos[1] - self.parentpos[1]) / self.parentsize[1]
        self.pos = (new_size[0] * proportion_x + new_pos[0], new_size[1] * proportion_y + new_pos[1])
        self.total_velocity = Vector(
            self.total_velocity.x * new_size[0] / self.parentsize[0],
            self.total_velocity.y * new_size[1] / self.parentsize[1]
        )
        self.fix_speed()
        self.update_color_based_on_speed()
        self._update_shape_positions()
        self.parentpos = new_pos
        self.parentsize = new_size
        self.keep_within_bounds()

    def keep_within_bounds(self):
        cx, cy = self.pos[0], self.pos[1]
        r = self.radius
        left   = self.parentpos[0]
        right  = self.parentpos[0] + self.parentsize[0]
        bottom = self.parentpos[1]
        top    = self.parentpos[1] + self.parentsize[1]
        new_cx = max(left + r, min(cx, right - r))
        new_cy = max(bottom + r, min(cy, top - r))
        if new_cx != cx or new_cy != cy:
            self.pos = (new_cx, new_cy)
        self._update_shape_positions()

    def collide_widget(self, other):
        distance = Vector(self.center).distance(other.center)
        return distance <= (self.width / 2 + other.width / 2)

    def push_apart(self, other):
        """Snap overlapping molecules to LJ equilibrium and kill relative normal velocity.
        At eq_dist: V = -epsilon, KE_normal = 0 -> total energy = -epsilon -> guaranteed bound state."""
        sigma    = self.width / 2 + other.width / 2          # touching = sigma_px
        eq_dist  = sigma * (2.0 ** (1.0 / 6.0))              # LJ minimum ~ 1.122 * sigma

        p1 = Vector(self.center)
        p2 = Vector(other.center)
        diff = p1 - p2
        dist = diff.length()

        if dist < sigma and dist > 1e-6:
            normal = diff.normalize()
            correction = (eq_dist - dist) / 2.0
            self.center  = (p1 + normal * correction)[:]
            other.center = (p2 - normal * correction)[:]

            m1 = self.width / 2
            m2 = other.width / 2
            v1n = normal.dot(self.total_velocity)
            v2n = normal.dot(other.total_velocity)
            v_cm_n  = (m1 * v1n + m2 * v2n) / (m1 + m2)     # shared normal velocity (CM frame)
            tangent = Vector(-normal[1], normal[0])
            self.total_velocity  = v_cm_n * normal + tangent.dot(self.total_velocity)  * tangent
            other.total_velocity = v_cm_n * normal + tangent.dot(other.total_velocity) * tangent
            self.fix_speed()
            other.fix_speed()

    def resolve_collision(self, other):
        # 2D elastic collision along the contact normal
        v1 = self.total_velocity
        v2 = other.total_velocity
        p1 = Vector(self.center)
        p2 = Vector(other.center)
        m1 = self.width / 2
        m2 = other.width / 2

        diff = p1 - p2
        dist = diff.length()
        min_dist = m1 + m2
        # positional correction - push molecules apart so they never stay overlapping
        if dist < min_dist and dist > 1e-6:
            overlap = (min_dist - dist) * 0.51
            push = diff.normalize() * overlap
            self.center  = (p1 + push)[:]
            other.center = (p2 - push)[:]

        normal  = diff.normalize() if dist > 1e-6 else Vector(1, 0)
        tangent = Vector(-normal[1], normal[0])
        v1n = normal.dot(v1);  v1t = tangent.dot(v1)
        v2n = normal.dot(v2);  v2t = tangent.dot(v2)
        v1n_new = (v1n * (m1 - m2) + 2 * m2 * v2n) / (m1 + m2)
        v2n_new = (v2n * (m2 - m1) + 2 * m1 * v1n) / (m1 + m2)
        self.total_velocity  = v1n_new * normal + v1t * tangent
        other.total_velocity = v2n_new * normal + v2t * tangent
        self.fix_speed()
        other.fix_speed()

    def update_color_based_on_speed(self):
        # Slow molecules are dark blue; fast ones shift toward bright pink/magenta
        t = min(self.total_velocity.length(), self.speed_cap) / self.speed_cap
        r = (self.color_slow[0] + (self.color_fast[0] - self.color_slow[0]) * t) / 255
        g = (self.color_slow[1] + (self.color_fast[1] - self.color_slow[1]) * t) / 255
        b = (self.color_slow[2] + (self.color_fast[2] - self.color_slow[2]) * t) / 255
        self.color_instruction.rgb = [r, g, b]
        self.glow_color.rgba       = [r, g, b, 0.18]
        self.base_color.rgb        = [r * 0.15, g * 0.15, b * 0.15]

    def reset_total_force(self):
        self.total_force = Vector(0, 0)

    def add_force(self, force_to_add):
        self.total_force += force_to_add

    def update_force_arrow(self):
        if not self.forces_visible or self.total_velocity.length() < 1e-9:
            self.arrow_line.points = []
            self.arrow_color.a = 0
            return
        t = min(self.total_velocity.length(), self.speed_cap) / self.speed_cap
        arrow_len = self.radius * 0.6 + self.radius * 2.5 * t
        vel_dir = self.total_velocity.normalize()
        cx, cy = self.pos[0], self.pos[1]
        sx = cx + vel_dir[0] * self.radius
        sy = cy + vel_dir[1] * self.radius
        ex = cx + vel_dir[0] * (self.radius + arrow_len)
        ey = cy + vel_dir[1] * (self.radius + arrow_len)
        self.arrow_line.points = [sx, sy, ex, ey]
        self.arrow_color.rgb = [t, 0.8 * (1 - t) + 0.3 * t, 1.0 * (1 - t)]
        self.arrow_color.a = 0.9
