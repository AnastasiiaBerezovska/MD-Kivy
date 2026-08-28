from kivy.uix.boxlayout import BoxLayout
from kivy_garden.graph import Graph, MeshLinePlot
from kivy.clock import Clock
from mdkivy.widgets.performance_monitor import PerformanceMonitor  

class MemoryUsageGraph(BoxLayout):
    def __init__(self, monitor, **kwargs):
        super().__init__(**kwargs)
        self.monitor = monitor

        self.graph = Graph(
            xlabel='Time (s)',
            ylabel='Memory Usage (%)',
            x_ticks_minor=1,
            x_ticks_major=5,

            y_ticks_major=1,
            y_grid_label=True,
            x_grid_label=True,

            xmin=0,
            xmax=60,
            ymin=0,
            ymax=100,

            border_color=[1, 1, 1, 1],
            tick_color=[0.7, 0.7, 0.7, 1],
            label_options={'color': [1, 1, 1, 1], 'bold': True},
        )

        self.plot = MeshLinePlot(color=[0, 1, 0, 1])
        self.graph.add_plot(self.plot)

        self.add_widget(self.graph)

        self.memory_data = []

        Clock.schedule_interval(self.update_graph, 1)

    def update_graph(self, dt):
        """Update the memory usage graph every second."""
        memory_usage = self.monitor.get_memory_usage()
        self.memory_data.append(memory_usage)

        length = len(self.memory_data)
        if length > 60:
            self.graph.xmin = length - 60
            self.graph.xmax = length
        else:
            self.graph.xmin = 0
            self.graph.xmax = 60

        # keep two minutes of samples
        if len(self.memory_data) > 120:
            self.memory_data.pop(0)

        cur_min = min(self.memory_data)
        cur_max = max(self.memory_data)

        self.graph.ymin = max(0, cur_min - 5)
        self.graph.ymax = cur_max + 5

        self.graph.y_ticks_major = 1

        self.plot.points = [(i, val) for i, val in enumerate(self.memory_data)]
