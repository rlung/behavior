#!/usr/bin/env python

'''
Sample tkinter live graph
'''

import tkinter as tk
import tkinter.ttk as ttk
import matplotlib
matplotlib.use('TKAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np


class LiveDataView(ttk.Frame):
    def __init__(self, parent, x_history=30, scale_x=1, scale_y = 1, data_types={'default': 'line'}, **ax_kwargs):
        self.parent = parent
        self.x_history = x_history * scale_x
        self.scale_x = scale_x
        self.scale_y = scale_y

        # Create matplotlib figure
        self.fig_preview = Figure()
        self.ax_preview = self.fig_preview.add_subplot(111)
        self.data = {}
        for name, plot_type in data_types.items():
            if plot_type in ['line', 'plot']:
                data, = self.ax_preview.plot(0, 0)
            elif plot_type == 'scatter':
                data = self.ax_preview.scatter(0, 0)
            self.data[name] = data
        self.ax_preview.set(**ax_kwargs)
        self.ax_preview.set_xlim((-self.x_history, 0))

        # Add to tkinter
        self.canvas_preview = FigureCanvasTkAgg(self.fig_preview, self.parent)
        self.canvas_preview.draw()
        self.canvas_preview.get_tk_widget().grid(row=0, column=0, sticky='wens')

    def update_view(self, xy, name='default'):
        # Update data
        # Need to determine the type of plot it is.
        new_xy = xy * np.array([self.scale_x, self.scale_y])
        data_type = type(self.data[name])
        if data_type == matplotlib.lines.Line2D:
            # Line plot
            current = self.data[name].get_xydata()
            updated = self.update_data(current, new_xy)
            self.data[name].set_data(updated.T)
        elif data_type == matplotlib.collections.PathCollection:
            # Scatter plot
            current = self.data[name].get_offsets()
            updated = self.update_data(current, new_xy)
            self.data[name].set_offsets(updated)

        # Update view
        new_xlim = new_xy[0] + np.array([-self.x_history, 0])
        self.ax_preview.set_xlim(new_xlim)
        self.canvas_preview.draw_idle()

    def update_data(self, current, xy):
        # Only keep data for window defined by `x_history`
        # Should keep down on resource usage.
        new_ix = current[:, 0] > xy[0] - self.x_history
        return np.concatenate([current[new_ix, :], [xy]], axis=0)

    def clear_data(self):
        blank = np.zeros((1, 2))
        for name, data in self.data.items():
            data_type = type(self.data[name])
            if data_type == matplotlib.lines.Line2D:
                # Need at least 2 data points for some reason...
                self.data[name].set_data(np.concatenate([blank, blank]))
            elif data_type == matplotlib.collections.PathCollection:
                self.data[name].set_offsets(blank)

        # Update view
        self.ax_preview.set_xlim([-self.x_history, 0])
        self.canvas_preview.draw_idle()


class Sample(ttk.Frame):
    def __init__(self, parent):
        self.parent = parent

        self.live_view = ttk.Frame(self.parent)
        self.live_view.grid()
        self.live_view_ = LiveDataView(self.live_view, x_history=10, ylim=(-1, 1))

        self.xy = np.array([0.0, 0.0])
        self.go_live()

    def go_live(self):
        self.xy[0] = self.xy[0] + 0.1
        self.xy[1] = np.sin(self.xy[0])

        self.live_view_.update_view(self.xy)
        self.parent.after(100, self.go_live)


def main():
    root = tk.Tk()
    Sample(root)
    root.mainloop()


if __name__ == '__main__':
    main()