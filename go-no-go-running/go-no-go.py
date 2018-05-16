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


TODO:
- reset counter for responses
- CS names
- add graph of events
x add weights as dataset to day group
x scoreboard
x link variable to ttk.Entry's
x set up threads as daemons
x update button for parameters closes window

'''

import sys
is_py2 = sys.version[0] == '2'

import matplotlib
matplotlib.use('TKAgg')
if is_py2:
    import Tkinter as tk
    import ttk
    import tkFont
    import tkMessageBox
    import tkFileDialog
    from ScrolledText import ScrolledText
    from Queue import Queue
else:
    import tkinter as tk
    import tkinter.ttk as ttk
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
from datetime import datetime, timedelta
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
    print('Environment variable SLACK_API_TOKEN not identified or invalid')
    slack = None
else:
    slack = SlackClient(slack_token)

# Header to print with Arduino outputs
arduino_head = '  [a]: '

# Styling
opts_labelframe = {}

opts_entry = {
    # 'bg': 'white',
    # 'borderwidth': 0.5,
    # 'relief': 'flat',
}
opts_entry10 = dict(opts_entry, **{'width': 10, 'justify': 'right'})

opts_button = {}
opts_button_grid = {'padx': 2}

opts_sep = {'padx': 50, 'pady': 15, }
opts_frame0 = {'pady': 15, }
opts_frame1 = {'padx': 15, 'pady': 5, }
opts_frame2 = {'padx': 5, }

# Serial input codes
code_end = 0;
code_lick = 1;
code_lick_form = 9;
code_movement = 2;
code_trial_start = 3;
code_trial_signal = 4;
code_cs_start = 5;
code_us_start = 6;
code_response = 7;
code_next_trial = 8;

# Serial output codes
# Should do following as byte in decimal form...
# Except wouldn't be backward compatible...
code_vac_on = '1'       # bytes([49])
code_vac_off = '2'      # bytes([50])
code_vac_trig = '3'     # bytes([51])
code_sol0_on = '4'      # bytes([52])
code_sol0_off = '5'     # bytes([53])
code_sol0_trig = '6'    # bytes([54])
code_sol1_on = '7'      # bytes([55])
code_sol1_off = '8'     # bytes([56])
code_sol1_trig = '9'    # bytes([57])
code_sol2_on = ':'      # bytes([58])
code_sol2_off = ';'     # bytes([59])
code_sol2_trig = '<'    # bytes([60])
code_cs0 = '='          # bytes([61])
code_cs1 = '>'          # bytes([62])
code_cs2 = '?'          # bytes([63])

# Events to record
events = [
    'lick', 'lick_form', 'movement',
    'trial_start', 'trial_signal', 'cs', 'us',
    'response',
]


class InputManager(ttk.Frame):

    def __init__(self, parent):
        ttk.Frame.__init__(self, parent)

        # GUI layout
        # parent
        # - frame_setup
        #   + frame_cam
        #   + frame_debug
        #   + frame_params
        #     ~ frame_session_type
        #     ~ frame_session
        #     ~ frame_trial
        #   + frame_info
        #   + frame_file
        #   + hardware_frame
        #     ~ frame_preview
        #     ~ frame_cam
        #     ~ serial_frame
        #     ~ debug_frame
        #   + frame_start
        #   + slack_frame
        # - frame_monitor
        #   + frame_solenoid
        # 
        # parameters
        # - frame_gonogo
        # - frame_csus0
        # - frame_csus1
        # - frame_csus2
        # - frame_misc

        self.parent = parent
        parent.columnconfigure(0, weight=1)   # centers frame (also fills col, but that's automatic being the only row)

        # Variables
        self.var_presession = tk.IntVar()
        self.var_postsession = tk.IntVar()
        self.var_session_dur = tk.IntVar()
        self.var_cs0_num = tk.IntVar()
        self.var_cs1_num = tk.IntVar()
        self.var_cs2_num = tk.IntVar()
        self.var_presession = tk.IntVar()
        self.var_session_type = tk.IntVar()
        self.var_iti_distro = tk.IntVar()
        self.var_mean_iti = tk.IntVar()
        self.var_min_iti = tk.IntVar()
        self.var_max_iti = tk.IntVar()
        self.var_pre_stim = tk.IntVar()
        self.var_post_stim = tk.IntVar()
        self.var_cs0_dur = tk.IntVar()
        self.var_cs0_freq = tk.IntVar()
        self.var_cs0_pulse = tk.IntVar()
        self.var_cr0_min = tk.IntVar()
        self.var_cr0_max = tk.IntVar()
        self.var_cr0_dur = tk.IntVar()
        self.var_us0_delay = tk.IntVar()
        self.var_us0_dur = tk.IntVar()
        self.var_cs1_dur = tk.IntVar()
        self.var_cs1_freq = tk.IntVar()
        self.var_cs1_pulse = tk.IntVar()
        self.var_cr1_min = tk.IntVar()
        self.var_cr1_max = tk.IntVar()
        self.var_cr1_dur = tk.IntVar()
        self.var_us1_delay = tk.IntVar()
        self.var_us1_dur = tk.IntVar()
        self.var_cs2_dur = tk.IntVar()
        self.var_cs2_freq = tk.IntVar()
        self.var_cs2_pulse = tk.IntVar()
        self.var_cr2_min = tk.IntVar()
        self.var_cr2_max = tk.IntVar()
        self.var_cr2_dur = tk.IntVar()
        self.var_us2_delay = tk.IntVar()
        self.var_us2_dur = tk.IntVar()
        self.var_trial_signal_offset = tk.IntVar()
        self.var_trial_signal_dur = tk.IntVar()
        self.var_trial_signal_freq = tk.IntVar()
        self.var_grace_dur = tk.IntVar()
        self.var_response_dur = tk.IntVar()
        self.var_timeout_dur = tk.IntVar()
        self.var_consumption_dur = tk.IntVar()
        self.var_vac_dur = tk.IntVar()
        self.var_image_all = tk.IntVar()
        self.var_image_ttl_dur = tk.IntVar()
        self.var_track_period = tk.IntVar()
        self.var_use_cam = tk.BooleanVar()
        self.var_serial_status = tk.StringVar()
        self.var_verbose = tk.BooleanVar()
        self.var_print_arduino = tk.BooleanVar()
        self.var_suppress_print_lick_form = tk.BooleanVar()
        self.var_suppress_print_movement = tk.BooleanVar()
        self.var_subject = tk.StringVar()
        self.var_weight = tk.StringVar()
        self.var_file = tk.StringVar()
        self.var_slack_address = tk.StringVar()
        self.var_counter_lick = tk.IntVar()
        self.var_counter_lick_form = tk.IntVar()
        self.var_counter_lick_onset = tk.IntVar()
        self.var_counter_movement = tk.IntVar()
        self.var_counter_trial_start = tk.IntVar()
        self.var_counter_trial_signal = tk.IntVar()
        self.var_counter_cs = tk.IntVar()
        self.var_counter_cs0 = tk.IntVar()
        self.var_counter_cs1 = tk.IntVar()
        self.var_counter_cs2 = tk.IntVar()
        self.var_counter_cs0_responses = tk.IntVar()
        self.var_counter_cs1_responses = tk.IntVar()
        self.var_counter_cs2_responses = tk.IntVar()
        self.var_counter_us = tk.IntVar()
        self.var_next_trial_time = tk.StringVar()
        self.var_next_trial_type = tk.StringVar()

        # Default variable values
        self.var_presession.set(0)
        self.var_postsession.set(0)
        self.var_session_dur.set(1200000)
        self.var_cs0_num.set(100)
        self.var_cs1_num.set(0)
        self.var_cs2_num.set(0)
        self.var_session_type.set(0)
        self.var_iti_distro.set(1)
        self.var_mean_iti.set(8000)
        self.var_min_iti.set(8000)
        self.var_max_iti.set(12000)
        self.var_pre_stim.set(0)
        self.var_post_stim.set(8000)
        self.var_cs0_dur.set(2000)
        self.var_cs0_freq.set(6000)
        self.var_cs0_pulse.set(100)
        self.var_cr0_min.set(0)
        self.var_cr0_max.set(0)
        self.var_cr0_dur.set(0)
        self.var_us0_delay.set(3000)
        self.var_us0_dur.set(50)
        self.var_cs1_dur.set(2000)
        self.var_cs1_freq.set(6000)
        self.var_cs1_pulse.set(0)
        self.var_cr1_min.set(0)
        self.var_cr1_max.set(0)
        self.var_cr1_dur.set(0)
        self.var_us1_delay.set(3000)
        self.var_us1_dur.set(50)
        self.var_cs2_dur.set(2000)
        self.var_cs2_freq.set(12000)
        self.var_cs2_pulse.set(0)
        self.var_cr2_min.set(0)
        self.var_cr2_max.set(0)
        self.var_cr2_dur.set(0)
        self.var_us2_delay.set(3000)
        self.var_us2_dur.set(50)
        self.var_consumption_dur.set(0)
        self.var_vac_dur.set(25)
        self.var_trial_signal_offset.set(2000)
        self.var_trial_signal_dur.set(1000)
        self.var_trial_signal_freq.set(0)
        self.var_grace_dur.set(2000)
        self.var_response_dur.set(2000)
        self.var_timeout_dur.set(8000)
        self.var_image_all.set(0)
        self.var_image_ttl_dur.set(100)
        self.var_track_period.set(50)
        self.var_serial_status.set('Closed')
        self.var_next_trial_time.set('--')
        self.var_next_trial_type.set('--')
        self.var_counter_cs0.set(0)
        self.var_counter_cs1.set(0)
        self.var_counter_cs2.set(0)
        self.var_counter_lick_onset.set(0)

        # Lay out GUI

        ## Setup frame
        frame_setup = ttk.Frame(parent)
        frame_setup.grid(row=0, column=0, **opts_frame0)
        frame_setup_col0 = ttk.Frame(frame_setup)
        frame_setup_col1 = ttk.Frame(frame_setup)
        frame_setup_col2 = ttk.Frame(frame_setup)
        frame_setup_col0.grid(row=0, column=0, sticky='we')
        frame_setup_col1.grid(row=0, column=1, sticky='we')
        frame_setup_col2.grid(row=0, column=2, sticky='we')

        ### Session frame
        frame_params = ttk.Frame(frame_setup_col0)
        frame_params.grid(row=0, column=0, rowspan=3, **opts_frame1)
        frame_params.columnconfigure(0, weight=1)

        frame_session_type = ttk.Frame(frame_params)
        frame_session = ttk.Frame(frame_params)
        frame_trial_params = ttk.Frame(frame_params)
        frame_misc = ttk.Frame(frame_params)
        frame_session_type.grid(row=0, column=0, **opts_frame1)
        frame_session.grid(row=1, column=0, sticky='e', **opts_frame1)
        frame_trial_params.grid(row=2, column=0, sticky='we', **opts_frame1)
        frame_misc.grid(row=3, column=0, sticky='e', **opts_frame1)
        frame_session_type.columnconfigure(0, weight=1)
        frame_trial_params.columnconfigure(0, weight=1)

        ### Camera frame
        frame_cam = ttk.LabelFrame(frame_setup_col1, text='Camera', **opts_labelframe)
        frame_cam.grid(row=0, column=0, sticky='we', **opts_frame1)

        ### Arduino frame
        frame_arduino = ttk.LabelFrame(frame_setup_col1, text='Arduino', **opts_labelframe)
        frame_arduino.grid(row=1, column=0, sticky='we', **opts_frame1)
        frame_arduino1 = ttk.Frame(frame_arduino)
        frame_arduino2 = ttk.Frame(frame_arduino)
        frame_arduino1.grid(row=0, column=0, sticky='we', **opts_frame1)
        frame_arduino2.grid(row=1, column=0, sticky='we', **opts_frame1)
        frame_arduino1.grid_columnconfigure(0, weight=1)
        frame_arduino2.grid_columnconfigure(0, weight=1)
        frame_arduino2.grid_columnconfigure(1, weight=1)
        frame_arduino.grid_columnconfigure(0, weight=1)

        ### Debug frame
        frame_debug = ttk.LabelFrame(frame_setup_col1, text='Debug', **opts_labelframe)
        frame_debug.grid(row=2, column=0, sticky='we', **opts_frame1)
        frame_debug.grid_columnconfigure(0, weight=1)

        ### Info frame
        frame_info = ttk.Frame(frame_setup_col2)
        frame_info.grid(row=0, column=0, sticky='we', **opts_frame1)
        frame_info.grid_columnconfigure(0, weight=1)

        ### Saved file frame
        frame_file = ttk.Frame(frame_setup_col2)
        frame_file.grid(row=1, column=0, sticky='we', **opts_frame1)
        frame_file.grid_columnconfigure(0, weight=3)
        frame_file.grid_columnconfigure(1, weight=1)

        ### Slack frame
        frame_slack = ttk.Frame(frame_setup_col2)
        frame_slack.grid(row=2, column=0, sticky='we', **opts_frame1)
        frame_slack.grid_columnconfigure(0, weight=3)
        frame_slack.grid_columnconfigure(1, weight=1)

        ### Start-stop frame
        frame_start = ttk.Frame(frame_setup_col2)
        frame_start.grid(row=3, column=0, sticky='we', **opts_frame1)
        frame_start.grid_columnconfigure(0, weight=1)
        frame_start.grid_columnconfigure(1, weight=1)

        ## Separator
        ttk.Separator(parent).grid(row=1, column=0, sticky='we', **opts_sep)

        ## Monitor frame
        frame_monitor = ttk.Frame(parent)
        frame_monitor.grid(row=2, column=0, **opts_frame0)
        frame_monitor_col0 = ttk.Frame(frame_monitor)
        frame_monitor_col1 = ttk.Frame(frame_monitor)
        frame_monitor_col2 = ttk.Frame(frame_monitor)
        frame_monitor_col0.grid(row=0, column=0, sticky='we')
        frame_monitor_col1.grid(row=0, column=1, sticky='we')
        frame_monitor_col2.grid(row=0, column=2, sticky='we')
        frame_monitor_col2.grid_columnconfigure(0, weight=1)

        ### Solenoid frame
        frame_sol = ttk.Frame(frame_monitor_col0)
        frame_sol.grid(row=0, column=0, sticky='we', **opts_frame1)
        frame_sol.grid_columnconfigure(0, weight=1)  # Fills into frame

        ### CS frame
        frame_cs = ttk.Frame(frame_monitor_col1)
        frame_cs.grid(row=0, column=1, sticky='we', **opts_frame1)
        frame_cs.grid_columnconfigure(0, weight=1)

        ### Next trial frame
        frame_next = ttk.Frame(frame_monitor_col2)
        frame_next.grid(row=0, column=2, sticky='we', **opts_frame1)
        frame_next.grid_columnconfigure(0, weight=1)

        ### Counter
        frame_count = ttk.Frame(frame_monitor_col2)
        frame_count.grid(row=1, column=2, sticky='we', **opts_frame1)
        frame_count.grid_columnconfigure(0, weight=1)
        frame_count_row0 = ttk.Frame(frame_count)
        frame_count_row1 = ttk.Frame(frame_count)
        frame_count_row0.grid(row=0, column=0, sticky='we', pady=5)
        frame_count_row1.grid(row=1, column=0, sticky='we', pady=5)

        # Add GUI components

        ## frame_params
        ## Session parameters

        ### frame_session_type
        ### UI for choosing session type, ie, classical conditining vs go/no go.
        self.radio_freelicking = ttk.Radiobutton(frame_session_type, text='Free licking', variable=self.var_session_type, value=2, command=self.update_param_preview)
        self.radio_conditioning = ttk.Radiobutton(frame_session_type, text='Classical conditioning', variable=self.var_session_type, value=0, command=self.update_param_preview)
        self.radio_gonogo = ttk.Radiobutton(frame_session_type, text='Go/no go', variable=self.var_session_type, value=1, command=self.update_param_preview)
        self.radio_freelicking.grid(row=0, column=0, sticky='w')
        self.radio_conditioning.grid(row=1, column=0, sticky='w')
        self.radio_gonogo.grid(row=2, column=0, sticky='w')

        ### frame_session
        ### UI for session.
        self.entry_pre_session = ttk.Entry(frame_session, textvariable=self.var_presession, **opts_entry10)
        self.entry_post_session = ttk.Entry(frame_session, textvariable=self.var_postsession, **opts_entry10)
        self.entry_cs0_num = ttk.Entry(frame_session, textvariable=self.var_cs0_num, **opts_entry10)
        self.entry_cs1_num = ttk.Entry(frame_session, textvariable=self.var_cs1_num, **opts_entry10)
        self.entry_cs2_num = ttk.Entry(frame_session, textvariable=self.var_cs2_num, **opts_entry10)
        ttk.Label(frame_session, text='Presession time (ms): ', anchor='e').grid(row=0, column=0, sticky='e')
        ttk.Label(frame_session, text='Postsession time (ms): ', anchor='e').grid(row=1, column=0, sticky='e')
        ttk.Label(frame_session, text='Number of CS0: ', anchor='e').grid(row=2, column=0, sticky='e')
        ttk.Label(frame_session, text='Number of CS1: ', anchor='e').grid(row=3, column=0, sticky='e')
        ttk.Label(frame_session, text='Number of CS2: ', anchor='e').grid(row=4, column=0, sticky='e')
        self.entry_pre_session.grid(row=0, column=1, sticky='w')
        self.entry_post_session.grid(row=1, column=1, sticky='w')
        self.entry_cs0_num.grid(row=2, column=1, sticky='w')
        self.entry_cs1_num.grid(row=3, column=1, sticky='w')
        self.entry_cs2_num.grid(row=4, column=1, sticky='w')
        

        ### frame_trial_params
        ### UI for session parameters.
        self.button_params = ttk.Button(frame_trial_params, text='Parameters', command=self.set_params, **opts_button)
        self.text_params = tk.Text(frame_trial_params, width=50, height=10, font=('Arial', 8), relief='flat')
        self.button_params.grid(row=0, column=0, sticky='we', **opts_button_grid)
        self.text_params.grid(row=1, column=0, sticky='we')
        # self.text_params['state'] = 'disabled'

        ### frame_misc
        ### UI for other things.
        self.check_image_all = ttk.Checkbutton(frame_misc, variable=self.var_image_all)
        self.entry_image_ttl_dur = ttk.Entry(frame_misc, textvariable=self.var_image_ttl_dur, **opts_entry10)
        self.entry_track_period = ttk.Entry(frame_misc, textvariable=self.var_track_period, **opts_entry10)
        ttk.Label(frame_misc, text='Image everything: ', anchor='e').grid(row=0, column=0, sticky='e')
        ttk.Label(frame_misc, text='Imaging TTL duration (ms): ', anchor='e').grid(row=1, column=0, sticky='e')
        ttk.Label(frame_misc, text='Track period (ms): ', anchor='e').grid(row=2, column=0, sticky='e')
        self.check_image_all.grid(row=0, column=1, sticky='w')
        self.entry_image_ttl_dur.grid(row=1, column=1, sticky='w')
        self.entry_track_period.grid(row=2, column=1, sticky='w')

        ## frame_cam
        self.check_use_cam = ttk.Checkbutton(frame_cam, variable=self.var_use_cam, text='Use camera')
        self.check_use_cam.grid(row=0, column=0)
        # cam_x = 1280
        # cam_y = 1024
        # scale = 0.2
        # dpi = 300.
        # self.fig_preview = Figure(dpi=dpi, figsize=(cam_x / dpi * scale, cam_y / dpi * scale))
        # self.ax_preview = self.fig_preview.add_axes([0, 0, 1, 1])
        # self.fig_preview.subplots_adjust(left=0, bottom=0, right=1, top=1, wspace=0, hspace=0)
        # self.im = self.ax_preview.imshow(np.zeros((1024, 1280)), vmin=1, vmax=254, cmap='gray', interpolation='none')
        # self.ax_preview.axis('image')
        # self.ax_preview.axis('off')
        # self.canvas_preview = FigureCanvasTkAgg(self.fig_preview, frame_cam)
        # self.canvas_preview.show()
        # self.canvas_preview.draw()
        # self.canvas_preview.get_tk_widget().grid(row=0, column=0, sticky='wens')

        # ### Set high/low colors
        # self.im.cmap.set_under('b')
        # self.im.cmap.set_over('r')

        ## frame_arduino
        ## Arduino setup
        self.port_var = tk.StringVar()
        self.option_ports = ttk.OptionMenu(frame_arduino1, self.port_var, [])
        self.button_update_ports = ttk.Button(frame_arduino1, text='u', command=self.update_ports, **opts_button)
        self.button_open_port = ttk.Button(frame_arduino2, text='Open', command=self.open_serial, **opts_button)
        self.button_close_port = ttk.Button(frame_arduino2, text='Close', command=self.close_serial, **opts_button)
        tk.Label(frame_arduino1, text='Port: ').grid(row=0, column=0, sticky='e')
        tk.Label(frame_arduino1, text='State: ').grid(row=1, column=0, sticky='e')
        self.option_ports.grid(row=0, column=1, sticky='we', **opts_frame2)
        ttk.Entry(frame_arduino1, textvariable=self.var_serial_status, state='readonly', **opts_entry).grid(row=1, column=1, sticky='w', **opts_frame2)
        self.button_update_ports.grid(row=0, column=2, **opts_button_grid)
        self.button_open_port.grid(row=0, column=0, sticky='we', **opts_button_grid)
        self.button_close_port.grid(row=0, column=1, sticky='we', **opts_button_grid)

        icon_refresh = ImageTk.PhotoImage(file='graphics/refresh.png')
        self.button_update_ports.config(image=icon_refresh)
        self.button_update_ports.image = icon_refresh

        ## frame_debug
        ## UI for debugging options.
        self.check_verbose = ttk.Checkbutton(frame_debug, text='Verbose', variable=self.var_verbose)
        self.check_print_arduino = ttk.Checkbutton(frame_debug, text='Print Arduino serial', variable=self.var_print_arduino)
        self.check_suppress_print_lick_form = ttk.Checkbutton(frame_debug, text='Suppress lick output', variable=self.var_suppress_print_lick_form)
        self.check_suppress_print_movement = ttk.Checkbutton(frame_debug, text='Suppress movement output', variable=self.var_suppress_print_movement)
        self.check_verbose.grid(row=0, column=0, sticky='w')
        self.check_print_arduino.grid(row=1, column=0, sticky='w')
        self.check_suppress_print_lick_form.grid(row=2, column=0, sticky='w')
        self.check_suppress_print_movement.grid(row=3, column=0, sticky='w')

        ## frame_info
        ## UI for session info.
        self.entry_subject = ttk.Entry(frame_info, textvariable=self.var_subject, **opts_entry)
        self.entry_weight = ttk.Entry(frame_info, textvariable=self.var_weight, **opts_entry)
        self.scrolled_notes = ScrolledText(frame_info, width=20, height=15)
        tk.Label(frame_info, text='Subject: ').grid(row=0, column=0, sticky='e')
        tk.Label(frame_info, text='Weight: ').grid(row=1, column=0, sticky='e')
        tk.Label(frame_info, text='Notes: ').grid(row=2, column=0, columnspan=2, sticky='w')
        self.entry_subject.grid(row=0, column=1, sticky='w')
        self.entry_weight.grid(row=1, column=1, sticky='w')
        self.scrolled_notes.grid(row=3, column=0, columnspan=2, sticky='wens')

        ## frame_file
        ## UI for saved file.
        self.entry_file = ttk.Entry(frame_file, textvariable=self.var_file, **opts_entry)
        self.button_find_file = ttk.Button(frame_file, command=self.get_save_file, **opts_button)
        tk.Label(frame_file, text='File to save data:', anchor='w').grid(row=0, column=0, columnspan=2, sticky='w')
        self.entry_file.grid(row=1, column=0, sticky='wens')
        self.button_find_file.grid(row=1, column=1, sticky='e', **opts_button_grid)

        ### Add icon to folder
        icon_folder = ImageTk.PhotoImage(file='graphics/folder.png')
        self.button_find_file.config(image=icon_folder)
        self.button_find_file.image = icon_folder  #Keeping a reference to the image

        ## frame_slack
        ## UI for slack notifications.
        self.button_slack = ttk.Button(frame_slack, command=lambda: slack_msg(self.var_slack_address.get(), 'Test', test=True), **opts_button)
        tk.Label(frame_slack, text='Slack address: ', anchor='w').grid(row=0, column=0, columnspan=2, sticky='w')
        ttk.Entry(frame_slack, textvariable=self.var_slack_address, **opts_entry).grid(row=1, column=0, sticky='wens')
        self.button_slack.grid(row=1, column=1, sticky='e', **opts_button_grid)

        ### Add icon to folder
        icon_slack = ImageTk.PhotoImage(file='graphics/slack.png')
        self.button_slack.config(image=icon_slack)
        self.button_slack.image = icon_slack

        ## frame_start
        ## UI for starting and stopping session.
        self.var_stop = tk.BooleanVar()
        self.var_stop.set(False)
        self.button_start = ttk.Button(frame_start, text='Start', command=lambda: self.parent.after(0, self.start), **opts_button)
        self.button_stop = ttk.Button(frame_start, text='Stop', command=lambda: self.var_stop.set(True), **opts_button)
        self.button_start.grid(row=0, column=0, sticky='we', **opts_button_grid)
        self.button_stop.grid(row=0, column=1, sticky='we', **opts_button_grid)
        
        self.button_start['state'] = 'disabled'
        self.button_stop['state'] = 'disabled'

        ## frame_sol
        ## UI for controlling solenoids.
        self.button_vac_on = ttk.Button(frame_sol, text='|', width=3, command=lambda: ser_write(self.ser, code_vac_on), **opts_button)
        self.button_vac_off = ttk.Button(frame_sol, text=u'\u25EF', width=3, command=lambda: ser_write(self.ser, code_vac_off), **opts_button)
        self.button_vac_trig = ttk.Button(frame_sol, text=u'\u25B6', width=3, command=lambda: ser_write(self.ser, code_vac_trig), **opts_button)
        self.button_sol0_on = ttk.Button(frame_sol, text='|', width=3, command=lambda: ser_write(self.ser, code_sol0_on), **opts_button)
        self.button_sol0_off = ttk.Button(frame_sol, text=u'\u25EF', width=3, command=lambda: ser_write(self.ser, code_sol0_off), **opts_button)
        self.button_sol0_trig = ttk.Button(frame_sol, text=u'\u25B6', width=3, command=lambda: ser_write(self.ser, code_sol0_trig), **opts_button)
        self.button_sol1_on = ttk.Button(frame_sol, text='|', width=3, command=lambda: ser_write(self.ser, code_sol1_on), **opts_button)
        self.button_sol1_off = ttk.Button(frame_sol, text=u'\u25EF', width=3, command=lambda: ser_write(self.ser, code_sol1_off), **opts_button)
        self.button_sol1_trig = ttk.Button(frame_sol, text=u'\u25B6', width=3, command=lambda: ser_write(self.ser, code_sol1_trig), **opts_button)
        self.button_sol2_on = ttk.Button(frame_sol, text='|', width=3, command=lambda: ser_write(self.ser, code_sol2_on), **opts_button)
        self.button_sol2_off = ttk.Button(frame_sol, text=u'\u25EF', width=3, command=lambda: ser_write(self.ser, code_sol2_off), **opts_button)
        self.button_sol2_trig = ttk.Button(frame_sol, text=u'\u25B6', width=3, command=lambda: ser_write(self.ser, code_sol2_trig), **opts_button)
        tk.Label(frame_sol, text='On', anchor='center').grid(row=0, column=1, sticky='we')
        tk.Label(frame_sol, text='Off', anchor='center').grid(row=0, column=2, sticky='we')
        tk.Label(frame_sol, text='Trig', anchor='center').grid(row=0, column=3, sticky='we')
        tk.Label(frame_sol, text='Vacuum: ', anchor='e').grid(row=1, column=0, sticky='we')
        tk.Label(frame_sol, text='Solenoid 0: ', anchor='e').grid(row=2, column=0, sticky='we')
        tk.Label(frame_sol, text='Solenoid 1: ', anchor='e').grid(row=3, column=0, sticky='we')
        tk.Label(frame_sol, text='Solenoid 2: ', anchor='e').grid(row=4, column=0, sticky='we')
        self.button_vac_on.grid(row=1, column=1, sticky='we', **opts_button_grid)
        self.button_vac_off.grid(row=1, column=2, sticky='we', **opts_button_grid)
        self.button_vac_trig.grid(row=1, column=3, sticky='we', **opts_button_grid)
        self.button_sol0_on.grid(row=2, column=1, sticky='we', **opts_button_grid)
        self.button_sol0_off.grid(row=2, column=2, sticky='we', **opts_button_grid)
        self.button_sol0_trig.grid(row=2, column=3, sticky='we', **opts_button_grid)
        self.button_sol1_on.grid(row=3, column=1, sticky='we', **opts_button_grid)
        self.button_sol1_off.grid(row=3, column=2, sticky='we', **opts_button_grid)
        self.button_sol1_trig.grid(row=3, column=3, sticky='we', **opts_button_grid)
        self.button_sol2_on.grid(row=4, column=1, sticky='we', **opts_button_grid)
        self.button_sol2_off.grid(row=4, column=2, sticky='we', **opts_button_grid)
        self.button_sol2_trig.grid(row=4, column=3, sticky='we', **opts_button_grid)

        self.button_vac_on['state'] = 'disabled'
        self.button_vac_off['state'] = 'disabled'
        self.button_vac_trig['state'] = 'disabled'
        self.button_sol0_on['state'] = 'disabled'
        self.button_sol0_off['state'] = 'disabled'
        self.button_sol0_trig['state'] = 'disabled'
        self.button_sol1_on['state'] = 'disabled'
        self.button_sol1_off['state'] = 'disabled'
        self.button_sol1_trig['state'] = 'disabled'
        self.button_sol2_on['state'] = 'disabled'
        self.button_sol2_off['state'] = 'disabled'
        self.button_sol2_trig['state'] = 'disabled'

        # frame_cs
        self.button_cs0 = ttk.Button(frame_cs, text=u'\u25B6', width=3, command=lambda: ser_write(self.ser, code_cs0))
        self.button_cs1 = ttk.Button(frame_cs, text=u'\u25B6', width=3, command=lambda: ser_write(self.ser, code_cs1))
        self.button_cs2 = ttk.Button(frame_cs, text=u'\u25B6', width=3, command=lambda: ser_write(self.ser, code_cs2))
        tk.Label(frame_cs, text='Trig', anchor='center').grid(row=0, column=1, sticky='we')
        tk.Label(frame_cs, text='CS0: ', anchor='e').grid(row=2, column=0, sticky='we')
        tk.Label(frame_cs, text='CS1: ', anchor='e').grid(row=3, column=0, sticky='we')
        tk.Label(frame_cs, text='CS2: ', anchor='e').grid(row=4, column=0, sticky='we')
        self.button_cs0.grid(row=2, column=1, sticky='we', **opts_button_grid)
        self.button_cs1.grid(row=3, column=1, sticky='we', **opts_button_grid)
        self.button_cs2.grid(row=4, column=1, sticky='we', **opts_button_grid)
        tk.Button(frame_cs, relief='flat', state='disabled').grid(row=1, column=1, **opts_button_grid)

        self.button_cs0['state'] = 'disabled'
        self.button_cs1['state'] = 'disabled'
        self.button_cs2['state'] = 'disabled'

        # frame_next
        ttk.Label(frame_next, text='Next trial time: ').grid(row=0, column=0, sticky='e')
        ttk.Label(frame_next, text='Next trial type: ').grid(row=1, column=0, sticky='e')
        ttk.Entry(frame_next, textvariable=self.var_next_trial_time, state='readonly', **opts_entry10).grid(row=0, column=1)
        ttk.Entry(frame_next, textvariable=self.var_next_trial_type, state='readonly', **opts_entry10).grid(row=1, column=1)

        # frame_count
        ttk.Label(frame_count_row0, text='Count', anchor='center').grid(row=0, column=1, sticky='we')
        ttk.Label(frame_count_row0, text='Response', anchor='center').grid(row=0, column=2, sticky='we')
        ttk.Label(frame_count_row0, text='CS0: ', anchor='e').grid(row=1, column=0, sticky='e')
        ttk.Label(frame_count_row0, text='CS1: ', anchor='e').grid(row=2, column=0, sticky='e')
        ttk.Label(frame_count_row0, text='CS2: ', anchor='e').grid(row=3, column=0, sticky='e')
        ttk.Entry(frame_count_row0, textvariable=self.var_counter_cs0, state='readonly', **opts_entry10).grid(row=1, column=1, sticky='e')
        ttk.Entry(frame_count_row0, textvariable=self.var_counter_cs1, state='readonly', **opts_entry10).grid(row=2, column=1, sticky='e')
        ttk.Entry(frame_count_row0, textvariable=self.var_counter_cs2, state='readonly', **opts_entry10).grid(row=3, column=1, sticky='e')
        ttk.Entry(frame_count_row0, textvariable=self.var_counter_cs0_responses, state='readonly', **opts_entry10).grid(row=1, column=2, sticky='e')
        ttk.Entry(frame_count_row0, textvariable=self.var_counter_cs1_responses, state='readonly', **opts_entry10).grid(row=2, column=2, sticky='e')
        ttk.Entry(frame_count_row0, textvariable=self.var_counter_cs2_responses, state='readonly', **opts_entry10).grid(row=3, column=2, sticky='e')

        ttk.Label(frame_count_row1, text='Lick count: ', anchor='e').grid(row=4, column=0, sticky='e')
        ttk.Entry(frame_count_row1, textvariable=self.var_counter_lick_onset, state='readonly', **opts_entry10).grid(row=4, column=1, sticky='e')

        ## Group GUI objects
        self.obj_to_disable_at_open = [
            self.radio_conditioning,
            self.radio_gonogo,
            self.entry_pre_session,
            self.entry_post_session,
            self.entry_cs0_num,
            self.entry_cs1_num,
            self.entry_cs2_num,
            self.button_params,
            self.check_image_all,
            self.entry_image_ttl_dur,
            self.entry_track_period,
            self.option_ports,
            self.button_open_port,
            self.button_update_ports,
        ]
        self.obj_to_enable_when_open = [
            self.button_close_port,
            self.button_start,
            self.button_vac_on,
            self.button_vac_off,
            self.button_vac_trig,
            self.button_sol0_on,
            self.button_sol0_off,
            self.button_sol0_trig,
            self.button_sol1_on,
            self.button_sol1_off,
            self.button_sol1_trig,
            self.button_sol2_on,
            self.button_sol2_off,
            self.button_sol2_trig,
            self.button_cs0,
            self.button_cs1,
            self.button_cs2,
        ]
        self.obj_to_disable_at_start = [
            self.button_close_port,
            self.check_print_arduino,
            self.check_suppress_print_lick_form,
            self.check_suppress_print_movement,
            self.entry_subject,
            self.entry_weight,
            self.entry_file,
            self.button_find_file,
            self.button_slack,
            self.button_start,
            self.button_vac_on,
            self.button_vac_off,
            self.button_sol0_on,
            self.button_sol0_off,
            self.button_sol1_on,
            self.button_sol1_off,
            self.button_sol2_on,
            self.button_sol2_off,
            self.button_cs0,
            self.button_cs1,
            self.button_cs2,
        ]
        self.obj_to_enable_at_start = [
            self.button_stop,
        ]

        # Boolean of objects states at open
        # Useful if object states are volatile, but state should be returned 
        # once serial is closed.
        self.obj_enabled_at_open = [False] * len(self.obj_to_disable_at_open)

        # Finalize
        self.update_param_preview()
        self.parameters = collections.OrderedDict()
        self.ser = serial.Serial(timeout=1, baudrate=9600)
        self.update_ports()
        self.q_serial = Queue()
        self.counter = {
            ev: var_count
            for ev, var_count in zip(events, [
                self.var_counter_lick,
                self.var_counter_lick_form,
                self.var_counter_movement,
                self.var_counter_trial_start,
                self.var_counter_trial_signal,
                self.var_counter_cs,
                self.var_counter_us,
            ])
        }
        self.counter_gui = [
            self.var_counter_cs0,
            self.var_counter_cs1,
            self.var_counter_cs2,
            self.var_counter_cs0_responses,
            self.var_counter_cs1_responses,
            self.var_counter_cs2_responses,
            self.var_counter_lick_onset,
        ]

    def gui_util(self, option):
        '''Updates GUI components
        Enable and disable components based on events to prevent bad stuff.
        '''

        if option == 'open':
            for i, obj in enumerate(self.obj_to_disable_at_open):
                # Determine current state of object                
                self.obj_enabled_at_open[i] = False if obj['state'] == 'disabled' else True
                
                # Disable object
                obj['state'] = 'disabled'

            self.var_serial_status.set('Opening...')
        elif option == 'opened':
            # Enable start objects
            for obj in self.obj_to_enable_when_open:
                obj['state'] = 'normal'

            self.var_serial_status.set('Opened')
        elif option == 'close':
            for obj, to_enable in zip(self.obj_to_disable_at_open, self.obj_enabled_at_open):
                if to_enable: obj['state'] = 'normal'
            for obj in self.obj_to_enable_when_open:
                obj['state'] = 'disabled'

            self.var_serial_status.set('Closed')
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

            self.var_serial_status.set('Closed')

    def set_params(self):
        session_type = self.var_session_type.get()

        title_session = \
            'Go/no-go' if session_type == 1 else \
            'Classical conditioning' if session_type == 0 else \
            'Free licking'
        window_param = tk.Toplevel(self)
        window_param.wm_title('{} parameters'.format(title_session))
        window_param.grab_set()

        frame_trial = ttk.Frame(window_param)
        frame_csus = ttk.Frame(window_param)
        frame_vac = ttk.Frame(window_param)
        frame_update = ttk.Frame(window_param)
        frame_trial.grid(row=0, column=0, sticky='we', **opts_frame1)
        frame_csus.grid(row=1, column=0, sticky='we', **opts_frame1)
        frame_vac.grid(row=2, column=0, sticky='we', **opts_frame1)
        frame_update.grid(row=4, column=0, sticky='we', **opts_frame1)
        frame_trial.columnconfigure(0, weight=1)
        frame_csus.columnconfigure(0, weight=1)
        frame_vac.columnconfigure(0, weight=1)
        frame_update.columnconfigure(0, weight=1)

        frame_trial_col0 = ttk.Frame(frame_trial)
        frame_trial_col1 = ttk.Frame(frame_trial)
        frame_trial_col0.grid(row=0, column=0, sticky='we', **opts_frame1)
        frame_trial_col1.grid(row=0, column=1, sticky='we', **opts_frame1)

        frame_cs = ttk.Frame(frame_csus)
        frame_us = ttk.Frame(frame_csus)
        frame_cs.grid(row=0, column=0, sticky='we', **opts_frame1)
        frame_us.grid(row=0, column=1, sticky='we', **opts_frame1)

        if session_type in [0, 1]:
            # frame_trial
            # UI for trial.
            radio_fixed_iti = ttk.Radiobutton(frame_trial_col0, text='Fixed', variable=self.var_iti_distro, value=0)
            radio_uniform_iti = ttk.Radiobutton(frame_trial_col0, text='Uniform distro', variable=self.var_iti_distro, value=1)
            radio_expo_iti = ttk.Radiobutton(frame_trial_col0, text='Exponential distro', variable=self.var_iti_distro, value=2)
            tk.Label(frame_trial_col0, text='ITI variability').grid(row=0, column=0, sticky='w')
            radio_fixed_iti.grid(row=1, column=0, sticky='w')
            radio_uniform_iti.grid(row=2, column=0, sticky='w')
            radio_expo_iti.grid(row=3, column=0, sticky='w')

            self.entry_mean_iti = ttk.Entry(frame_trial_col1, textvariable=self.var_mean_iti, **opts_entry10)
            self.entry_min_iti = ttk.Entry(frame_trial_col1, textvariable=self.var_min_iti, **opts_entry10)
            self.entry_max_iti = ttk.Entry(frame_trial_col1, textvariable=self.var_max_iti, **opts_entry10)
            self.entry_pre_stim = ttk.Entry(frame_trial_col1, textvariable=self.var_pre_stim, **opts_entry10)
            self.entry_post_stim = ttk.Entry(frame_trial_col1, textvariable=self.var_post_stim, **opts_entry10)
            tk.Label(frame_trial_col1, text='Mean ITI (ms): ', anchor='e').grid(row=3, column=0, sticky='e')
            tk.Label(frame_trial_col1, text='Min ITI (ms): ', anchor='e').grid(row=4, column=0, sticky='e')
            tk.Label(frame_trial_col1, text='Max ITI (ms): ', anchor='e').grid(row=5, column=0, sticky='e')
            tk.Label(frame_trial_col1, text='Prestim time (ms): ', anchor='e').grid(row=6, column=0, sticky='e')
            tk.Label(frame_trial_col1, text='Poststim time (ms): ', anchor='e').grid(row=7, column=0, sticky='e')
            self.entry_mean_iti.grid(row=3, column=1, sticky='w')
            self.entry_min_iti.grid(row=4, column=1, sticky='w')
            self.entry_max_iti.grid(row=5, column=1, sticky='w')
            self.entry_pre_stim.grid(row=6, column=1, sticky='w')
            self.entry_post_stim.grid(row=7, column=1, sticky='w')

            # frame_csus
            # UI for CS-US
            self.entry_cs0_dur = ttk.Entry(frame_cs, textvariable=self.var_cs0_dur, **opts_entry10)
            self.entry_cs0_freq = ttk.Entry(frame_cs, textvariable=self.var_cs0_freq, **opts_entry10)
            self.entry_cs0_pulse = ttk.Entry(frame_cs, textvariable=self.var_cs0_pulse, **opts_entry10)
            self.entry_cs1_dur = ttk.Entry(frame_cs, textvariable=self.var_cs1_dur, **opts_entry10)
            self.entry_cs1_freq = ttk.Entry(frame_cs, textvariable=self.var_cs1_freq, **opts_entry10)
            self.entry_cs1_pulse = ttk.Entry(frame_cs, textvariable=self.var_cs1_pulse, **opts_entry10)
            tk.Label(frame_cs, text='t (ms)', anchor='center').grid(row=0, column=1, sticky='we')
            tk.Label(frame_cs, text='f (s' u'\u207b\u00b9' ')', anchor='center').grid(row=0, column=2, sticky='we')
            tk.Label(frame_cs, text='pulse (ms)', anchor='center').grid(row=0, column=3, sticky='we')
            tk.Label(frame_cs, text='CS0: ', anchor='e').grid(row=1, column=0, sticky='e')
            tk.Label(frame_cs, text='CS1: ', anchor='e').grid(row=2, column=0, sticky='e')
            self.entry_cs0_dur.grid(row=1, column=1, sticky='w')
            self.entry_cs0_freq.grid(row=1, column=2, sticky='w')
            self.entry_cs0_pulse.grid(row=1, column=3, sticky='w')
            self.entry_cs1_dur.grid(row=2, column=1, sticky='w')
            self.entry_cs1_freq.grid(row=2, column=2, sticky='w')
            self.entry_cs1_pulse.grid(row=2, column=3, sticky='w')

            self.entry_us0_dur = ttk.Entry(frame_us, textvariable=self.var_us0_dur, **opts_entry10)
            self.entry_us1_dur = ttk.Entry(frame_us, textvariable=self.var_us1_dur, **opts_entry10)
            tk.Label(frame_us, text='t (ms)', anchor='center').grid(row=0, column=1, sticky='we')
            tk.Label(frame_us, text='US0: ', anchor='e').grid(row=1, column=0, sticky='e')
            tk.Label(frame_us, text='US1: ', anchor='e').grid(row=2, column=0, sticky='e')
            self.entry_us0_dur.grid(row=1, column=1, sticky='w')
            self.entry_us1_dur.grid(row=2, column=1, sticky='w')

            # frame_vac
            # UI for vacuum.
            self.entry_consumption_dur = ttk.Entry(frame_vac, textvariable=self.var_consumption_dur, **opts_entry10)
            self.entry_vac_dur = ttk.Entry(frame_vac, textvariable=self.var_vac_dur, **opts_entry10)
            tk.Label(frame_vac, text='Consumption time limit (ms): ', anchor='e').grid(row=0, column=0, sticky='e')
            tk.Label(frame_vac, text='Vacuum duration (ms): ', anchor='e').grid(row=1, column=0, sticky='e')
            self.entry_consumption_dur.grid(row=0, column=1, sticky='w')
            self.entry_vac_dur.grid(row=1, column=1, sticky='w')

        # frame_update
        # UI for 'Update' button
        button_update = ttk.Button(frame_update, text='Update', command=lambda: [self.update_param_preview(), window_param.destroy()], **opts_button)
        button_update.grid(row=0, column=0, **opts_button_grid)

        if session_type == 0:
            # Classical conditioning

            frame_csus2 = ttk.Frame(window_param)
            frame_csus2.grid(row=3, column=0, sticky='e', **opts_frame1)
            
            self.entry_cs2_dur = ttk.Entry(frame_cs, textvariable=self.var_cs2_dur, **opts_entry10)
            self.entry_cs2_freq = ttk.Entry(frame_cs, textvariable=self.var_cs2_freq, **opts_entry10)
            self.entry_cs2_pulse = ttk.Entry(frame_cs, textvariable=self.var_cs2_pulse, **opts_entry10)
            tk.Label(frame_cs, text='CS2: ', anchor='e').grid(row=3, column=0, sticky='e')
            self.entry_cs2_dur.grid(row=3, column=1, sticky='w')
            self.entry_cs2_freq.grid(row=3, column=2, sticky='w')
            self.entry_cs2_pulse.grid(row=3, column=3, sticky='w')

            self.entry_us2_dur = ttk.Entry(frame_us, textvariable=self.var_us2_dur, **opts_entry10)
            self.entry_us0_delay = ttk.Entry(frame_us, textvariable=self.var_us0_delay, **opts_entry10)
            self.entry_us1_delay = ttk.Entry(frame_us, textvariable=self.var_us1_delay, **opts_entry10)
            self.entry_us2_delay = ttk.Entry(frame_us, textvariable=self.var_us2_delay, **opts_entry10)
            tk.Label(frame_us, text='US2: ', anchor='e').grid(row=3, column=0, sticky='e')
            tk.Label(frame_us, text='Delay (ms)', anchor='e').grid(row=0, column=2, sticky='e')
            self.entry_us2_dur.grid(row=3, column=1, sticky='w')
            self.entry_us0_delay.grid(row=1, column=2, sticky='w')
            self.entry_us1_delay.grid(row=2, column=2, sticky='w')
            self.entry_us2_delay.grid(row=3, column=2, sticky='w')
            
        elif session_type == 1:
            # Go/no-go

            frame_gonogo = ttk.Frame(window_param)
            frame_gonogo.grid(row=3, column=0, sticky='e', **opts_frame1)

            ### frame_gonogo
            ### UI for trial start (signal)
            self.entry_trial_signal_offset = ttk.Entry(frame_gonogo, textvariable=self.var_trial_signal_offset, **opts_entry10)
            self.entry_trial_signal_dur = ttk.Entry(frame_gonogo, textvariable=self.var_trial_signal_dur, **opts_entry10)
            self.entry_trial_signal_freq = ttk.Entry(frame_gonogo, textvariable=self.var_trial_signal_freq, **opts_entry10)
            self.entry_grace_dur = ttk.Entry(frame_gonogo, textvariable=self.var_grace_dur, **opts_entry10)
            self.entry_response_dur = ttk.Entry(frame_gonogo, textvariable=self.var_response_dur, **opts_entry10)
            self.entry_timeout_dur = ttk.Entry(frame_gonogo, textvariable=self.var_timeout_dur, **opts_entry10)
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

        elif session_type == 2:
            self.entry_session_dur = ttk.Entry(frame_trial, textvariable=self.var_session_dur, **opts_entry10)
            tk.Label(frame_trial, text='Session duration (ms): ', anchor='e').grid(row=0, column=0, sticky='e')
            self.entry_session_dur.grid(row=0, column=1, sticky='w')

            self.entry_us0_dur = ttk.Entry(frame_us, textvariable=self.var_us0_dur, **opts_entry10)
            tk.Label(frame_us, text='US0 duration (ms): ', anchor='e').grid(row=0, column=0, sticky='e')
            self.entry_us0_dur.grid(row=0, column=1, sticky='w')

    def update_param_preview(self):
        session_type = self.var_session_type.get()
        iti_type = self.var_iti_distro.get()

        if iti_type == 0:
            summary_iti = 'ITI: {}'.format(self.var_mean_iti.get())
        elif iti_type == 1:
            summary_iti = 'ITI: {} (min), {} (max)'.format(
                self.var_min_iti.get(), self.var_max_iti.get()
            )
        elif iti_type == 2:
            summary_iti = 'ITI: {} (mean), {} (min), {} (max)'.format(
                self.var_mean_iti.get(), self.var_min_iti.get(), self.var_max_iti.get()
            )

        if session_type == 2:
            # Free licking
            summary_session = 'Session will last for {} ms (plus pre-/postsession)'.format(
                self.var_session_dur.get(),
            )
            summary_us = 'US0: {}-ms delivery after lick'.format(
                self.var_us0_dur.get()
            )
            summary_notes = 'CS parameters not used\nNo trials (be aware for imaging)'
            summary = '{}\n{}\n{}'.format(
                summary_session,
                summary_us,
                summary_notes,
            )

        if session_type == 0:
            # Classical conditioning
            summary_cs0 = 'CS0: {}-ms, {}-Hz cue'.format(
                self.var_cs0_dur.get(), self.var_cs0_freq.get()
            )
            summary_us0 = 'US0: {}-ms delivery after {}-ms delay'.format(
                self.var_us0_dur.get(), self.var_us0_delay.get()
            )
            summary_csus1 = 'CS1: {}-ms, {}-Hz cue'.format(
                self.var_cs1_dur.get(), self.var_cs1_freq.get()
            )
            summary_us1 = 'US1: {}-ms delivery after {}-ms delay'.format(
                self.var_us1_dur.get(), self.var_us1_delay.get()
            )
            summary_csus2 = 'CS2: {}-ms, {}-Hz cue'.format(
                self.var_cs2_dur.get(), self.var_cs2_freq.get()
            )
            summary_us2 = 'US2: {}-ms delivery after {}-ms delay'.format(
                self.var_us2_dur.get(), self.var_us2_delay.get()
            )
            summary = '{}\n{}\n{}\n{}\n{}\n{}\n{}'.format(
                summary_iti,
                summary_cs0, summary_us0,
                summary_csus1, summary_us1,
                summary_csus2, summary_us2
            )

        elif session_type == 1:
            # Go/no-go
            summary_gonogo0 = 'Trial start: {}-ms, {}-Hz cue {} ms before go/no-go signal'.format(
                self.var_trial_signal_dur.get(), self.var_trial_signal_freq.get(), self.var_trial_signal_offset.get()
            )
            summary_gonogo1 = 'Go (CS0): {}-ms, {}-Hz cue'.format(
                self.var_cs0_dur.get(), self.var_cs0_freq.get()
            )
            summary_gonogo2 = 'Go (US0): {} ms'.format(self.var_us0_dur.get())
            summary_gonogo3 = 'No-go (CS1): {}-ms, {}-Hz cue'.format(
                self.var_cs1_dur.get(), self.var_cs1_freq.get()
            )
            summary_gonogo4 = 'Go (US1): {} ms'.format(self.var_us1_dur.get())
            summary_gonogo5 = '{}-ms grace, {}-ms response window, {}-ms timeout'.format(
                self.var_grace_dur.get(), self.var_response_dur.get(), self.var_timeout_dur.get()
            )
            summary = '{}\n{}\n{}\n{}\n{}\n{}\n{}'.format(
                summary_iti, summary_gonogo0, summary_gonogo1, summary_gonogo2, summary_gonogo3, summary_gonogo4, summary_gonogo5
            )

        if session_type in {0, 1}:
            summary += '\nUS will be removed after {} ms'.format(self.var_consumption_dur.get())

        self.text_params.delete(0.0, 'end')
        self.text_params.insert(0.0, summary)

    def open_serial(self, delay=3, timeout=5, code_params='D'):
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
            err_msg = err.args                                           # Could be done bettter...
            tkMessageBox.showerror('Serial error', err_msg)
            print('Serial error: {}'.format(err_msg))
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
                sys.stdout.write(arduino_head + ser_readline(self.ser))
        else:
            self.ser.flushInput()

        # Define parameters
        # NOTE: Order is important here since this order is preserved when 
        # sending via serial.
        self.parameters = collections.OrderedDict()   # Clear self.parameters (maybe not necessary)

        self.parameters['session_type'] = self.var_session_type.get()
        self.parameters['pre_session'] = self.var_presession.get()
        self.parameters['post_session'] = self.var_postsession.get()
        self.parameters['session_dur'] = self.var_session_dur.get()
        self.parameters['cs0_num'] = self.var_cs0_num.get()
        self.parameters['cs1_num'] = self.var_cs1_num.get()
        self.parameters['cs2_num'] = self.var_cs2_num.get()
        self.parameters['iti_distro'] = self.var_iti_distro.get()
        self.parameters['mean_iti'] = self.var_mean_iti.get()
        self.parameters['min_iti'] = self.var_min_iti.get()
        self.parameters['max_iti'] = self.var_max_iti.get()
        self.parameters['pre_stim'] = self.var_pre_stim.get()
        self.parameters['post_stim'] = self.var_post_stim.get()
        self.parameters['cs0_dur'] = self.var_cs0_dur.get()
        self.parameters['cs0_freq'] = self.var_cs0_freq.get()
        self.parameters['cs0_pulse'] = self.var_cs0_pulse.get()
        self.parameters['cr0_min'] = self.var_cr0_min.get()
        self.parameters['cr0_max'] = self.var_cr0_max.get()
        self.parameters['cr0_dur'] = self.var_cr0_dur.get()
        self.parameters['us0_dur'] = self.var_us0_dur.get()
        self.parameters['us0_delay'] = self.var_us0_delay.get()
        self.parameters['cs1_dur'] = self.var_cs1_dur.get()
        self.parameters['cs1_freq'] = self.var_cs1_freq.get()
        self.parameters['cs1_pulse'] = self.var_cs1_pulse.get()
        self.parameters['cs1_dur'] = self.var_cs1_dur.get()
        self.parameters['cs1_freq'] = self.var_cs1_freq.get()
        self.parameters['cs1_pulse'] = self.var_cs1_pulse.get()
        self.parameters['us1_dur'] = self.var_us1_dur.get()
        self.parameters['us1_delay'] = self.var_us1_delay.get()
        self.parameters['cs2_dur'] = self.var_cs2_dur.get()
        self.parameters['cs2_freq'] = self.var_cs2_freq.get()
        self.parameters['cs2_pulse'] = self.var_cs2_pulse.get()
        self.parameters['cs2_dur'] = self.var_cs2_dur.get()
        self.parameters['cs2_freq'] = self.var_cs2_freq.get()
        self.parameters['cs2_pulse'] = self.var_cs2_pulse.get()
        self.parameters['us2_dur'] = self.var_us2_dur.get()
        self.parameters['us2_delay'] = self.var_us2_delay.get()
        self.parameters['consumption_dur'] = self.var_consumption_dur.get()
        self.parameters['vac_dur'] = self.var_vac_dur.get()
        self.parameters['trial_signal_offset'] = self.var_trial_signal_offset.get()
        self.parameters['trial_signal_dur'] = self.var_trial_signal_dur.get()
        self.parameters['trial_signal_freq'] = self.var_trial_signal_freq.get()
        self.parameters['grace_dur'] = self.var_grace_dur.get()
        self.parameters['response_dur'] = self.var_response_dur.get()
        self.parameters['timeout_dur'] = self.var_timeout_dur.get()
        self.parameters['image_all'] = self.var_image_all.get()
        self.parameters['image_ttl_dur'] = self.var_image_ttl_dur.get()
        self.parameters['track_period'] = self.var_track_period.get()
        
        # Send parameters and make sure it's processed
        values = self.parameters.values()
        if self.var_verbose.get(): print('Sending parameters: {}'.format(values))
        ser_write(self.ser, code_params + '+'.join(str(s) for s in values))

        start_time = time.time()
        while 1:
            if self.ser.in_waiting:
                if self.var_print_arduino.get():
                    # Print incoming data
                    while self.ser.in_waiting:
                        sys.stdout.write(arduino_head + ser_readline(self.ser))
                print('Parameters uploaded to Arduino')
                print('Ready to start')
                return
            elif time.time() >= start_time + timeout:
                print('Error sending parameters to Arduino')
                print('Uploading timed out. Start signal not found. Make sure Arduino is configured.')
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
            initialdir=self.var_file.get(),
            defaultextension='.h5',
            filetypes=[
                ('HDF5 file', '*.h5 *.hdf5'),
                ('All files', '*.*')
            ]
        )
        self.var_file.set(save_file)

    def start(self, code_start='E'):
        '''Start session on button press'''

        self.gui_util('start')

        # Create data file
        if self.var_file.get():
            try:
                # Create file if it doesn't already exist, append otherwise ('a' parameter)
                self.data_file = h5py.File(self.var_file.get(), 'a')
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

        # Create group for experiment
        # Append to existing file (if applicable). If group already exists, append number to name.
        date = str(datetime.now().date())
        subj = self.var_subject.get() or '?'
        index = 0
        file_index = ''
        while True:
            try:
                self.grp_exp = self.data_file.create_group('{}/{}'.format(subj, date + file_index))
            except (RuntimeError, ValueError):
                index += 1
                file_index = '-' + str(index)
            else:
                break
        self.grp_exp['weight'] = self.var_weight.get()

        # Initialize datasets
        n_trials = self.parameters['cs0_num'] + self.parameters['cs1_num'] + self.parameters['cs2_num']
        if n_trials:
            session_time = n_trials * self.parameters['mean_iti']
        else:
            n_trials = 1   # in order for chunk to work dataset needs to be bigger than chunk size
            session_time = self.var_session_dur.get()
        n_movement_frames = 2 * (session_time + self.parameters['pre_session'] + self.parameters['post_session']
            ) / self.parameters['track_period']
        if not n_movement_frames: n_movement_frames = 1 # same reason for n_trial = 1 above
        chunk_size = (2, 1)

        self.grp_behav = self.grp_exp.create_group('behavior')
        self.grp_behav.create_dataset(name='lick', dtype='uint32', shape=(2, n_movement_frames), chunks=chunk_size)
        self.grp_behav.create_dataset(name='lick_form', dtype='uint32', shape=(2, n_movement_frames), chunks=chunk_size)
        self.grp_behav.create_dataset(name='movement', dtype='int32', shape=(2, n_movement_frames), chunks=chunk_size)
        self.grp_behav.create_dataset(name='trial_start', dtype='uint32', shape=(2, n_trials), chunks=chunk_size)
        self.grp_behav.create_dataset(name='trial_signal', dtype='uint32', shape=(2, n_trials), chunks=chunk_size)
        self.grp_behav.create_dataset(name='cs', dtype='uint32', shape=(2, n_trials), chunks=chunk_size)
        self.grp_behav.create_dataset(name='us', dtype='uint32', shape=(2, n_movement_frames), chunks=chunk_size)
        self.grp_behav.create_dataset(name='response', dtype='uint32', shape=(2, n_trials), chunks=chunk_size)

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

        # Store session parameters into behavior group
        for key, value in self.parameters.items():
            self.grp_behav.attrs[key] = value

        # Setup multithreading for serial scan and recording
        for q in [self.q_serial, ]:
            with q.mutex:
                q.queue.clear()

        suppress = [
            code_lick_form if self.var_suppress_print_lick_form.get() else None,
            code_movement if self.var_suppress_print_movement.get() else None
        ]
        thread_scan = threading.Thread(
            target=scan_serial,
            args=(self.q_serial, self.ser, self.var_print_arduino.get(), suppress),
        )
        thread_scan.daemon = True

        # Reset counters
        # self.counter = {ev: 0 for ev in events}
        for counter in self.counter.values(): counter.set(0)
        for counter_gui in self.counter_gui: counter_gui.set(0)

        # Start session
        ser_write(self.ser, code_start)
        thread_scan.start()
        self.start_time = datetime.now()
        print('Session started at {}'.format(self.start_time))
        self.grp_exp.attrs['start_time'] = str(self.start_time)

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

        # Code-event dictionary
        event = {
            code_lick: 'lick',
            code_lick_form: 'lick_form',
            code_movement: 'movement',
            code_trial_start: 'trial_start',
            code_trial_signal: 'trial_signal',
            code_cs_start: 'cs',
            code_us_start: 'us',
            code_response: 'response',
        }

        # End on 'Stop' button (by user)
        if self.var_stop.get():
            self.var_stop.set(False)
            ser_write(self.ser, '0')
            print('User triggered stop, sending signal to Arduino...')

        # Watch incoming queue
        # Data has format: [code, ts, extra values]
        # Empty queue before leaving. Otherwise, a backlog will grow.
        while not self.q_serial.empty():
            code, ts, data = self.q_serial.get()

            # End session
            if code == code_end:
                arduino_end = ts
                # self.q_to_thread_rec.put(0)
                # while self.q_from_thread_rec.empty():
                #     pass
                print('Arduino ended, finalizing data...')
                self.stop_session(arduino_end=arduino_end)
                return

            # Record event
            if code not in [code_next_trial]:
                self.grp_behav[event[code]][:, self.counter[event[code]].get()] = [ts, data]
                self.counter[event[code]].set(self.counter[event[code]].get() + 1)

            # Update GUI
            if code == code_lick:
                if data == 1:
                    self.var_counter_lick_onset.set(self.var_counter_lick_onset.get() + 1)
            elif code == code_cs_start:
                if data == 0:
                    self.var_counter_cs0.set(self.var_counter_cs0.get() + 1)
                elif data == 1:
                    self.var_counter_cs1.set(self.var_counter_cs1.get() + 1)
                elif data == 2:
                    self.var_counter_cs2.set(self.var_counter_cs2.get() + 1)
            elif code == code_response:
                if data == 1:
                    self.var_counter_cs0_responses.set(self.var_counter_cs0_responses.get() + 1)
                if data == 3:
                    self.var_counter_cs1_responses.set(self.var_counter_cs1_responses.get() + 1)
                if data == 5:
                    self.var_counter_cs2_responses.set(self.var_counter_cs2_responses.get() + 1)
            elif code == code_next_trial:
                self.var_next_trial_time.set((self.start_time + timedelta(milliseconds=ts)).strftime('%H:%M:%S'))
                self.var_next_trial_type.set(data)

        self.parent.after(refresh_rate, self.update_session)

    def stop_session(self, arduino_end=None):
        '''Finalize session
        Closes hardware connections and saves HDF5 data file. Resets GUI.
        '''

        end_time = datetime.now().strftime('%H:%M:%S')
        print('Session ended at {}'.format(end_time))
        
        self.gui_util('stop')
        self.close_serial()
        # self.cam_close()

        print('Writing behavioral data into HDF5 group {}'.format(self.grp_exp.name))
        self.grp_behav.attrs['end_time'] = end_time
        self.grp_behav.attrs['notes'] = self.scrolled_notes.get(1.0, 'end')
        self.grp_behav.attrs['arduino_end'] = arduino_end
        for ev in events:
            self.grp_behav[ev].resize((2, self.counter[ev].get()))

        # self.grp_cam.attrs['end_time'] = end_time
        # if frame_cutoff:
        #     print('Trimming recording')
        #     self.grp_cam['timestamps'].resize((frame_cutoff, ))
        #     _, dy, dx = self.grp_cam['frames'].shape
        #     self.grp_cam['frames'].resize((frame_cutoff, dy, dx))

        print('Closing {}'.format(self.data_file.filename))
        self.data_file.close()

        # Slack that session is done
        if self.var_slack_address.get():
            slack_msg(self.var_slack_address.get(), 'Session ended')
        print('All done!')


def ser_write(ser, code):
    if not is_py2:
        if type(code) is not bytes: code = code.encode()
    ser.write(code)


def ser_readline(ser):
    if is_py2:
        return ser.readline()
    else:
        return ser.readline().decode()


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
def scan_serial(q_serial, ser, print_arduino=False, suppress=[]):
    '''Check serial for data
    Continually check serial connection for data sent from Arduino. Send data 
    through Queue to communicate with main GUI. Stop when `code_end` is 
    received from serial.
    '''

    while 1:
        input_arduino = ser_readline(ser)
        if not input_arduino: continue

        try:
            input_split = [int(x) for x in input_arduino.split(',')]
        except ValueError:
            # If not all comma-separated values are int castable
            if print_arduino: sys.stdout.write(arduino_head + input_arduino)
        else:
            if print_arduino and input_split[0] not in suppress:
                # Only print from serial if code is not in list of codes to suppress
                sys.stdout.write(arduino_head + input_arduino)
            if input_arduino: q_serial.put(input_split)
            if input_split[0] == code_end:
                # q_to_rec_thread.put(0)
                if print_arduino: print('  Scan complete.')
                return


def main():
    # GUI
    root = tk.Tk()
    root.wm_title('Go/no go & classical conditioning')
    # default_font = tkFont.nametofont('TkDefaultFont')
    # default_font.configure(family='Arial')
    # root.option_add('*Font', default_font)
    InputManager(root)
    root.grid()
    root.mainloop()


if __name__ == '__main__':
    main()
