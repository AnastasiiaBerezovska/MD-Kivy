from kivy.uix.boxlayout import BoxLayout
from kivy_garden.graph import Graph, MeshLinePlot
from kivy.clock import Clock
from mdkivy.widgets.performance_monitor import PerformanceMonitor

def integer_formatter(value):
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
            border_color=[0.3, 1, 0.3, 1],
            tick_color=[0.5, 0.8, 0.5, 1],
            label_options={'color': [0.7, 1, 0.7, 1], 'bold': True}
        )

        self.graph.y_label_func = integer_formatter

        self.glow_outer = MeshLinePlot(color=[0.2, 0.8, 0.2, 0.15])
        self.graph.add_plot(self.glow_outer)
        
        self.glow_middle = MeshLinePlot(color=[0.3, 0.9, 0.3, 0.25])
        self.graph.add_plot(self.glow_middle)
        
        self.glow_inner = MeshLinePlot(color=[0.4, 1, 0.4, 0.4])
        self.graph.add_plot(self.glow_inner)
        
        self.plot = MeshLinePlot(color=[0.5, 1, 0.5, 1])
        self.graph.add_plot(self.plot)
        
        self.add_widget(self.graph)

        self.cpu_data = []

        Clock.schedule_interval(self.update_graph, 1)

    def update_graph(self, dt):
        cpu_usage = self.monitor.get_cpu_usage()
        self.cpu_data.append(cpu_usage)
        length = len(self.cpu_data)

        if length > 60:
            self.graph.xmin = length - 60
            self.graph.xmax = length
        else:
            self.graph.xmin = 0
            self.graph.xmax = 60

        # keep two minutes of samples
        if len(self.cpu_data) > 120:
            self.cpu_data.pop(0)

        points = [(i, val) for i, val in enumerate(self.cpu_data)]
        self.plot.points = points
        self.glow_outer.points = points
        self.glow_middle.points = points
        self.glow_inner.points = points

        ymin = max(0, min(self.cpu_data) - 5)
        ymax = max(self.cpu_data) + 5
        self.graph.ymin = ymin
        self.graph.ymax = ymax
