from kivy.uix.boxlayout import BoxLayout
from kivy_garden.graph import Graph, MeshLinePlot
from kivy.clock import Clock
from mdkivy.widgets.performance_monitor import PerformanceMonitor  

class MemoryUsageGraph(BoxLayout):
    def __init__(self, monitor, **kwargs):
        super().__init__(**kwargs)
        self.monitor = monitor

        # make a Graph widget
        self.graph = Graph(
            xlabel='Time (s)',
            ylabel='Memory Usage (%)',
            x_ticks_minor=1,
            x_ticks_major=5,

            # more frequent ticks so you can see memory changes
            # even if the range is small
            y_ticks_major=1,
            y_grid_label=True,
            x_grid_label=True,

            # starting range (changes as we go)
            xmin=0,
            xmax=60,
            ymin=0,
            ymax=100,

            border_color=[1, 1, 1, 1],
            tick_color=[0.7, 0.7, 0.7, 1],
            label_options={'color': [1, 1, 1, 1], 'bold': True},
        )

        # Memory usage plot (green)
        self.plot = MeshLinePlot(color=[0, 1, 0, 1])
        self.graph.add_plot(self.plot)

        # the graph to this layout
        self.add_widget(self.graph)

        # Data storage for memory usage
        self.memory_data = []

        # every second
        Clock.schedule_interval(self.update_graph, 1)

    def update_graph(self, dt):
        """Update the memory usage graph every second."""
        # 1) the latest memory usage from the shared PerformanceMonitor
        memory_usage = self.monitor.get_memory_usage()
        self.memory_data.append(memory_usage)

        # 2) scroll the X-axis (show last 60 samples)
        length = len(self.memory_data)
        if length > 60:
            self.graph.xmin = length - 60
            self.graph.xmax = length
        else:
            self.graph.xmin = 0
            self.graph.xmax = 60

        # 3) the list from growing indefinitely
        if len(self.memory_data) > 120:
            self.memory_data.pop(0)

        # 4) Auto-scale the Y-axis around the min/max of memory_data
        cur_min = min(self.memory_data)
        cur_max = max(self.memory_data)

        # not below 0
        self.graph.ymin = max(0, cur_min - 5)
        self.graph.ymax = cur_max + 5

        # spacing move
        self.graph.y_ticks_major = 1

        # 5) the points on the plot
        self.plot.points = [(i, val) for i, val in enumerate(self.memory_data)]
