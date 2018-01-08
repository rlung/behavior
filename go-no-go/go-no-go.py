#!/usr/bin/env python

'''
Go/no go

Creates GUI to control behavioral and imaging devices for in vivo calcium
imaging. Script interfaces with Arduino microcontroller and imaging devices.

Opens serial connection with Arduino that controls hardware and timing. Creates 
a dedicated thread to scan serial connection for incoming data to save in HDF5 
file.

Packages needed:
- pyserial
- slackclient
'''

import sys
is_py2 = sys.version[0] == '2'

import matplotlib
matplotlib.use('TKAgg')
if is_py2:
    import Tkinter as tk
    import tkFont
    import tkMessageBox
    import tkFileDialog
    from ScrolledText import ScrolledText
    from Queue import Queue
else:
    import tkinter as tk
    import tkinter.font as tkFont
    import tkinter.messagebox as tkMessageBox
    import tkinter.filedialog as tkFileDialog
    from tkinter.scrolledtext import ScrolledText
    from queue import Queue
from PIL import ImageTk
import collections
import serial
import serial.tools.list_ports
import threading
import time
from datetime import datetime
from datetime import timedelta
import os
import sys
import h5py
import numpy as np
from matplotlib.figure import Figure
import matplotlib.animation as animation
from matplotlib.colors import LinearSegmentedColormap
from matplotlib import style
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2TkAgg
from slackclient import SlackClient
import pdb


# Setup Slack
try:
    slack_token = os.environ['SLACK_API_TOKEN']
except KeyError:
    print('Environment variable SLACK_API_TOKEN not identified')
    slack = None
else:
    slack = SlackClient(slack_token)

# Header to print with Arduino outputs
arduino_head = '  [a]: '


