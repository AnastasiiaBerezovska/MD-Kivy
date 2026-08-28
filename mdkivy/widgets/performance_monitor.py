import threading
import time

class PerformanceMonitor:
    def __init__(self, sample_interval=0.2):
        self.sample_interval = sample_interval

        self._cpu_usage = 0.0
        self._target_usage = 0.0

        self.rise_rate = 1.5
        self.decay_rate = 1.5

        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()

    def _monitor_loop(self):
        print("[MONITOR] Thread started")
        while True:
            if self._cpu_usage < self._target_usage:
                self._cpu_usage += min(self.rise_rate, self._target_usage - self._cpu_usage)
            elif self._cpu_usage > self._target_usage:
                self._cpu_usage -= min(self.decay_rate, self._cpu_usage - self._target_usage)

            self._cpu_usage = max(0, min(self._cpu_usage, 100))
            time.sleep(self.sample_interval)

    def get_cpu_usage(self):
        return round(self._cpu_usage, 1)

    def set_target_usage(self, value):
        self._target_usage = min(max(value, 0), 100)

    def update_simulation_metrics(self, molecule_count, gravity, epsilon, speed, forces_on, 
                                  arduino_activity=0.0, total_energy=0.0):
        """
        Calculate speedometer value based on simulation complexity and Arduino input.
        Represents computational load and system activity.
        """
        if molecule_count == 0:
            self.set_target_usage(0)
            return

        # this feeds the exhibit gauge, not system cpu
        force_multiplier = 2.0 if forces_on else 0.3
        
        molecule_score = (molecule_count ** 1.2) * 0.5
        
        gravity_score = gravity * 2
        epsilon_score = epsilon * 1.5
        speed_score = speed * 5
        
        energy_score = min(total_energy / 50.0, 20)
        
        arduino_score = arduino_activity * 0.5
        
        simulation_load = (molecule_score + gravity_score + epsilon_score + 
                          speed_score + energy_score) * force_multiplier
        
        total_score = simulation_load + arduino_score
        
        self.set_target_usage(total_score)
        
        if molecule_count > 0:
            print(f"[SPEEDOMETER] Molecules:{molecule_count}, Energy:{total_energy:.1f}, "
                  f"Arduino:{arduino_activity:.1f}, Target:{self._target_usage:.1f}%")


_global_monitor = None

def set_global_monitor(monitor):
    global _global_monitor
    _global_monitor = monitor

def get_global_monitor():
    return _global_monitor
