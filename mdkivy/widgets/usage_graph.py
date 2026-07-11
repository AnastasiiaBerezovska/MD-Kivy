from kivy.uix.boxlayout import BoxLayout
from kivy_garden.graph import Graph, MeshLinePlot
from kivy.clock import Clock
from mdkivy.widgets.performance_monitor import PerformanceMonitor

def integer_formatter(value):
    # Round and convert to int if want no decimals
    return str(int(round(value)))

class CPUUsageGraph(BoxLayout): 
    def __init__(self, monitor, **kwargs):
        super().__init__(**kwargs)
        self.monitor = monitor

        self.graph = Graph(
            xlabel='Time (s)',
            ylabel='CPU Usage (%)',
            x_ticks_minor=1,
            x_ticks_major=5,
            y_ticks_major=10,
            y_grid_label=True,
            x_grid_label=True,
            xmin=0,
            xmax=60,
            ymin=0,
            ymax=100,
            border_color=[0.3, 1, 0.3, 1],  # Green border to match theme
            tick_color=[0.5, 0.8, 0.5, 1],  # Green ticks
            label_options={'color': [0.7, 1, 0.7, 1], 'bold': True}  # Green labels
        )

        # the Y-axis to use integer labels
        self.graph.y_label_func = integer_formatter

        # Add glow layers behind the main plot for a glowing effect
        # Outer glow (widest, most transparent)
        self.glow_outer = MeshLinePlot(color=[0.2, 0.8, 0.2, 0.15])
        self.graph.add_plot(self.glow_outer)
        
        # Middle glow
        self.glow_middle = MeshLinePlot(color=[0.3, 0.9, 0.3, 0.25])
        self.graph.add_plot(self.glow_middle)
        
        # Inner glow
        self.glow_inner = MeshLinePlot(color=[0.4, 1, 0.4, 0.4])
        self.graph.add_plot(self.glow_inner)
        
        # Main bright line on top
        self.plot = MeshLinePlot(color=[0.5, 1, 0.5, 1])
        self.graph.add_plot(self.plot)
        
        self.add_widget(self.graph)

        self.cpu_data = []

        Clock.schedule_interval(self.update_graph, 1)

    def update_graph(self, dt):
        cpu_usage = self.monitor.get_cpu_usage()
        self.cpu_data.append(cpu_usage)
        length = len(self.cpu_data)

        # Shift X-axis
        if length > 60:
            self.graph.xmin = length - 60
            self.graph.xmax = length
        else:
            self.graph.xmin = 0
            self.graph.xmax = 60

        # Bound the history length
        if len(self.cpu_data) > 120:
            self.cpu_data.pop(0)

        # Updating the main plot and glow layers
        points = [(i, val) for i, val in enumerate(self.cpu_data)]
        self.plot.points = points
        # Update glow layers with same points for layered effect
        self.glow_outer.points = points
        self.glow_middle.points = points
        self.glow_inner.points = points

        #the Y-axis with buffer
        ymin = max(0, min(self.cpu_data) - 5)
        ymax = max(self.cpu_data) + 5
        self.graph.ymin = ymin
        self.graph.ymax = ymax