class InputManager(tk.Frame):

    def __init__(self, parent):
        tk.Frame.__init__(self, parent)

        # GUI layout
        # parent
        # - frame_setup
        #   + frame_cam
        #   + frame_debug
        #   + frame_params
        #     ~ frame_session_type
        #     ~ frame_session
        #     ~ frame_trial
        #     ~ frame_gonogo
        #     ~ frame_csus0
        #     ~ frame_csus1
        #     ~ frame_misc
        #   + frame_notes
        #   + frame_file

        #   + hardware_frame
        #     ~ frame_preview
        #     ~ frame_cam
        #     ~ serial_frame
        #     ~ debug_frame
        #   + frame_start
        #   + slack_frame
        # - monitor_frame
        #   + (figure)
        #   + scoreboard_frame

        entry_width = 10
        ew = 10  # Width of Entry UI
        px = 15
        py = 5
        px1 = 5
        py1 = 2

        self.parent = parent
        parent.columnconfigure(0, weight=1)

        # Lay out GUI

        ## Setup frame
        frame_setup = tk.Frame(parent)
        frame_setup.grid(row=0, column=0)
        frame_setup_col0 = tk.Frame(frame_setup)
        frame_setup_col1 = tk.Frame(frame_setup)
        frame_setup_col2 = tk.Frame(frame_setup)
        frame_setup_col0.grid(row=0, column=0, sticky='we')
        frame_setup_col1.grid(row=0, column=1, sticky='we')
        frame_setup_col2.grid(row=0, column=2, sticky='we')
        # frame_setup.grid_columnconfigure(0, weight=1)
        # frame_setup.grid_columnconfigure(1, weight=1)
        # frame_setup.grid_columnconfigure(2, weight=5)

        ### Camera frame
        frame_cam = tk.Frame(frame_setup_col0)
        frame_cam.grid(row=0, column=0, padx=px, pady=py)

        ### Arduino frame
        frame_arduino = tk.LabelFrame(frame_setup_col0, text='Arduino')
        frame_arduino.grid(row=1, column=0, padx=px, pady=py)
        frame_arduino1 = tk.Frame(frame_arduino)
        frame_arduino2 = tk.Frame(frame_arduino)
        frame_arduino1.grid(row=0, column=0, sticky='we', padx=px, pady=py)
        frame_arduino2.grid(row=1, column=0, sticky='we', padx=px, pady=py)
        frame_arduino2.grid_columnconfigure(0, weight=1)
        frame_arduino2.grid_columnconfigure(1, weight=1)

        ### Debug frame
        frame_debug = tk.LabelFrame(frame_setup_col0, text='Debug')
        frame_debug.grid(row=2, column=0, padx=px, pady=py)

        ### Session frame
        frame_params = tk.Frame(frame_setup_col1)
        frame_params.grid(row=0, column=0, rowspan=3, padx=px, pady=py)
        frame_params.columnconfigure(0, weight=1)

        frame_session_type = tk.Frame(frame_params)
        frame_session = tk.Frame(frame_params)
        frame_trial = tk.Frame(frame_params)
        frame_csus0 = tk.Frame(frame_params)
        frame_csus1 = tk.Frame(frame_params)
        frame_gonogo = tk.Frame(frame_params)
        frame_misc = tk.Frame(frame_params)
        frame_session_type.grid(row=0, column=0, sticky='e', padx=px, pady=py)
        frame_session.grid(row=1, column=0, sticky='e', padx=px, pady=py)
        frame_trial.grid(row=2, column=0, sticky='e', padx=px, pady=py)
        frame_csus0.grid(row=3, column=0, sticky='e', padx=px, pady=py)
        frame_csus1.grid(row=4, column=0, sticky='e', padx=px, pady=py)
        frame_gonogo.grid(row=5, column=0, sticky='e', padx=px, pady=py)
        frame_misc.grid(row=6, column=0, sticky='e', padx=px, pady=py)

        ### Notes frame
        frame_notes = tk.Frame(frame_setup_col2)
        frame_notes.grid(row=0, column=0, sticky='we', padx=px, pady=py)
        frame_notes.grid_columnconfigure(0, weight=1)

        ### Saved file frame
        frame_file = tk.Frame(frame_setup_col2)
        frame_file.grid(row=1, column=0, sticky='we', padx=px, pady=py)
        frame_file.grid_columnconfigure(0, weight=3)
        frame_file.grid_columnconfigure(1, weight=1)

        ### Slack frame
        frame_slack = tk.Frame(frame_setup_col2)
        frame_slack.grid(row=2, column=0, sticky='we', padx=px, pady=py)
        frame_slack.grid_columnconfigure(0, weight=3)
        frame_slack.grid_columnconfigure(1, weight=1)

        ### Start-stop frame
        frame_start = tk.Frame(frame_setup_col2)
        frame_start.grid(row=3, column=0, sticky='we', padx=px, pady=py)
        frame_start.grid_columnconfigure(0, weight=1)
        frame_start.grid_columnconfigure(1, weight=1)

        # Add GUI components

        ## Camera preview
        cam_x = 1280
        cam_y = 1024
        scale = 0.2
        dpi = 300.
        self.fig_preview = Figure(dpi=dpi, figsize=(cam_x / dpi * scale, cam_y / dpi * scale))
        self.ax_preview = self.fig_preview.add_axes([0, 0, 1, 1])
        self.fig_preview.subplots_adjust(left=0, bottom=0, right=1, top=1, wspace=0, hspace=0)
        self.im = self.ax_preview.imshow(np.zeros((1024, 1280)), vmin=1, vmax=254, cmap='gray', interpolation='none')
        self.ax_preview.axis('image')
        self.ax_preview.axis('off')
        self.canvas_preview = FigureCanvasTkAgg(self.fig_preview, frame_cam)
        self.canvas_preview.show()
        self.canvas_preview.draw()
        self.canvas_preview.get_tk_widget().grid(row=0, column=0, sticky='wens')

        ### Set high/low colors
        self.im.cmap.set_under('b')
        self.im.cmap.set_over('r')

        ## frame_arduino
        ## Arduino setup
        self.port_var = tk.StringVar()
        self.entry_serial_status = tk.Entry(frame_arduino1)
        self.option_ports = tk.OptionMenu(frame_arduino1, self.port_var, [])
        self.button_update_ports = tk.Button(frame_arduino1, text='u', command=self.update_ports)
        self.button_open_port = tk.Button(frame_arduino2, text='Open', command=self.open_serial)
        self.button_close_port = tk.Button(frame_arduino2, text='Close', command=self.close_serial)
        tk.Label(frame_arduino1, text='Port: ').grid(row=0, column=0, sticky='e')
        tk.Label(frame_arduino1, text='State: ').grid(row=1, column=0, sticky='e')
        self.option_ports.grid(row=0, column=1, sticky='we', padx=px1)
        self.entry_serial_status.grid(row=1, column=1, sticky='w', padx=px1)
        self.button_update_ports.grid(row=0, column=2, pady=py)
        self.button_open_port.grid(row=0, column=0, pady=py, sticky='we')
        self.button_close_port.grid(row=0, column=1, pady=py, sticky='we')

        self.entry_serial_status.insert(0, 'Closed')
        self.entry_serial_status['state'] = 'normal'
        self.entry_serial_status['state'] = 'readonly'
        self.button_close_port['state'] = 'disabled'

        ## frame_debug
        ## UI for debugging options.
        self.var_verbose = tk.BooleanVar()
        self.var_print_arduino = tk.BooleanVar()
        self.check_verbose = tk.Checkbutton(frame_debug, variable=self.var_verbose)
        self.check_print_arduino = tk.Checkbutton(frame_debug, variable=self.var_print_arduino)
        tk.Label(frame_debug, text='Verbose: ', anchor='e').grid(row=0, column=0, sticky='e')
        tk.Label(frame_debug, text='Print Arduino serial: ', anchor='e').grid(row=1, column=0, sticky='e')
        self.check_verbose.grid(row=0, column=1, sticky='w')
        self.check_print_arduino.grid(row=1, column=1, sticky='w')

        ## frame_params
        ## Session parameters

        ### frame_session_type
        ### UI for choosing session type, ie, classical conditining vs go/no go.
        self.var_session_type = tk.IntVar()
        self.radio_conditioning = tk.Radiobutton(frame_session_type, variable=self.var_session_type, value=0, command=lambda: self.gui_util('pavlov'))
        self.radio_gonogo = tk.Radiobutton(frame_session_type, variable=self.var_session_type, value=1, command=lambda: self.gui_util('gonogo'))
        tk.Label(frame_session_type, text='Classical conditioning: ', anchor='e').grid(row=0, column=0, sticky='e')
        tk.Label(frame_session_type, text='Go/no go: ', anchor='e').grid(row=1, column=0, sticky='e')
        self.radio_conditioning.grid(row=0, column=1, sticky='w')
        self.radio_gonogo.grid(row=1, column=1, sticky='w')

        ### frame_session
        ### UI for session.
        self.entry_cs0_num = tk.Entry(frame_session, width=entry_width)
        self.entry_cs1_num = tk.Entry(frame_session, width=entry_width)
        self.entry_pre_session = tk.Entry(frame_session, width=entry_width)
        self.entry_post_session = tk.Entry(frame_session, width=entry_width)
        tk.Label(frame_session, text='Presession time (ms): ', anchor='e').grid(row=0, column=0, sticky='e')
        tk.Label(frame_session, text='Postsession time (ms): ', anchor='e').grid(row=1, column=0, sticky='e')
        tk.Label(frame_session, text='Number of CS0: ', anchor='e').grid(row=2, column=0, sticky='e')
        tk.Label(frame_session, text='Number of CS1: ', anchor='e').grid(row=3, column=0, sticky='e')
        self.entry_pre_session.grid(row=0, column=1, sticky='w')
        self.entry_post_session.grid(row=1, column=1, sticky='w')
        self.entry_cs0_num.grid(row=2, column=1, sticky='w')
        self.entry_cs1_num.grid(row=3, column=1, sticky='w')

        ### frame_trial
        ### UI for trial.
        self.var_iti_distro = tk.IntVar()
        self.radio_fixed_iti = tk.Radiobutton(frame_trial, variable=self.var_iti_distro, value=0, command=lambda: self.gui_util('fixed'))
        self.radio_uniform_iti = tk.Radiobutton(frame_trial, variable=self.var_iti_distro, value=1, command=lambda: self.gui_util('not_fixed'))
        self.radio_expo_iti = tk.Radiobutton(frame_trial, variable=self.var_iti_distro, value=2, command=lambda: self.gui_util('not_fixed'))
        self.entry_mean_iti = tk.Entry(frame_trial, width=entry_width)
        self.entry_min_iti = tk.Entry(frame_trial, width=entry_width)
        self.entry_max_iti = tk.Entry(frame_trial, width=entry_width)
        self.entry_pre_stim = tk.Entry(frame_trial, width=entry_width)
        self.entry_post_stim = tk.Entry(frame_trial, width=entry_width)
        tk.Label(frame_trial, text='Fixed ITI: ', anchor='e').grid(row=0, column=0, sticky='e')
        tk.Label(frame_trial, text='Uniform distro: ', anchor='e').grid(row=1, column=0, sticky='e')
        tk.Label(frame_trial, text='Exponential distro: ', anchor='e').grid(row=2, column=0, sticky='e')
        tk.Label(frame_trial, text='Mean ITI (ms): ', anchor='e').grid(row=3, column=0, sticky='e')
        tk.Label(frame_trial, text='Min ITI (ms): ', anchor='e').grid(row=4, column=0, sticky='e')
        tk.Label(frame_trial, text='Max ITI (ms): ', anchor='e').grid(row=5, column=0, sticky='e')
        tk.Label(frame_trial, text='Prestim time (ms): ', anchor='e').grid(row=6, column=0, sticky='e')
        tk.Label(frame_trial, text='Poststim time (ms): ', anchor='e').grid(row=7, column=0, sticky='e')
        self.radio_fixed_iti.grid(row=0, column=1, sticky='w')
        self.radio_uniform_iti.grid(row=1, column=1, sticky='w')
        self.radio_expo_iti.grid(row=2, column=1, sticky='w')
        self.entry_mean_iti.grid(row=3, column=1, sticky='w')
        self.entry_min_iti.grid(row=4, column=1, sticky='w')
        self.entry_max_iti.grid(row=5, column=1, sticky='w')
        self.entry_pre_stim.grid(row=6, column=1, sticky='w')
        self.entry_post_stim.grid(row=7, column=1, sticky='w')

        ### frame_csus0
        ### UI for CS-US 0.
        self.entry_cs0_dur = tk.Entry(frame_csus0, width=entry_width)
        self.entry_cs0_freq = tk.Entry(frame_csus0, width=entry_width)
        self.entry_us0_delay = tk.Entry(frame_csus0, width=entry_width)
        self.entry_us0_dur = tk.Entry(frame_csus0, width=entry_width)
        tk.Label(frame_csus0, text='CS0 duration (ms): ', anchor='e').grid(row=10, column=0, sticky='e')
        tk.Label(frame_csus0, text='CS0 frequency (s' u'\u207b\u00b9' '): ', anchor='e').grid(row=11, column=0, sticky='e')
        tk.Label(frame_csus0, text='US0 delay (ms): ', anchor='e').grid(row=12, column=0, sticky='e')
        tk.Label(frame_csus0, text='US0 duration (ms): ', anchor='e').grid(row=13, column=0, sticky='e')
        self.entry_cs0_dur.grid(row=10, column=1, sticky='w')
        self.entry_cs0_freq.grid(row=11, column=1, sticky='w')
        self.entry_us0_delay.grid(row=12, column=1, sticky='w')
        self.entry_us0_dur.grid(row=13, column=1, sticky='w')

        ### frame_csus1
        ### UI for CS-US 1.
        self.entry_cs1_dur = tk.Entry(frame_csus1, width=entry_width)
        self.entry_cs1_freq = tk.Entry(frame_csus1, width=entry_width)
        self.entry_us1_delay = tk.Entry(frame_csus1, width=entry_width)
        self.entry_us1_dur = tk.Entry(frame_csus1, width=entry_width)
        tk.Label(frame_csus1, text='CS1 duration (ms): ', anchor='e').grid(row=14, column=0, sticky='e')
        tk.Label(frame_csus1, text='CS1 frequency (s' u'\u207b\u00b9' '): ', anchor='e').grid(row=15, column=0, sticky='e')
        tk.Label(frame_csus1, text='US1 delay (ms): ', anchor='e').grid(row=16, column=0, sticky='e')
        tk.Label(frame_csus1, text='US1 duration (ms): ', anchor='e').grid(row=17, column=0, sticky='e')
        self.entry_cs1_dur.grid(row=14, column=1, sticky='w')
        self.entry_cs1_freq.grid(row=15, column=1, sticky='w')
        self.entry_us1_delay.grid(row=16, column=1, sticky='w')
        self.entry_us1_dur.grid(row=17, column=1, sticky='w')

        ### frame_gonogo
        ### UI for trial start (signal)
        self.entry_trial_signal_offset = tk.Entry(frame_gonogo, width=entry_width)
        self.entry_trial_signal_dur = tk.Entry(frame_gonogo, width=entry_width)
        self.entry_trial_signal_freq = tk.Entry(frame_gonogo, width=entry_width)
        self.entry_grace_dur = tk.Entry(frame_gonogo, width=entry_width)
        self.entry_response_dur = tk.Entry(frame_gonogo, width=entry_width)
        self.entry_timeout_dur = tk.Entry(frame_gonogo, width=entry_width)
        tk.Label(frame_gonogo, text='Trial signal offset (ms): ', anchor='e').grid(row=0, column=0, sticky='e')
        tk.Label(frame_gonogo, text='Trial signal duration (ms): ', anchor='e').grid(row=1, column=0, sticky='e')
        tk.Label(frame_gonogo, text='Trial signal frequency (s' u'\u207b\u00b9' '): ', anchor='e').grid(row=2, column=0, sticky='e')
        tk.Label(frame_gonogo, text='Grace period (ms): ', anchor='e').grid(row=3, column=0, sticky='e')
        tk.Label(frame_gonogo, text='Response window (ms): ', anchor='e').grid(row=4, column=0, sticky='e')
        tk.Label(frame_gonogo, text='Timeout duration (ms): ', anchor='e').grid(row=5, column=0, sticky='e')
        self.entry_trial_signal_offset.grid(row=0, column=1, sticky='w')
        self.entry_trial_signal_dur.grid(row=1, column=1, sticky='w')
        self.entry_trial_signal_freq.grid(row=2, column=1, sticky='w')
        self.entry_grace_dur.grid(row=3, column=1, sticky='w')
        self.entry_response_dur.grid(row=4, column=1, sticky='w')
        self.entry_timeout_dur.grid(row=5, column=1, sticky='w')

        ### frame_misc
        ### UI for other things.
        self.var_image_all = tk.BooleanVar()
        self.entry_image_ttl_dur = tk.Entry(frame_misc, width=entry_width)
        self.check_image_all = tk.Checkbutton(frame_misc, variable=self.var_image_all)
        self.entry_track_period = tk.Entry(frame_misc, width=entry_width)
        tk.Label(frame_misc, text='Image everything: ', anchor='e').grid(row=0, column=0, sticky='e')
        tk.Label(frame_misc, text='Imaging TTL duration (ms): ', anchor='e').grid(row=1, column=0, sticky='e')
        tk.Label(frame_misc, text='Track period (ms): ', anchor='e').grid(row=2, column=0, sticky='e')
        self.check_image_all.grid(row=0, column=1, sticky='w')
        self.entry_image_ttl_dur.grid(row=1, column=1, sticky='w')
        self.entry_track_period.grid(row=2, column=1, sticky='w')

        ## frame_notes
        ## UI for note taking.
        tk.Label(frame_notes, text="Notes: ").grid(row=0, column=0, sticky='w')
        self.scrolled_notes = ScrolledText(frame_notes, width=20, height=15)
        self.scrolled_notes.grid(row=1, column=0, sticky='wens')

        ## frame_file
        ## UI for saved file.
        self.entry_file = tk.Entry(frame_file)
        self.button_find_file = tk.Button(frame_file, text='...', command=self.get_save_file)
        tk.Label(frame_file, text='File to save data:', anchor='w').grid(row=0, column=0, columnspan=4, sticky='w')
        self.entry_file.grid(row=1, column=0, sticky='wens')
        self.button_find_file.grid(row=1, column=1, sticky='e')

        ### Add icon to folder
        icon_folder = ImageTk.PhotoImage(file='icon_folder.png')
        self.button_find_file.config(image=icon_folder)
        self.button_find_file.image = icon_folder  #Keeping a reference to the image

        ## frame_slack
        ## UI for slack notifications.
        self.entry_slack = tk.Entry(frame_slack)
        self.button_slack = tk.Button(frame_slack, text='', command=lambda: slack_msg(self.entry_slack.get(), 'Test', test=True))
        tk.Label(frame_slack, text="Slack address: ", anchor='w').grid(row=0, column=0, sticky='we')
        self.entry_slack.grid(row=1, column=0, sticky='wens')
        self.button_slack.grid(row=1, column=1, sticky='e')

        ### Add icon to folder
        icon_slack = ImageTk.PhotoImage(file='icon_slack.png')
        self.button_slack.config(image=icon_slack)
        self.button_slack.image = icon_slack

        ## frame_start
        ## UI for starting and stopping session.
        self.var_stop = tk.BooleanVar()
        self.var_stop.set(False)
        self.button_start = tk.Button(frame_start, text='Start', command=lambda: self.parent.after(0, self.start))
        self.button_stop = tk.Button(frame_start, text='Stop', command=lambda: self.var_stop.set(True))
        self.button_start.grid(row=0, column=0, sticky='we')
        self.button_stop.grid(row=0, column=1, sticky='we')
        
        self.button_start['state'] = 'disabled'
        self.button_stop['state'] = 'disabled'

        ## Group GUI objects
        self.obj_not_fixed_iti = [
            self.entry_min_iti,
            self.entry_max_iti,
        ]
        self.obj_pavlov = [
            self.entry_us0_delay,
            self.entry_us1_delay,
        ]
        self.obj_gonogo = [
            self.entry_trial_signal_offset,
            self.entry_trial_signal_dur,
            self.entry_trial_signal_freq,
            self.entry_grace_dur,
            self.entry_response_dur,
            self.entry_timeout_dur,
        ]
        self.obj_to_disable_at_open = [
            self.option_ports,
            self.button_open_port,
            self.button_update_ports,
            self.radio_conditioning,
            self.radio_gonogo,
            self.entry_pre_session,
            self.entry_post_session,
            self.entry_cs0_num,
            self.entry_cs1_num,
            self.radio_fixed_iti,
            self.radio_uniform_iti,
            self.radio_expo_iti,
            self.entry_mean_iti,
            self.entry_min_iti,
            self.entry_max_iti,
            self.entry_pre_stim,
            self.entry_post_stim,
            self.entry_cs0_dur,
            self.entry_cs0_freq,
            self.entry_us0_delay,
            self.entry_us0_dur,
            self.entry_cs1_dur,
            self.entry_cs1_freq,
            self.entry_us1_delay,
            self.entry_us1_dur,
            self.entry_trial_signal_offset,
            self.entry_trial_signal_dur,
            self.entry_trial_signal_freq,
            self.entry_grace_dur,
            self.entry_response_dur,
            self.entry_timeout_dur,
            self.check_image_all,
            self.entry_image_ttl_dur,
            self.entry_track_period,
        ]
        self.obj_to_enable_when_open = [
            self.button_close_port,
            self.button_start,
        ]
        self.obj_to_disable_at_start = [
            self.button_close_port,
            self.button_find_file,
            self.button_slack,
            self.button_start,
        ]
        self.obj_to_enable_at_start = [
            self.button_stop,
        ]

        # Boolean of objects states at open
        # Useful if object states are volatile, but state should be returned 
        # once serial is closed.
        self.obj_enabled_at_open = [False] * len(self.obj_to_disable_at_open)

        # Default values

        ## Session values
        ## Example: 0+3000+3000+3+1 + 0+60000+17000+360000+5000+10000 + 500+1000+100+500+500+5000+100+500 + 500+100+0+2000+2000+8000 + 0+100+50
        self.var_session_type.set(0)
        self.entry_pre_session.insert(0, 30000)
        self.entry_post_session.insert(0, 30000)
        self.entry_cs0_num.insert(0, 3)
        self.entry_cs1_num.insert(0, 1)
        
        self.var_iti_distro.set(0)
        self.entry_mean_iti.insert(0, 60000)
        self.entry_min_iti.insert(0, 40000)
        self.entry_max_iti.insert(0, 80000)
        self.entry_pre_stim.insert(0, 7000)
        self.entry_post_stim.insert(0, 13000)
        
        self.entry_cs0_dur.insert(0, 2000)
        self.entry_cs0_freq.insert(0, 1000)
        self.entry_us0_delay.insert(0, 3000)
        self.entry_us0_dur.insert(0, 50)
        self.entry_cs1_dur.insert(0, 2000)
        self.entry_cs1_freq.insert(0, 5000)
        self.entry_us1_delay.insert(0, 3000)
        self.entry_us1_dur.insert(0, 50)

        self.entry_trial_signal_offset.insert(0, 0)
        self.entry_trial_signal_dur.insert(0, 0)
        self.entry_trial_signal_freq.insert(0, 0)
        self.entry_grace_dur.insert(0, 2000)
        self.entry_response_dur.insert(0, 2000)
        self.entry_timeout_dur.insert(0, 0)

        self.var_image_all.set(0)
        self.entry_image_ttl_dur.insert(0, 100)
        self.entry_track_period.insert(0, 50)

        # Finalize
        self.parameters = collections.OrderedDict()
        self.ser = serial.Serial(timeout=1, baudrate=9600)
        self.update_ports()
        self.q_serial = Queue()
        self.counter = {}

    def gui_util(self, option):
        '''Updates GUI components
        Enable and disable components based on events to prevent bad stuff.
        '''

        if option == 'fixed':
            for obj in self.obj_not_fixed_iti:
                obj['state'] = 'disabled'
        if option == 'not_fixed':
            for obj in self.obj_not_fixed_iti:
                obj['state'] = 'normal'
        elif option == 'pavlov':
            for obj in self.obj_gonogo:
                obj['state'] = 'disabled'
            for obj in self.obj_pavlov:
                obj['state'] = 'normal'
        elif option == 'gonogo':
            for obj in self.obj_pavlov:
                obj['state'] = 'disabled'
            for obj in self.obj_gonogo:
                obj['state'] = 'normal'
        elif option == 'open':
            for i, obj in enumerate(self.obj_to_disable_at_open):
                # Determine current state of object                
                self.obj_enabled_at_open[i] = False if obj['state'] == 'disabled' else True
                
                # Disable object
                obj['state'] = 'disabled'

            self.entry_serial_status.config(state='normal', fg='red')
            self.entry_serial_status.delete(0, 'end')
            self.entry_serial_status.insert(0, 'Opening...')
            self.entry_serial_status['state'] = 'readonly'
        elif option == 'opened':
            # Enable start objects
            for obj in self.obj_to_enable_when_open:
                obj['state'] = 'normal'

            self.entry_serial_status.config(state='normal', fg='black')
            self.entry_serial_status.delete(0, 'end')
            self.entry_serial_status.insert(0, 'Opened')
            self.entry_serial_status['state'] = 'readonly'
        elif option == 'close':
            for obj, to_enable in zip(self.obj_to_disable_at_open, self.obj_enabled_at_open):
                if to_enable: obj['state'] = 'normal'
            for obj in self.obj_to_enable_when_open:
                obj['state'] = 'disabled'

            self.entry_serial_status.config(state='normal', fg='black')
            self.entry_serial_status.delete(0, 'end')
            self.entry_serial_status.insert(0, 'Closed')
            self.entry_serial_status['state'] = 'readonly'
        elif option == 'start':
            for obj in self.obj_to_disable_at_start:
                obj['state'] = 'disabled'
            for obj in self.obj_to_enable_at_start:
                obj['state'] = 'normal'
        elif option == 'stop':
            for obj in self.obj_to_disable_at_start:
                obj['state'] = 'normal'
            for obj in self.obj_to_enable_at_start:
                obj['state'] = 'disabled'

            self.entry_serial_status.config(state='normal', fg='black')
            self.entry_serial_status.delete(0, tk.END)
            self.entry_serial_status.insert(0, 'Closed')
            self.entry_serial_status['state'] = 'readonly'

    def open_serial(self, delay=3, timeout=5):
        '''Open serial connection to Arduino
        Executes when 'Open' button is pressed. `delay` sets amount of time (in
        seconds) to wait for the Arduino to be ready after serial is open.
        '''
        
        # Disable GUI components
        self.gui_util('open')

        # Open serial
        self.ser.port = self.port_var.get()
        try:
            self.ser.open()
        except serial.SerialException as err:
            # Error during serial.open()
            err_msg = err.args[1] if is_py2 else err.message
            tkMessageBox.showerror('Serial error', err_msg)
            print('Serial error: ' + err_msg)
            self.close_serial()
            self.gui_util('close')
            return
        else:
            # Serial opened successfully
            time.sleep(delay)
            self.gui_util('opened')
            if self.var_verbose.get(): print('Connection to Arduino opened')

        # Handle opening message from serial
        if self.var_print_arduino.get():
            while self.ser.in_waiting:
                sys.stdout.write(arduino_head + self.ser.readline())
        else:
            self.ser.flushInput()

        # Define parameters
        # NOTE: Order is important here since this order is preserved when 
        # sending via serial.
        self.parameters = collections.OrderedDict()   # Clear self.parameters (maybe not necessary)

        self.parameters['session_type'] = int(self.var_session_type.get())
        self.parameters['pre_session'] = int(self.entry_pre_session.get())
        self.parameters['post_session'] = int(self.entry_post_session.get())
        self.parameters['cs0_num'] = int(self.entry_cs0_num.get())
        self.parameters['cs1_num'] = int(self.entry_cs1_num.get())

        self.parameters['iti_distro'] = int(self.var_iti_distro.get())
        self.parameters['mean_iti'] = int(self.entry_mean_iti.get())
        self.parameters['min_iti'] = int(self.entry_min_iti.get())
        self.parameters['max_iti'] = int(self.entry_max_iti.get())
        self.parameters['pre_stim'] = int(self.entry_pre_stim.get())
        self.parameters['post_stim'] = int(self.entry_post_stim.get())

        self.parameters['cs0_dur'] = int(self.entry_cs0_dur.get())
        self.parameters['cs0_freq'] = int(self.entry_cs0_freq.get())
        self.parameters['us0_delay'] = int(self.entry_us0_delay.get())
        self.parameters['us0_dur'] = int(self.entry_us0_dur.get())
        self.parameters['cs1_dur'] = int(self.entry_cs1_dur.get())
        self.parameters['cs1_freq'] = int(self.entry_cs1_freq.get())
        self.parameters['us1_delay'] = int(self.entry_us1_delay.get())
        self.parameters['us1_dur'] = int(self.entry_us1_dur.get())

        self.parameters['trial_signal_offset'] = int(self.entry_trial_signal_offset.get())
        self.parameters['trial_signal_dur'] = int(self.entry_trial_signal_dur.get())
        self.parameters['trial_signal_freq'] = int(self.entry_trial_signal_freq.get())
        self.parameters['grace_dur'] = int(self.entry_grace_dur.get())
        self.parameters['response_dur'] = int(self.entry_response_dur.get())
        self.parameters['timeout_dur'] = int(self.entry_timeout_dur.get())

        self.parameters['image_all'] = int(self.var_image_all.get())
        self.parameters['image_ttl_dur'] = int(self.entry_image_ttl_dur.get())
        self.parameters['track_period'] = int(self.entry_track_period.get())
        
        # Send parameters and make sure it's processed
        values = self.parameters.values()
        if self.var_verbose.get(): print('Sending parameters: {}'.format(values))
        self.ser.write('+'.join(str(s) for s in values))

        start_time = time.time()
        while 1:
            if self.ser.in_waiting:
                if self.var_print_arduino.get():
                    # Print incoming data
                    while self.ser.in_waiting:
                        sys.stdout.write(arduino_head + self.ser.readline())
                print('Parameters uploaded to Arduino')
                print('Ready to start')
                return
            elif time.time() >= start_time + timeout:
                print('Error sending parameters to Arduino')
                print('Uploading timed out. Start signal not found.')
                self.gui_util('close')
                self.close_serial()
                return


    def close_serial(self):
        '''Close serial connection to Arduino on button press'''

        self.ser.close()
        self.gui_util('close')
        if self.var_verbose.get(): print('Connection to Arduino closed')

    def update_ports(self):
        '''Updates list of available ports on button press'''

        ports_info = list(serial.tools.list_ports.comports())
        ports = [port.device for port in ports_info]
        ports_description = [port.description for port in ports_info]

        menu = self.option_ports['menu']
        menu.delete(0, 'end')
        if ports:
            for port, description in zip(ports, ports_description):
                menu.add_command(label=description, command=lambda com=port: self.port_var.set(com))
            self.port_var.set(ports[0])
        else:
            self.port_var.set('No ports found')

    def get_save_file(self):
        '''Opens prompt for file for data to be saved on button press'''

        save_file = tkFileDialog.asksaveasfilename(
            defaultextension='.h5',
            filetypes=[
                ('HDF5 file', '*.h5 *.hdf5'),
                ('All files', '*.*')
            ]
        )
        self.entry_file.delete(0, 'end')
        self.entry_file.insert(0, save_file)

    def start(self):
        '''Start session on button press'''

        self.gui_util('start')

        # Create data file
        if self.entry_file.get():
            try:
                # Create file if it doesn't already exist ('x' parameter)
                self.data_file = h5py.File(self.entry_save.get(), 'x')
            except IOError:
                tkMessageBox.showerror('File error', 'Could not create file to save data.')
                self.gui_util('stop')
                self.gui_util('open')
                self.gui_util('opened')
                return
        else:
            # Default file name
            if not os.path.exists('data'):
                os.makedirs('data')
            now = datetime.now()
            filename = 'data/data-' + now.strftime('%y%m%d-%H%M%S') + '.h5'
            self.data_file = h5py.File(filename, 'x')

        # Create HDF5 file
        n_trials = self.parameters['cs0_num'] + self.parameters['cs1_num']
        n_movement_frames = 2 * (n_trials * self.parameters['mean_iti'] + 
            self.parameters['pre_session'] + self.parameters['post_session']
            ) / self.parameters['track_period']

        # self.grp_cam = self.data_file.create_group('cam')
        # self.dset_ts = self.grp_cam.create_dataset('timestamps', dtype=float,
        #     shape=(int(nframes * 1.1), ), chunks=(1, ))
        # self.dset_cam = self.grp_cam.create_dataset('frames', dtype='uint8',
        #     shape=(int(nframes * 1.1), dy, dx), chunks=(1, dy, dx))
        # self.grp_cam.attrs['fps'] = fps
        # self.grp_cam.attrs['exposure'] = exposure_time
        # self.grp_cam.attrs['gain'] = self.var_gain.get()
        # self.grp_cam.attrs['vsub'] = self.var_vsub.get()
        # self.grp_cam.attrs['hsub'] = self.var_hsub.get()

        self.grp_behav = self.data_file.create_group('behavior')
        self.grp_behav.create_dataset(name='lick', dtype='uint32',
            shape=(2, n_movement_frames), chunks=(2, 1))
        self.grp_behav.create_dataset(name='movement', dtype='int32',
            shape=(2, n_movement_frames), chunks=(2, 1))
        self.grp_behav.create_dataset(name='trial_start', dtype='uint32',
            shape=(2, n_trials), chunks=(2, 1))
        self.grp_behav.create_dataset(name='trial_signal', dtype='uint32',
            shape=(2, n_trials), chunks=(2, 1))
        self.grp_behav.create_dataset(name='cs', dtype='uint32',
            shape=(2, n_trials), chunks=(2, 1))
        self.grp_behav.create_dataset(name='us', dtype='uint32',
            shape=(2, n_trials), chunks=(2, 1))
        self.grp_behav.create_dataset(name='response', dtype='uint32',
            shape=(2, n_trials), chunks=(2, 1))

        # Store session parameters into behavior group
        for key, value in self.parameters.iteritems():
            self.grp_behav.attrs[key] = value

        # if self.print_arduino.get():
        #     while self.ser.in_waiting:
        #         sys.stdout.write(arduino_head + self.ser.readline())
        # else:
        #     self.ser.flushInput()

        # Setup multithreading for serial scan and recording
        # for q in [self.q_serial, self.q_to_thread_rec, self.q_from_thread_rec]:
        for q in [self.q_serial, ]:
            with q.mutex:
                q.queue.clear()

        thread_scan = threading.Thread(
            target=scan_serial,
            args=(self.q_serial, self.ser, self.var_print_arduino.get())
        )

        # Reset things
        self.counter = {
            'lick': 0, 'movement': 0,
            'trial_start': 0, 'trial_signal':0, 'cs': 0, 'us': 0,
            'response': 0
        }

        # Start session
        self.ser.write('E')
        thread_scan.start()
        print('Session started at {}'.format(datetime.now().time()))

        # Update GUI
        self.update_session()

    def update_session(self):
        '''Update with incoming data
        Checks Queue for incoming data from arduino. Data arrives as comma-
        separated values with the first element defining the type of data. Data 
        on GUI is updated, and data is saved to HDF5 file.
        '''
        
        # Rate to update GUI; should be faster than incoming data
        refresh_rate = 10

        # Codes
        code_end = 0;
        code_lick = 1;
        code_movement = 2;
        code_trial_start = 3;
        code_trial_signal = 4;
        code_cs_start = 5;
        code_us_start = 6;
        code_response = 7;
        code_next_trial = 8;
        event = {
            code_lick: 'lick',
            code_movement: 'movement',
            code_trial_start: 'trial_start',
            code_trial_signal: 'trial_signal',
            code_cs_start: 'cs',
            code_us_start: 'us',
            code_response: 'response',
        }

        # End on "Stop" button (by user)
        if self.var_stop.get():
            self.var_stop.set(False)
            self.ser.write('0')
            print('User triggered stop, sending signal to Arduino...')

        # Watch incoming queue
        # Data has format: [code, ts, extra values]
        if not self.q_serial.empty():
            code, ts, data = self.q_serial.get()

            if code == code_end:
                arduino_end = ts
                # self.q_to_thread_rec.put(0)
                # while self.q_from_thread_rec.empty():
                #     pass
                print('Arduino ended, finalizing data...')
                self.stop_session(arduino_end=arduino_end)
                return
            
            # Record event
            if code < 8:
                self.grp_behav[event[code]][:, self.counter[event[code]]] = [ts, data]
                self.counter[event[code]] += 1

        self.parent.after(refresh_rate, self.update_session)

    def stop_session(self, arduino_end=None):
        '''Finalize session
        Closes hardware connections and saves HDF5 data file. Resets GUI.
        '''

        end_time = datetime.now().strftime("%H:%M:%S")
        print('Session ended at {}'.format(end_time))
        
        self.gui_util('stop')
        self.close_serial()
        # self.cam_close()

        print("Writing behavioral data")
        self.grp_behav.attrs['end_time'] = end_time
        self.grp_behav['lick'].resize((2, self.counter['lick']))
        self.grp_behav['movement'].resize((2, self.counter['movement']))
        self.grp_behav['trial_start'].resize((2, self.counter['trial_start']))
        self.grp_behav['trial_signal'].resize((2, self.counter['trial_signal']))
        self.grp_behav['cs'].resize((2, self.counter['cs']))
        self.grp_behav['us'].resize((2, self.counter['us']))
        self.grp_behav['response'].resize((2, self.counter['response']))
        self.grp_behav.attrs['notes'] = self.scrolled_notes.get(1.0, 'end')
        self.grp_behav.attrs['arduino_end'] = arduino_end

        # self.grp_cam.attrs['end_time'] = end_time
        # if frame_cutoff:
        #     print('Trimming recording')
        #     self.grp_cam['timestamps'].resize((frame_cutoff, ))
        #     _, dy, dx = self.grp_cam['frames'].shape
        #     self.grp_cam['frames'].resize((frame_cutoff, dy, dx))

        print('Closing {}'.format(self.data_file.filename))
        self.data_file.close()

        # Slack that session is done
        if self.entry_slack.get():
            slack_msg(self.entry_slack.get(), 'Session ended')
        print('All done!')


