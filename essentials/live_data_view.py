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
    def __init__(self, parent, x_history=30, ylim=(0, 1), data_types={'default': 'line'}):
        self.parent = parent
        self.x_history = x_history

        self.fig_preview = Figure()
        self.ax_preview = self.fig_preview.add_subplot(111)
        self.data = {}
        for name, plot_type in data_types.items():
            if plot_type == 'line':
                data, = self.ax_preview.plot(0, 0)
            self.data[name] = data
        self.ax_preview.set_xlim((-self.x_history, 0))
        self.ax_preview.set_ylim(ylim)

        self.canvas_preview = FigureCanvasTkAgg(self.fig_preview, self.parent)
        self.canvas_preview.draw()
        self.canvas_preview.get_tk_widget().grid(row=0, column=0, sticky='wens')

    def update_view(self, xy, name='default'):
        old_xy = self.data[name].get_xydata()
        new_xy = np.concatenate([old_xy, [xy]], axis=0)
        self.data[name].set_data(new_xy.T)
        self.ax_preview.set_xlim(xy[0] + np.array([-self.x_history, 0]))
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
        print(self.xy)
        self.xy[0] = self.xy[0] + 0.1
        self.xy[1] = np.sin(self.xy[0])
        print(self.xy)
        self.live_view_.update_view(self.xy)
        self.parent.after(100, self.go_live)


def main():
    root = tk.Tk()
    Sample(root)
    root.mainloop()


if __name__ == '__main__':
    main()