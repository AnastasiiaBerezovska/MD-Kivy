from kivy.uix.widget import Widget
from kivy.uix.label import Label
from mdkivy.inputs.dual_makey import DualMakeyInput
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, Line, Quad, Ellipse
from kivy.graphics.instructions import InstructionGroup
from kivy.properties import NumericProperty, BooleanProperty
from kivy.vector import Vector
from mdkivy.simulation.molecule import Molecule
from mdkivy.simulation.beaker import Beaker, SIDE, TOP
from kivy.core.window import Window
from kivy.metrics import dp
from random import uniform
from collections import deque
import math
from mdkivy.widgets.performance_monitor import set_global_monitor
from mdkivy.inputs.arduino_reading import ArduinoReading
import time
import random
import gc
from kivy.animation import Animation
import numpy as np


class GameLayout(Widget):

    intermolecular_forces = BooleanProperty(False)
    epsilon = NumericProperty(50.0)
    sigma = NumericProperty(1.0)
    spring_constant = 100.0
    spring_rest_length = 2.0
    molecule_radius_ratio = 0.03
    use_verlet = False
    

    def __init__(self, performance_monitor, arduino_graph = None, **kwargs):
        super(GameLayout, self).__init__(**kwargs)
        try:
            self.arduino = ArduinoReading()
            print(f"[INFO] Arduino serial opened on {self.arduino.port} @ {self.arduino.baud_rate}")
        except Exception as e:
            print(f"[WARNING] Arduino not connected or no permission: {e}")
            print("         Hint: set ARDUINO_PORT=/dev/ttyACM0 and ensure you are in the 'dialout' group, then re-run.")
            self.arduino = None


        with self.canvas.before:
            Color(0.01, 0.01, 0.04, 1)
            self.rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self.update_rect, size=self.update_rect)

        self._beaker_group = InstructionGroup()
        self.canvas.before.add(self._beaker_group)
        self.beaker = Beaker(self)

        self._lj_viz_group = InstructionGroup()
        self.canvas.add(self._lj_viz_group)

        self.frame_counter = 0
        self.performance_monitor = performance_monitor

        self.arduino_graph = arduino_graph

        self.molecules = []
        Clock.schedule_interval(self.monitor_performance, 1)
        set_global_monitor(self.performance_monitor)
        
        Clock.schedule_interval(self.periodic_cleanup, 60)

        self.ui_update_every = 5
        self.arrow_update_every = 5
        self._arduino_log_accum = 0.0
        self._sec_accum = 0.0
        self.arduino_activity = 0.0
        
        self._prev_accel = None
        self._shake_intensity = 0.0

        self._governor_state = 'normal'
        self._governor_high_time = 0.0
        self._governor_low_time = 0.0
        self._governor_multiplier = 1.0
        self._forces_hidden_by_governor = False

        self._speed_factor = 1.0
        self._base_interval = 1 / 30.0
        self._current_interval = self._base_interval

        self._last_molecule_radius = 0.0

        self._keyboard = None
        self._keyboard_initialized = False
        self._key_last_press = {}
        self._key_cooldown = 0.08

        Clock.schedule_interval(lambda _dt: gc.collect(), 30)

        Clock.schedule_interval(self._governor_update, 0.5)

        self.mission_manager = None

        # one tap can arrive twice on the exhibit screen
        self._last_spawn_t = 0.0

        self._energy_history = deque(maxlen=120)

        self.thermostat_active = False
        self.thermostat_target_speed = 30.0

        self.bonds = {}
        self.old_pos = self.pos[:]
        self.old_size = self.size[:]
        self.pos_in_between = self.pos[:]
        self.size_in_between = self.size[:]
        self.gravity = 0
        self.makey_left_count  = 0
        self.makey_right_count = 0
        self.delta = 1 / 60.0
        self.simulation_running = False
        self.update_event = None
        self.energy_bar = None
        self.size_factor = 0.6
        self.molecule_radius = self.size[0] * self.molecule_radius_ratio * self.size_factor
        self.scale = 2 * self.molecule_radius
        self.forces_visible = False
        self.bonds_visible = False

        self.enable_lj_cutoff = True
        self.lj_cutoff_sigma = 2.5

        self._feedback_label = Label(
            text='', markup=True,
            size_hint=(None, None), size=(dp(260), dp(48)),
            pos_hint={'center_x': 0.5, 'center_y': 0.5},
            font_size='18sp', bold=True,
            halign='center', valign='middle',
            color=(0, 1, 1, 0),
        )
        self.add_widget(self._feedback_label)

        self._makey_left_last  = 0.0
        self._makey_right_last = 0.0
        self._dual_makey = DualMakeyInput(
            left_cb=self._makey_left_press,
            right_cb=self._makey_right_press,
        )

    def _makey_left_press(self):
        """Called by DualMakeyInput when the LEFT Makey Makey fires any key."""
        if self.width < 100 or self.height < 100:
            return
        if not self.simulation_running:
            return
        now = time.monotonic()
        if now - self._makey_left_last < 0.25:
            return
        self._makey_left_last = now
        cx = self.pos[0] + self.size[0] * uniform(0.15, 0.45)
        cy = self.pos[1] + self.size[1] * uniform(0.2, 0.8)
        self.spawn_molecule_at_touch(type('_T', (), {'pos': (cx, cy)})())
        self.makey_left_count += 1
        self.show_key_feedback(f'[color=00cfff]LEFT[/color]  #{self.makey_left_count}')

    def _makey_right_press(self):
        """Called by DualMakeyInput when the RIGHT Makey Makey fires any key."""
        if self.width < 100 or self.height < 100:
            return
        if not self.simulation_running:
            return
        now = time.monotonic()
        if now - self._makey_right_last < 0.25:
            return
        self._makey_right_last = now
        cx = self.pos[0] + self.size[0] * uniform(0.55, 0.85)
        cy = self.pos[1] + self.size[1] * uniform(0.2, 0.8)
        self.spawn_molecule_at_touch(type('_T', (), {'pos': (cx, cy)})())
        self.makey_right_count += 1
        self.show_key_feedback(f'[color=ff9900]RIGHT[/color]  #{self.makey_right_count}')

    def monitor_performance(self, _dt):
        atom_count = len(self.molecules)

        if not self.simulation_running:
            try:
                self.performance_monitor.update_simulation_metrics(
                    molecule_count=atom_count,
                    gravity=self.gravity,
                    epsilon=self.epsilon,
                    speed=self.speed_slider.value if getattr(self, 'speed_slider', None) else 1.0,
                    forces_on=self.intermolecular_forces,
                    arduino_activity=0.0,
                    total_energy=0.0,
                )
            except Exception:
                pass

        self.key_mapping = {
            'gravity_increase': 'w',
            'gravity_decrease': 's',
            'epsilon_increase': 'e',
            'epsilon_decrease': 'd',
            'sigma_increase': 'r',
            'sigma_decrease': 'f',
            'delta_increase': 't',
            'delta_decrease': 'g',
            'speed_increase': 'y',
            'speed_decrease': 'h',
            'size_increase' : 'u',
            'size_decrease' : 'j'
        }

        if not self._keyboard_initialized:
            self.setup_keyboard()
            self._keyboard_initialized = True

    def setup_keyboard(self):
        """set up keyboard bindings for slider controls"""
        if self._keyboard:
            try:
                self._keyboard.unbind(on_key_down=self.on_key_down)
            except Exception:
                pass
        self._keyboard = Window.request_keyboard(self._keyboard_closed, self)
        self._keyboard.bind(on_key_down=self.on_key_down)

    def _keyboard_closed(self):
        """keyboard was released - unbind and immediately re-request so Makey Makey keeps working"""
        try:
            self._keyboard.unbind(on_key_down=self.on_key_down)
        except Exception:
            pass
        self._keyboard = None
        self._keyboard_initialized = False
        Clock.schedule_once(lambda _dt: self.setup_keyboard(), 0.05)

    def on_key_down(self, _keyboard, keycode, _text, _modifiers):
        """Handle key press events for controlling sliders.

        Makey Makey board key layout:
          Arrow keys (base board / Makey Mouse) : up/down = gravity, left/right = epsilon
          Player 2 D-pad                        : a=gravity+, s=gravity-, w=gravity+, d=epsilon-
          Player 2 / Makey Max buttons          : f=sigma-, g=delta-
          Makey Max full keyboard section       : w/a=gravity+, s=gravity-, d/epsilon-,
                                                  f=sigma-, g=delta-
          Space (any board)                     : spawn molecule
        """
        key = keycode[1]

        now = time.monotonic()
        if now - self._key_last_press.get(key, 0) < self._key_cooldown:
            return True
        self._key_last_press[key] = now

        if key == self.key_mapping['gravity_increase']:
            self.adjust_gravity(1.0)
        elif key == self.key_mapping['gravity_decrease']:
            self.adjust_gravity(-1.0)
        elif key == self.key_mapping['epsilon_increase']:
            self.adjust_epsilon(0.5)
        elif key == self.key_mapping['epsilon_decrease']:
            self.adjust_epsilon(-0.5)
        elif key == self.key_mapping['sigma_increase']:
            self.adjust_sigma(0.2)
        elif key == self.key_mapping['sigma_decrease']:
            self.adjust_sigma(-0.2)
        elif key == self.key_mapping['delta_increase']:
            self.adjust_delta(1 / 60.0)
        elif key == self.key_mapping['delta_decrease']:
            self.adjust_delta(-1 / 60.0)
        elif key == self.key_mapping['speed_increase']:
            self.adjust_speed(0.1)
        elif key == self.key_mapping['speed_decrease']:
            self.adjust_speed(-0.1)
        elif key == self.key_mapping['size_increase']:
            self.adjust_size(0.05)
        elif key == self.key_mapping['size_decrease']:
            self.adjust_size(-0.05)
        elif key == 'a':
            self.adjust_gravity(1.0)
        elif key == 'up':
            self.adjust_gravity(1.0)
        elif key == 'down':
            self.adjust_gravity(-1.0)
        elif key == 'right':
            self.adjust_epsilon(0.5)
        elif key == 'left':
            self.adjust_epsilon(-0.5)
        return True

    def show_key_feedback(self, text):
        """Flash a label in the centre of the game area for 0.7 s."""
        lbl = getattr(self, '_feedback_label', None)
        if lbl is None:
            return
        lbl.text = f'[b]{text}[/b]'
        lbl.color = (0, 1, 1, 1)
        Animation.cancel_all(lbl)
        Animation(color=(0, 1, 1, 0), duration=0.7).start(lbl)

    def adjust_gravity(self, change):
        """change gravity value and update the slider"""
        self.gravity = max(0, min(self.gravity + change, 10))
        if self.gravity_slider:
            self.gravity_slider.value = self.gravity

    def adjust_epsilon(self, change):
        """change epsilon value and update slider"""
        self.epsilon = max(0, min(self.epsilon + change, 10))
        if self.epsilon_slider:
            self.epsilon_slider.value = self.epsilon

    def adjust_sigma(self, change):
        """change sigma value and update slider"""
        self.sigma = max(0.1, min(self.sigma + change, 3))
        if self.sigma_slider:
            self.sigma_slider.value = self.sigma

    def adjust_delta(self, change):
        """change timestep value and update slider"""
        self.delta = max(1 / 600, min(self.delta + change, 1))
        if self.delta_slider:
            self.delta_slider.value = self.delta

    def adjust_speed(self, change):
        """change simulation speed and update slider"""
        new_speed = max(0.1, min(self.speed_slider.value + change, 1)) if self.speed_slider else 1.0

        if self.speed_slider:
            self.speed_slider.value = new_speed
        
        self.set_speed(new_speed)
        
    def adjust_size(self, change):
        """change size factor and update slider"""
        self.size_factor = max(0.2, min(self.size_factor + change, 1))
        if self.size_slider:
            self.size_slider.value = self.size_factor
            
        self.molecule_radius = self.size[0] * self.molecule_radius_ratio * self.size_factor
        self.scale = 2 * self.molecule_radius
        for molecule in self.molecules:
            molecule.fix_radius(self.molecule_radius)

    def create_bond(self, molecule1, molecule2):
        """create a bond line between two molecules"""
        if (molecule1, molecule2) in self.bonds or (molecule2, molecule1) in self.bonds:
            return
        dist = Vector(molecule1.pos).distance(Vector(molecule2.pos))
        if dist > (molecule1.radius + molecule2.radius) * 6:
            return
        with self.canvas:
            color = Color(0.4, 0.85, 1.0, 0.65)
            line = Line(points=[molecule1.pos[0], molecule1.pos[1],
                                 molecule2.pos[0], molecule2.pos[1]], width=2)
        self.bonds[(molecule1, molecule2)] = (line, color)

    def remove_bond(self, molecule1, molecule2):
        """delete a bond between two molecules"""
        if (molecule1, molecule2) in self.bonds:
            bond = (molecule1, molecule2)
        elif (molecule2, molecule1) in self.bonds:
            bond = (molecule2, molecule1)
        else:
            return False
        line, color = self.bonds[bond]
        self.canvas.remove(line)
        self.canvas.remove(color)
        del self.bonds[bond]
        return True

    def clear_bonds(self):
        """remove all bonds from the canvas"""
        for bond, (line, color) in self.bonds.items():
            self.canvas.remove(line)
            self.canvas.remove(color)
        self.bonds.clear()
    
    def periodic_cleanup(self, dt):
        """Run periodic garbage collection."""
        try:
            gc.collect()
            
            if len(self.molecules) == 0:
                # canvas.before keeps the background
                self.canvas.clear()
                self.canvas.add(self._lj_viz_group)
            
            print(f"[DEBUG] cleanup: {len(self.molecules)} molecules, {len(self.bonds)} bonds")
        except Exception as e:
            print(f"[WARNING] cleanup failed: {e}")

    def update_bond_lines(self):
        """update where all the bond lines are drawn"""
        for (mol1, mol2), (line, _) in self.bonds.items():
            line.points = [mol1.pos[0], mol1.pos[1], mol2.pos[0], mol2.pos[1]]
                
    def apply_spring_force(self):
        """apply spring forces to bonded molecules"""
        for (molecule1, molecule2) in self.bonds:
            r12 = Vector(molecule2.center_x - molecule1.center_x, molecule2.center_y - molecule1.center_y)
            distance = r12.length()
            
            if distance > 0:
                k_spring = 0.5
                r_eq = 100
                force_magnitude = k_spring * (distance - r_eq)
                force_vector = (force_magnitude / distance) * r12
                molecule1.add_force(-force_vector)
                molecule2.add_force(force_vector)

    def update_rect(self, _instance, _value):
        self.old_pos = self.pos_in_between[:]
        self.old_size = self.size_in_between[:]


        self.pos_in_between = self.pos[:]
        self.size_in_between = self.size[:]

        self.rect.pos = self.pos
        self.rect.size = self.size
        
        self.canvas.ask_update()
        
        self.molecule_radius = self.size[0] * self.molecule_radius_ratio * self.size_factor
        self.scale = 2 * self.molecule_radius
        self.draw_beaker()
        self.on_resize()

    def on_touch_down(self, touch):
        """Spawn one molecule at the tapped point.

        The device='mouse' event carries the calibrated cursor position; the
        raw touch device is mis-mapped, so only mouse events spawn.
        """
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)

        if getattr(touch, 'device', '') != 'mouse':
            return super().on_touch_down(touch)
        if getattr(touch, 'button', 'left') != 'left' or getattr(touch, 'multitouch_sim', False):
            return super().on_touch_down(touch)
        now = time.monotonic()
        if now - self._last_spawn_t < 0.12:
            return True
        self._last_spawn_t = now

        if self.is_safe_touch(touch):
            self.spawn_molecule_at_touch(touch)
            return True
        return super().on_touch_down(touch)

    def is_safe_touch(self, touch):
        """
        Check if the touch is within safe bounds to prevent the molecule from extending past the edges.
        """
        # pos is the molecule center in this app
        safe_margin_x = self.molecule_radius
        safe_margin_y = self.molecule_radius

        return (
            self.pos[0] + safe_margin_x <= touch.x <= self.right - safe_margin_x and
            self.pos[1] + safe_margin_y <= touch.y <= self.top - safe_margin_y
        )

    def spawn_molecule_at_touch(self, touch):
        """Spawn a molecule centred on the touch, with a random velocity."""
        angle = uniform(-math.pi, math.pi)
        vx = 300 * math.cos(angle)
        vy = 300 * math.sin(angle)
        self.create_molecule(touch.pos[0] + 50, touch.pos[1] + 50, vx, vy)
        self.molecules[-1].update_color_based_on_speed()
        
    def start_simulation(self):
        """start the update loop"""
        if not self.simulation_running:
            self.simulation_running = True
            if self.update_event is not None:
                try:
                    self.update_event.cancel()
                except Exception:
                    pass
            self._base_interval = (1 / 30.0) / self._speed_factor
            self._current_interval = self._base_interval * self._governor_multiplier
            self.update_event = Clock.schedule_interval(self.update, self._current_interval)

    def stop_simulation(self):
        """stop the update loop"""
        if self.simulation_running:
            self.simulation_running = False
            if self.update_event is not None:
                self.update_event.cancel()
                self.update_event = None
            
            gc.collect()

    def reset_simulation(self):
        """Stop and clear molecules only (used internally)."""
        self.thermostat_active = False
        self.stop_simulation()
        self.clear_molecules()
        self._lj_viz_group.clear()
        self.intermolecular_forces = False
        self.bonds_visible = False
        self.forces_visible = False

    def reset_all_params(self):
        """Reset molecules and parameters."""
        self.reset_simulation()
        self.epsilon    = 50.0
        self.sigma      = 1.0
        self.delta      = 1 / 60.0
        self.gravity    = 0.0
        self.use_verlet = False
        self._speed_factor  = 1.0
        self._base_interval = 1 / 30.0
        self.size_factor      = 0.6
        self.molecule_radius  = self.size[0] * self.molecule_radius_ratio * self.size_factor
        self.scale = 2 * self.molecule_radius
        defaults = {
            'epsilon_slider': 50.0,
            'sigma_slider':   1.0,
            'delta_slider':   1 / 60.0,
            'gravity_slider': 0.0,
            'speed_slider':   1.0,
            'size_slider':    0.6,
        }
        for slider_attr, val in defaults.items():
            sl = getattr(self, slider_attr, None)
            if sl is not None:
                sl.value = val

    def inject_energy(self, amount):
        """Boost all molecule velocities randomly ==> called by slider or also EnergyInputWidget name if applicable."""
        boost = amount * 360
        for mol in self.molecules:
            angle = random.uniform(0, 2 * math.pi)
            mol.total_velocity += Vector(boost * math.cos(angle), boost * math.sin(angle))
            mol.fix_speed()
        if self.energy_bar is not None and self.molecules:
            total_spd = sum(mol.total_velocity.length() for mol in self.molecules)
            self.energy_bar.feed(total_spd / len(self.molecules))


    def set_speed(self, speed_factor):
        """change simulation speed"""
        self._speed_factor = max(0.1, float(speed_factor))
        self._base_interval = (1 / 30.0) / self._speed_factor
        self._apply_update_interval()

    def _apply_update_interval(self):
        """apply the interval based on governor settings"""
        if not self.simulation_running:
            return
        effective = self._base_interval * self._governor_multiplier
        if self.update_event is not None:
            try:
                self.update_event.cancel()
            except Exception:
                pass
        self._current_interval = effective
        self.update_event = Clock.schedule_interval(self.update, effective)
        
    def set_size(self, size_factor):
        """Adjust the simulation speed by setting a new interval."""
        self.size_factor = size_factor
        self.molecule_radius = self.size[0] * self.molecule_radius_ratio * self.size_factor
        self.scale = 2 * self.molecule_radius
        for molecule in self.molecules:
            molecule.fix_radius(self.molecule_radius)

    def toggle_update_mode(self):
        self.use_verlet = not self.use_verlet


    def update(self, dt):
        """
        Update molecule positions, handle collisions, and update bonds.
        Arduino integration affects: gravity, kinetic energy, temperature, and pressure.
        """
        total_energy = 0
        temperature = 0
        pressure = 0

        arduino_data = self.arduino.get_xyz() if self.arduino else None
        if arduino_data:
            x, y, z = arduino_data
            accel_magnitude = (x**2 + y**2 + z**2) ** 0.5
            # 16384 is 1g on the MPU6050
            scale_factor = max(accel_magnitude / 16384.0, 0.1)

            if self._prev_accel is not None:
                prev_x, prev_y, prev_z = self._prev_accel
                delta_x = abs(x - prev_x)
                delta_y = abs(y - prev_y)
                delta_z = abs(z - prev_z)
                
                shake_delta = (delta_x**2 + delta_y**2 + delta_z**2) ** 0.5
                
                if shake_delta < 20:
                    shake_raw = 0
                elif shake_delta < 100:
                    shake_raw = (shake_delta - 20) / 4.0
                elif shake_delta < 500:
                    shake_raw = 20 + (shake_delta - 100) * 0.075
                else:
                    shake_raw = 50 + min((shake_delta - 500) * 0.05, 50)
                
                shake_raw = min(shake_raw, 100)
                
                self.arduino_activity = 0.5 * self.arduino_activity + 0.5 * shake_raw
            else:
                self.arduino_activity = 0

            self._prev_accel = (x, y, z)

            self.gravity = 9.8 * scale_factor
            

            if self.arduino_graph:
                self.arduino_graph.feed_arduino(x, y, z, self.arduino_activity)

            self._arduino_log_accum += dt
            if self._arduino_log_accum >= 1.0:
                print(f"Arduino → X:{x:.2f}, Y:{y:.2f}, Z:{z:.2f}, Scale:{scale_factor:.2f}")
                self._arduino_log_accum = 0.0
        else:
            scale_factor = 1.0

        # old forces first
        if self.use_verlet:
            for mol in self.molecules:
                mol.speed_cap = 500
                mol.move_verlet_a(self.delta)

        beaker_g = self.beaker.view_gravity()
        for molecule in self.molecules:
            molecule.reset_total_force()
            g = self.gravity
            if beaker_g and self.beaker.contains(*molecule.pos):
                g += beaker_g
            molecule.add_force(Vector(0, -g))

        new_radius = self.size[0] * self.molecule_radius_ratio * self.size_factor
        if abs(new_radius - self._last_molecule_radius) > 0.1:
            self.molecule_radius = new_radius
            self.scale = 2 * new_radius
            self._last_molecule_radius = new_radius
            for mol in self.molecules:
                mol.fix_radius(self.molecule_radius)
        self.apply_spring_force()

        self.frame_counter += 1
        if self.frame_counter % 5 == 0:
            self.update_bond_lines()
        if self.frame_counter % 8 == 0:
            if self.bonds_visible:
                self._update_lj_viz()
        if self.frame_counter % 10 == 0:
            visible = random.sample(self.molecules, min(len(self.molecules), 10))
            for molecule in visible:
                molecule.update_color_based_on_speed()
                if self.forces_visible:
                    molecule.update_force_arrow()
            self.update_bond_lines()

        coll_cell = max(self.molecule_radius * 3, 40)
        for mol1, mol2 in self._spatial_pairs(coll_cell):
            dx    = mol2.center_x - mol1.center_x
            dy    = mol2.center_y - mol1.center_y
            sum_r = (mol1.width + mol2.width) * 0.5
            if abs(dx) <= sum_r and abs(dy) <= sum_r and mol1.collide_widget(mol2):
                if self.intermolecular_forces:
                    # LJ already handles the pushback
                    mol1.push_apart(mol2)
                else:
                    mol1.resolve_collision(mol2)
                mol1.update_color_based_on_speed()
                mol2.update_color_based_on_speed()

        if self.intermolecular_forces and len(self.molecules) >= 2:
            self._apply_lj_forces_numpy()

        do_arrows = self.forces_visible and (self.frame_counter % self.arrow_update_every == 0)
        for mol in self.molecules:
            if do_arrows:
                mol.update_force_arrow()
            if not self.use_verlet:
                mol.speed_cap = 2000
                mol.move_nonVerlet(self.delta)

        # finish with the new forces
        if self.use_verlet:
            for mol in self.molecules:
                mol.move_verlet_b(self.delta)

        if self.beaker.active:
            for mol in self.molecules:
                self.beaker.collide(mol)

        damped = [m for m in self.molecules
                  if self.thermostat_active or m.thermo]
        if damped:
            avg_spd = sum(m.total_velocity.length() for m in damped) / len(damped)
            if avg_spd > self.thermostat_target_speed and avg_spd > 0:
                scale = 1.0 + (self.thermostat_target_speed / avg_spd - 1.0) * 0.10
                for m in damped:
                    m.total_velocity = m.total_velocity * scale

        for molecule1 in self.molecules:
            try:
                velocity_magnitude = molecule1.total_velocity.length()
            except (OverflowError, ValueError):
                molecule1.total_velocity = Vector(0, 0)
                velocity_magnitude = 0.0
            normalized_velocity = velocity_magnitude / 50.0
            kinetic_energy = 0.5 * (normalized_velocity ** 2)
            total_energy += kinetic_energy * scale_factor
            temperature += kinetic_energy * scale_factor
            momentum = (abs(molecule1.total_velocity.x) + abs(molecule1.total_velocity.y)) / 50.0 
            pressure += momentum * scale_factor

        num_molecules = len(self.molecules) if len(self.molecules) > 0 else 1
        avg_temperature = temperature / num_molecules

        if self.energy_bar is not None and self.molecules and self.use_verlet:
            total_spd = 0.0
            for mol in self.molecules:
                try:
                    total_spd += mol.total_velocity.length()
                except (OverflowError, ValueError):
                    pass
            self.energy_bar.feed(total_spd / len(self.molecules))

        if self.frame_counter % self.ui_update_every == 0:
            self.total_energy_label.text = f"{total_energy:.2f}"

            self.temperature_label.text = f"{avg_temperature:.2f}"

            self.pressure_label.text = f"{pressure:.2f}"

        self.performance_monitor.update_simulation_metrics(
            molecule_count=len(self.molecules),
            gravity=self.gravity,
            epsilon=self.epsilon,
            speed=self.speed_slider.value if self.speed_slider else 1.0,
            forces_on=self.intermolecular_forces,
            arduino_activity=self.arduino_activity,
            total_energy=total_energy
        )
        self._sec_accum += dt

        if self.mission_manager and self.mission_manager.state == 'active':
            self.mission_manager.tick(dt, avg_temperature, self.performance_monitor.get_cpu_usage(), len(self.molecules))

        if self.molecules:
            try:
                avg_spd = sum(m.total_velocity.length() for m in self.molecules) / len(self.molecules)
                self._energy_history.append(avg_spd)
            except Exception:
                pass

    def get_stability_warnings(self):
        """Return a list of active accuracy/stability warnings for the current state.

        Each entry: {'severity': 'low'|'medium'|'high', 'title': str, 'detail': str}
        Severity colours: low=yellow, medium=orange, high=red.
        """
        if not self.simulation_running:
            return []

        warnings = []
        n = len(self.molecules)

        if not self.use_verlet:
            warnings.append({
                'severity': 'medium',
                'title': 'Euler integration — energy not conserved',
                'detail': (
                    'Euler just adds the current force and keeps going each step. '
                    'Small errors pile up every frame, so total kinetic energy drifts '
                    'upward indefinitely — not physical. '
                    'Switch to Verlet (WHY? panel) for stable, energy-conserving integration.'
                ),
            })

        if self.delta > 0.025:
            sev = 'high' if self.delta > 0.06 else 'medium'
            warnings.append({
                'severity': sev,
                'title': f'Timestep too large  (Δt = {self.delta:.3f} s)',
                'detail': (
                    f'At Δt = {self.delta:.3f}, each molecule jumps too far in one step. '
                    'The LJ r^-12 repulsion spikes before a collision is detected, '
                    'so molecules can pass through each other or fly apart violently. '
                    'Keep Δt ≤ 0.017 (1/60 s) for reliable integration.'
                ),
            })

        if len(self._energy_history) >= 60:
            hist = list(self._energy_history)
            recent = sum(hist[-30:]) / 30
            older  = sum(hist[:30])  / 30
            if older > 1.0 and recent > older * 1.4:
                pct = int((recent / older - 1) * 100)
                warnings.append({
                    'severity': 'high',
                    'title': f'Energy diverging  (+{pct}% in ~2 s)',
                    'detail': (
                        f'Average molecule speed grew {pct}% in the last 2 seconds — '
                        'the simulation has gone numerically unstable. '
                        'Common causes: Δt too large, molecules deeply overlapping '
                        '(stuck in the r^-12 wall), or Euler drift compounding. '
                        'Reduce Δt, press STOP, or switch to Verlet to recover.'
                    ),
                })

        if self.gravity > 0.5 and self.intermolecular_forces:
            warnings.append({
                'severity': 'low',
                'title': 'Gravity + LJ forces  (not physical)',
                'detail': (
                    'At atomic scale, gravity is roughly 10¹⁸× weaker than '
                    'intermolecular forces — real atoms are completely unaffected by '
                    'gravity relative to their bonding. '
                    'This combination is visually interesting but not chemically realistic.'
                ),
            })

        if self.intermolecular_forces and n > 80:
            warnings.append({
                'severity': 'low',
                'title': f'High load  ({n} molecules × LJ forces)',
                'detail': (
                    f'LJ force computation is O(n²): {n} molecules = '
                    f'{n * (n - 1) // 2:,} pair checks per frame. '
                    'Under heavy load the app skips physics steps to stay responsive, '
                    'so the simulation runs slower than real-time and integration '
                    'accuracy drops.'
                ),
            })

        return warnings

    def on_resize(self):
        for molecule in self.molecules:
            molecule.rescale_position(self.pos[:], self.size[:])
            molecule.fix_radius(self.molecule_radius)

    def set_gravity(self, value):
        """Update gravity for all molecules based on slider value."""
        self.gravity = value

    def set_epsilon(self, value):
        """Update the epsilon parameter for Lennard-Jones potential."""
        self.epsilon = value

    def set_sigma(self, value):
        """Update the sigma parameter for Lennard-Jones potential."""
        self.sigma = value
        if self.intermolecular_forces:
            self._push_apart_lj()

    def _push_apart_lj(self):
        """Push molecule pairs so none sit inside the new LJ equilibrium radius.

        push_apart() on Molecule only fixes hard-sphere overlaps (dist < radius_sum).
        When LJ sigma increases, non-touching molecules can still be deep inside the
        repulsive zone - this method uses the actual LJ sigma in pixels.
        """
        # keep pairs out of the hard repulsion zone
        from kivy.vector import Vector as _V
        eq_px = (2.0 ** (1.0 / 6.0)) * self.sigma * self.scale
        mols  = self.molecules
        for i in range(len(mols)):
            m1 = mols[i]
            for j in range(i + 1, len(mols)):
                m2  = mols[j]
                p1  = _V(m1.center)
                p2  = _V(m2.center)
                d   = p1.distance(p2)
                if d < eq_px and d > 1.0:
                    n    = (p1 - p2).normalize()
                    corr = (eq_px - d) / 2.0
                    m1.center = (p1 + n * corr)[:]
                    m2.center = (p2 - n * corr)[:]
                    v1n = n.dot(m1.total_velocity)
                    v2n = n.dot(m2.total_velocity)
                    if v1n - v2n < 0:
                        t   = _V(-n[1], n[0])
                        avg = (v1n + v2n) / 2.0
                        m1.total_velocity = avg * n + t.dot(m1.total_velocity) * t
                        m2.total_velocity = avg * n + t.dot(m2.total_velocity) * t
                    m1.fix_speed()
                    m2.fix_speed()
        
    def set_delta(self, value):
        """Update the timestep for Verlet integration."""
        self.delta = max(1 / 60.0, float(value))

    def toggle_intermolecular_forces(self):
        """Toggle LJ force computation; lines follow forces when turning on/off."""
        self.intermolecular_forces = not self.intermolecular_forces
        self.bonds_visible = self.intermolecular_forces
        if not self.bonds_visible:
            self._lj_viz_group.clear()
        else:
            mols = self.molecules
            for i in range(len(mols)):
                for j in range(i + 1, len(mols)):
                    mols[i].push_apart(mols[j])

    def toggle_lj_lines(self):
        """Hide/show LJ viz lines without touching the physics calculation."""
        self.bonds_visible = not self.bonds_visible
        if not self.bonds_visible:
            self._lj_viz_group.clear()

    def toggle_force_arrows(self):
        """Toggle directional force arrows on each molecule."""
        self.forces_visible = not self.forces_visible
        for molecule in self.molecules:
            molecule.forces_visible = self.forces_visible
            molecule.update_force_arrow()

    def _update_lj_viz(self):
        """Draw LJ potential interaction lines between molecule pairs.

        Reduced distance r* = r / (sigma * scale).
        Force is repulsive  for r* < 2^(1/6) ~ 1.122  -> red/orange line.
        Force is attractive for r* > 2^(1/6)           -> cyan/blue line, fades at cutoff.
        Line disappears near the equilibrium where force ~ 0.
        """
        self._lj_viz_group.clear()
        if not self.bonds_visible or len(self.molecules) < 2:
            return

        sigma_px  = max(self.sigma * self.scale, 1.0)
        cutoff_px = self.lj_cutoff_sigma * sigma_px
        equil     = 2.0 ** (1.0 / 6.0)

        for i in range(len(self.molecules)):
            mol1 = self.molecules[i]
            for j in range(i + 1, len(self.molecules)):
                mol2 = self.molecules[j]
                dx = mol2.pos[0] - mol1.pos[0]
                dy = mol2.pos[1] - mol1.pos[1]
                r  = (dx * dx + dy * dy) ** 0.5
                if r < 1.0 or r > cutoff_px:
                    continue

                r_star = r / sigma_px
                r_star = max(r_star, 0.6)

                f_star = 4.0 * (12.0 / r_star ** 13 - 6.0 / r_star ** 7)
                f_abs  = abs(f_star)
                strength = min(math.log1p(f_abs) / 6.0, 1.0)

                if r_star < equil:
                    self._lj_viz_group.add(Color(1.0, 0.6 - 0.5 * strength, 0.0, 0.35 + 0.55 * strength))
                    lw = 1.0 + 3.0 * strength
                else:
                    fade = 1.0 - (r_star - equil) / (self.lj_cutoff_sigma - equil)
                    fade = max(fade, 0.0)
                    if fade < 0.05:
                        continue
                    self._lj_viz_group.add(Color(0.0, 0.7 + 0.3 * fade, 1.0, 0.15 + 0.55 * fade))
                    lw = 1.0 + 1.5 * fade

                self._lj_viz_group.add(Line(
                    points=[mol1.pos[0], mol1.pos[1], mol2.pos[0], mol2.pos[1]],
                    width=lw
                ))

    def toggle_forces_visible(self):
        """Toggle intermolecular forces on or off."""
        self.forces_visible = not self.forces_visible
        for molecule in self.molecules:
            molecule.forces_visible = self.forces_visible
            molecule.update_force_arrow()

    def _apply_lj_forces_numpy(self):
        """Compute all pairwise Lennard-Jones forces in one NumPy broadcast.

        Replaces the O(n²) Python loop - for 300 molecules this is ~30x faster
        because all distance and force maths run inside NumPy's C layer.
        """
        mols = self.molecules
        n    = len(mols)

        pos = np.empty((n, 2), dtype=np.float64)
        for i, m in enumerate(mols):
            pos[i, 0] = m.center_x
            pos[i, 1] = m.center_y

        diff = pos[np.newaxis, :, :] - pos[:, np.newaxis, :]
        r2   = diff[:, :, 0]**2 + diff[:, :, 1]**2

        eps_i = np.fromiter((self.epsilon if mm.eps is None else mm.eps
                             for mm in mols), dtype=np.float64, count=n)
        sig_i = np.fromiter((self.sigma if mm.sig is None else mm.sig
                             for mm in mols), dtype=np.float64, count=n)
        eps_ij = np.sqrt(np.outer(eps_i, eps_i))
        sig_ij = 0.5 * (sig_i[:, np.newaxis] + sig_i[np.newaxis, :])

        sigma_px   = sig_ij * self.scale
        cutoff_px2 = (self.lj_cutoff_sigma * sigma_px) ** 2
        mask = (r2 > 1e-6) & (r2 < cutoff_px2)

        r2_nat  = np.where(mask, r2 / (sigma_px ** 2), 1.0)
        rSqInv  = 1.0 / r2_nat
        attract = rSqInv * rSqInv * rSqInv
        repel   = attract * attract

        fOverR = np.where(mask,
                          24.0 * eps_ij * (2.0 * repel - attract) * rSqInv,
                          0.0)

        fvec = fOverR[:, :, np.newaxis] * (-diff)
        net  = fvec.sum(axis=1)

        for i, m in enumerate(mols):
            m.total_force.x += float(net[i, 0])
            m.total_force.y += float(net[i, 1])

    def _spatial_pairs(self, cell_size):
        """Yield each unique (mol1, mol2) pair using a cell-list spatial grid.

        Molecules are binned into cells of `cell_size`. Only cells that are
        adjacent (≤1 cell apart) are checked against each other, so distant
        pairs are never visited.  The half-space neighbour offsets ensure every
        pair is yielded exactly once without a seen-set.
        """
        inv  = 1.0 / cell_size
        grid = {}
        for mol in self.molecules:
            key = (int(mol.center_x * inv), int(mol.center_y * inv))
            try:
                grid[key].append(mol)
            except KeyError:
                grid[key] = [mol]

        for (gx, gy), mols in grid.items():
            n = len(mols)
            for k in range(n):
                for l in range(k + 1, n):
                    yield mols[k], mols[l]
            for dgx, dgy in ((1, -1), (1, 0), (1, 1), (0, 1)):
                nb = grid.get((gx + dgx, gy + dgy))
                if nb:
                    for m1 in mols:
                        for m2 in nb:
                            yield m1, m2

    def _governor_update(self, dt):
        """adjust update rate based on cpu usage"""
        try:
            cpu = self.performance_monitor.get_cpu_usage()
        except Exception:
            return
        threshold = 90.0
        if cpu >= threshold:
            self._governor_high_time += dt
            self._governor_low_time = 0.0
        else:
            self._governor_low_time += dt
            self._governor_high_time = 0.0

        n = len(self.molecules)
        if n > 200:
            throttle_mul = 3.0
        elif n > 120:
            throttle_mul = 2.0
        else:
            throttle_mul = 1.5

        # ignore one bad cpu sample
        if self._governor_state == 'normal' and self._governor_high_time >= 1.5:
            self._governor_state = 'throttle'
            self._governor_multiplier = throttle_mul
            if self.forces_visible:
                # arrows cost extra when it is busy
                self._forces_hidden_by_governor = True
                self.forces_visible = False
            self._apply_update_interval()

        if self._governor_state == 'throttle' and self._governor_multiplier != throttle_mul:
            self._governor_multiplier = throttle_mul
            self._apply_update_interval()

        if self._governor_state == 'throttle' and self._governor_low_time >= 4.0:
            self._governor_state = 'normal'
            self._governor_multiplier = 1.0
            if self._forces_hidden_by_governor:
                self.forces_visible = True
                self._forces_hidden_by_governor = False
            self._apply_update_interval()

    def _apply_physics_preset(self, gravity, epsilon, sigma):
        """Set gravity, epsilon and sigma and sync their sliders."""
        self.set_gravity(gravity)
        self.set_epsilon(epsilon)
        self.set_sigma(sigma)
        if self.gravity_slider:
            self.gravity_slider.value = gravity
        if self.epsilon_slider:
            self.epsilon_slider.value = epsilon
        if self.sigma_slider:
            self.sigma_slider.value = sigma

    def _preset_boost(self):
        try:
            if hasattr(self.performance_monitor, 'trigger_boost'):
                self.performance_monitor.trigger_boost(40.0)
        except Exception:
            print("[Slider boost error] trigger_boost unavailable")

    def generate_solid(self):
        """A compact block of molecules locked in a lattice, floating together.

        Not the whole play area: a solid is a lump you can see the edges of, so
        it reads as one object against the liquid and gas presets.
        """
        self._apply_physics_preset(gravity=0, epsilon=5.0, sigma=1.0)
        self.clear_molecules()

        r_eq    = (2 ** (1.0 / 6.0)) * self.sigma * self.scale
        spacing = max(r_eq, 2.0 * self.molecule_radius)
        dx = spacing
        # hex rows pack without overlaps
        dy = spacing * (3.0 ** 0.5) / 2.0

        cols = rows = 7
        block_w = (cols - 1) * dx + dx / 2.0
        block_h = (rows - 1) * dy
        offset  = 50
        x0 = self.pos[0] + (self.size[0] - block_w) / 2.0 + offset
        y0 = self.pos[1] + (self.size[1] - block_h) / 2.0 + offset

        for row in range(rows):
            y = y0 + row * dy
            xs = x0 + (dx / 2.0 if row % 2 else 0.0)
            for col in range(cols):
                self.create_molecule(xs + col * dx, y, 0, 0)

        self.thermostat_active = True
        self.thermostat_target_speed = 25.0

    def generate_liquid(self):
        """A cohesive blob - molecules slip past each other but stay together."""
        self.thermostat_active = False
        self._preset_boost()
        self._apply_physics_preset(gravity=0, epsilon=2.0, sigma=1.0)
        self.clear_molecules()

        offset = 50
        cx = self.pos[0] + self.size[0] / 2.0 + offset
        cy = self.pos[1] + self.size[1] / 2.0 + offset
        blob = min(self.size[0], self.size[1]) * 0.24

        for _ in range(48):
            ang = uniform(0, 2 * math.pi)
            d = blob * math.sqrt(uniform(0.0, 1.0))
            self.create_molecule(cx + d * math.cos(ang), cy + d * math.sin(ang),
                                 uniform(-60, 60), uniform(-60, 60))

    def generate_gas(self):
        """Create the gas preset."""
        self.thermostat_active = False
        self._preset_boost()
        self._apply_physics_preset(gravity=0, epsilon=0.3, sigma=1.5)
        self.clear_molecules()

        offset = 50
        pad = max(self.molecule_radius * 2, 40)
        for _ in range(20):
            x = uniform(self.pos[0] + pad, self.pos[0] + self.size[0] - pad) + offset
            y = uniform(self.pos[1] + pad, self.pos[1] + self.size[1] - pad) + offset
            self.create_molecule(x, y, uniform(-350, 350), uniform(-350, 350))

    def toggle_beaker(self):
        """Show or hide the flask."""
        self.beaker.active = not self.beaker.active
        self.draw_beaker()
        return self.beaker.active

    def set_beaker_orientation(self, orientation):
        """SIDE puts gravity on inside the glass and opens the mouth;
        TOP looks straight down, so the boundary closes into a circle."""
        self.beaker.orientation = orientation
        self.draw_beaker()

    def fill_beaker(self, phase):
        if not self.beaker.active:
            return
        self.beaker.fill(phase)

    def draw_beaker(self):
        """Draw the flask behind the molecules."""
        group = getattr(self, '_beaker_group', None)
        if group is None:
            return
        group.clear()
        if not self.beaker.active or self.width < 10:
            return

        b = self.beaker
        if b.orientation == TOP:
            cx, cy, r = b.top_circle
            group.add(Color(0.16, 0.26, 0.38, 0.35))
            group.add(Ellipse(pos=(cx - r, cy - r), size=(r * 2, r * 2)))
            group.add(Color(0.72, 0.86, 0.96, 0.85))
            group.add(Line(circle=(cx, cy, r), width=b.wall * 0.5))
            group.add(Color(0.90, 0.96, 1.0, 0.55))
            group.add(Line(circle=(cx, cy, r - b.wall * 0.5), width=1.2))
            return

        pts = b.outline
        (nlx, nly), (slx, sly), (flx, fly), (frx, fry), (srx, sry), (nrx, nry) = pts

        group.add(Color(0.16, 0.26, 0.38, 0.30))
        group.add(Quad(points=[flx, fly, frx, fry, srx, sry, slx, sly]))
        group.add(Rectangle(pos=(nlx, sly), size=(nrx - nlx, nly - sly)))

        group.add(Color(0.80, 0.90, 1.0, 0.40))
        for i in range(1, 4):
            f = i / 4.0
            gy = fly + (sly - fly) * f
            lo = flx + (slx - flx) * f
            hi = frx + (srx - frx) * f
            group.add(Line(points=[lo + (hi - lo) * 0.55, gy, hi - (hi - lo) * 0.12, gy],
                           width=1.1))

        group.add(Color(0.74, 0.87, 0.97, 0.95))
        flat = []
        for px, py in pts:
            flat.extend((px, py))
        group.add(Line(points=flat, width=b.wall * 0.45, joint='round', cap='round'))

        group.add(Color(0.92, 0.97, 1.0, 0.90))
        lip = (nrx - nlx) * 0.30
        group.add(Line(points=[nlx - lip, nly, nlx, nly], width=b.wall * 0.45, cap='round'))
        group.add(Line(points=[nrx, nry, nrx + lip, nry], width=b.wall * 0.45, cap='round'))

    def clear_molecules(self):
        """remove all molecules from the game"""
        self.clear_bonds()
        for molecule in self.molecules:
            self.remove_widget(molecule)
        self.molecules.clear()
        gc.collect()

    def create_molecule(self, x, y, vx, vy, eps=None, sig=None, thermo=False):
        """make and add a molecule to the game

        eps/sig default to None, meaning the molecule follows the global
        epsilon and sigma - see Molecule.__init__.
        """
        molecule = Molecule(
            molecule_center=(x, y),
            molecule_radius=self.size[0] * self.molecule_radius_ratio * self.size_factor,
            molecule_vx=vx,
            molecule_vy=vy,
            parent_pos=self.pos[:],
            parent_size=self.size[:],
            forces_visible=self.forces_visible,
            eps=eps, sig=sig, thermo=thermo,
        )
        self.add_widget(molecule)
        self.molecules.append(molecule)