def slack_msg(slack_recipient, msg, test=False, verbose=False):
    '''Sends message through Slack
    Creates Slack message `msg` to `slack_recipient` from Bot.
    '''

    if not slack:
        print('No Slack client defined. Check environment variables.')
    else:
        bot_username = 'Go/no go bot'
        bot_icon = ':squirrel:'
        if test: msg='Test'

        try:
            slack.api_call(
              'chat.postMessage',
              username=bot_username,
              icon_emoji=bot_icon,
              channel=slack_recipient,
              text=msg
            )
        except:
            print('Unable to send Slack message')


# def scan_serial(q_serial, q_to_rec_thread, ser, print_arduino=False):
def scan_serial(q_serial, ser, print_arduino=False):
    '''Check serial for data
    Continually check serial connection for data sent from Arduino. Send data 
    through Queue to communicate with main GUI. Stop when `code_end` is 
    received from serial.
    '''

    code_end = 0

    while 1:
        input_arduino = ser.readline()
        if not input_arduino: continue

        if print_arduino: sys.stdout.write(arduino_head + input_arduino)

        try:
            input_split = map(int, input_arduino.split(','))
        except ValueError:
            # If not all comma-separated values are int castable
            pass
        else:
            if input_arduino: q_serial.put(input_split)
            if input_split[0] == code_end:
                # q_to_rec_thread.put(0)
                if print_arduino: print("  Scan complete.")
                return


def main():
    # GUI
    root = tk.Tk()
    root.wm_title("Go/no go")
    # default_font = tkFont.nametofont('TkDefaultFont')
    # default_font.configure(family='Arial')
    # root.option_add('*Font', default_font)
    InputManager(root)
    root.grid()
    root.mainloop()


if __name__ == '__main__':
    main()
