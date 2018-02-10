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
- pulsing tone
- trigger CS
- CS names

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
    print('Environment variable SLACK_API_TOKEN not identified or invalid')
    slack = None
else:
    slack = SlackClient(slack_token)

# Header to print with Arduino outputs
arduino_head = '  [a]: '

entry_width = 10
opts_entry = {
    'width': 10,
    'justify': 'right',
    'bg': 'white',
    'borderwidth': 0.5,
}
ew = 10  # Width of Entry UI
pX = 50
pY = 15
px = 15
py = 5
px1 = 5
py1 = 2

# Serial codes
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

# Should do following as byte in decimal form...
code_vac_on = '1'
code_vac_off = '2'
code_vac_trig = '3'
code_sol0_on = '4'
code_sol0_off = '5'
code_sol0_trig = '6'
code_sol1_on = '7'
code_sol1_off = '8'
code_sol1_trig = '9'
code_sol2_on = ':'
code_sol2_off = ';'
code_sol2_trig = '<'

# Events to record
events = [
    'lick', 'lick_form', 'movement',
    'trial_start', 'trial_signal', 'cs', 'us',
    'response',
]


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
        self.var_session_type = tk.IntVar()
        self.var_iti_distro = tk.IntVar()
        self.var_mean_iti = tk.IntVar()
        self.var_min_iti = tk.IntVar()
        self.var_max_iti = tk.IntVar()
        self.var_pre_stim = tk.IntVar()
        self.var_post_stim = tk.IntVar()
        self.var_cs0_dur = tk.IntVar()
        self.var_cs0_freq = tk.IntVar()
        self.var_us0_delay = tk.IntVar()
        self.var_us0_dur = tk.IntVar()
        self.var_cs1_dur = tk.IntVar()
        self.var_cs1_freq = tk.IntVar()
        self.var_us1_delay = tk.IntVar()
        self.var_us1_dur = tk.IntVar()
        self.var_cs2_dur = tk.IntVar()
        self.var_cs2_freq = tk.IntVar()
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
        self.var_verbose = tk.BooleanVar()
        self.var_print_arduino = tk.BooleanVar()
        self.var_suppress_print_lick_form = tk.BooleanVar()
        self.var_suppress_print_movement = tk.BooleanVar()

        # Default variable values
        self.var_session_type.set(0)
        self.var_iti_distro.set(1)
        self.var_mean_iti.set(60000)
        self.var_min_iti.set(40000)
        self.var_max_iti.set(80000)
        self.var_pre_stim.set(7000)
        self.var_post_stim.set(13000)
        self.var_cs0_dur.set(2000)
        self.var_cs0_freq.set(3000)
        self.var_us0_delay.set(3000)
        self.var_us0_dur.set(50)
        self.var_cs1_dur.set(2000)
        self.var_cs1_freq.set(6000)
        self.var_us1_delay.set(3000)
        self.var_us1_dur.set(50)
        self.var_cs2_dur.set(2000)
        self.var_cs2_freq.set(12000)
        self.var_us2_delay.set(3000)
        self.var_us2_dur.set(50)
        self.var_consumption_dur.set(8000)
        self.var_vac_dur.set(100)
        self.var_trial_signal_offset.set(2000)
        self.var_trial_signal_dur.set(1000)
        self.var_trial_signal_freq.set(0)
        self.var_grace_dur.set(2000)
        self.var_response_dur.set(2000)
        self.var_timeout_dur.set(8000)
        self.var_image_all.set(0)
        self.var_image_ttl_dur.set(100)
        self.var_track_period.set(50)

        # Lay out GUI

        ## Setup frame
        frame_setup = tk.Frame(parent)
        frame_setup.grid(row=0, column=0, pady=pY)
        frame_setup_col0 = tk.Frame(frame_setup)
        frame_setup_col1 = tk.Frame(frame_setup)
        frame_setup_col2 = tk.Frame(frame_setup)
        frame_setup_col0.grid(row=0, column=0, sticky='we')
        frame_setup_col1.grid(row=0, column=1, sticky='we')
        frame_setup_col2.grid(row=0, column=2, sticky='we')

        ### Session frame
        frame_params = tk.Frame(frame_setup_col0)
        frame_params.grid(row=0, column=0, rowspan=3, padx=px, pady=py)
        frame_params.columnconfigure(0, weight=1)

        frame_session_type = tk.Frame(frame_params)
        frame_session = tk.Frame(frame_params)
        frame_trial_params = tk.Frame(frame_params)
        frame_misc = tk.Frame(frame_params)
        frame_session_type.grid(row=0, column=0, padx=px, pady=py)
        frame_session.grid(row=1, column=0, sticky='e', padx=px, pady=py)
        frame_trial_params.grid(row=2, column=0, sticky='we', padx=px, pady=py)
        frame_misc.grid(row=3, column=0, sticky='e', padx=px, pady=py)
        frame_session_type.columnconfigure(0, weight=1)
        frame_trial_params.columnconfigure(0, weight=1)

        ### Camera frame
        frame_cam = tk.Frame(frame_setup_col1)
        frame_cam.grid(row=0, column=0, padx=px, pady=py)

        ### Arduino frame
        frame_arduino = tk.LabelFrame(frame_setup_col1, text='Arduino')
        frame_arduino.grid(row=1, column=0, padx=px, pady=py, sticky='we')
        frame_arduino1 = tk.Frame(frame_arduino)
        frame_arduino2 = tk.Frame(frame_arduino)
        frame_arduino1.grid(row=0, column=0, sticky='we', padx=px, pady=py)
        frame_arduino2.grid(row=1, column=0, sticky='we', padx=px, pady=py)
        frame_arduino2.grid_columnconfigure(0, weight=1)
        frame_arduino2.grid_columnconfigure(1, weight=1)
        frame_arduino.grid_columnconfigure(0, weight=1)

        ### Debug frame
        frame_debug = tk.LabelFrame(frame_setup_col1, text='Debug')
        frame_debug.grid(row=2, column=0, padx=px, pady=py, sticky='we')
        frame_debug.grid_columnconfigure(0, weight=1)

        ### Notes frame
        frame_info = tk.Frame(frame_setup_col2)
        frame_info.grid(row=0, column=0, sticky='we', padx=px, pady=py)
        frame_info.grid_columnconfigure(0, weight=1)

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

        ## Separator frame
        frame_sep = tk.Frame(parent, height=1, bg='gray')
        frame_sep.grid(row=1, column=0, sticky='we', padx=pX, pady=pY)

        ## Monitor frame
        frame_monitor = tk.Frame(parent)
        frame_monitor.grid(row=2, column=0, pady=pY)
        frame_setup_col0 = tk.Frame(frame_monitor)
        frame_setup_col0.grid(row=0, column=0, sticky='we')

        ### Solenoid frame
        frame_sol = tk.Frame(frame_monitor)
        frame_sol.grid(row=0, column=0, sticky='we', padx=px, pady=py)
        frame_debug.grid_columnconfigure(0, weight=1)  # Fills into frame

        # Add GUI components

        ## frame_params
        ## Session parameters

        ### frame_session_type
        ### UI for choosing session type, ie, classical conditining vs go/no go.
        self.radio_conditioning = tk.Radiobutton(frame_session_type, text='Classical conditioning', variable=self.var_session_type, value=0, command=self.update_param_preview)
        self.radio_gonogo = tk.Radiobutton(frame_session_type, text='Go/no go', variable=self.var_session_type, value=1, command=self.update_param_preview)
        self.radio_conditioning.grid(row=0, column=0, sticky='w')
        self.radio_gonogo.grid(row=1, column=0, sticky='w')

        ### frame_session
        ### UI for session.
        self.entry_pre_session = tk.Entry(frame_session, **opts_entry)
        self.entry_post_session = tk.Entry(frame_session, **opts_entry)
        self.entry_cs0_num = tk.Entry(frame_session, **opts_entry)
        self.entry_cs1_num = tk.Entry(frame_session, **opts_entry)
        self.entry_cs2_num = tk.Entry(frame_session, **opts_entry)
        tk.Label(frame_session, text='Presession time (ms): ', anchor='e').grid(row=0, column=0, sticky='e')
        tk.Label(frame_session, text='Postsession time (ms): ', anchor='e').grid(row=1, column=0, sticky='e')
        tk.Label(frame_session, text='Number of CS0: ', anchor='e').grid(row=2, column=0, sticky='e')
        tk.Label(frame_session, text='Number of CS1: ', anchor='e').grid(row=3, column=0, sticky='e')
        tk.Label(frame_session, text='Number of CS2: ', anchor='e').grid(row=4, column=0, sticky='e')
        self.entry_pre_session.grid(row=0, column=1, sticky='w')
        self.entry_post_session.grid(row=1, column=1, sticky='w')
        self.entry_cs0_num.grid(row=2, column=1, sticky='w')
        self.entry_cs1_num.grid(row=3, column=1, sticky='w')
        self.entry_cs2_num.grid(row=4, column=1, sticky='w')
        

        ### frame_trial_params
        ### UI for session parameters.
        self.button_params = tk.Button(frame_trial_params, text='Parameters', command=self.set_params)
        self.text_params = tk.Text(frame_trial_params, width=50, height=10, font=("Arial", 8))
        self.button_params.grid(row=0, column=0, sticky='we')
        self.text_params.grid(row=1, column=0, sticky='we')
        # self.text_params['state'] = 'disabled'

        ### frame_misc
        ### UI for other things.
        self.check_image_all = tk.Checkbutton(frame_misc, variable=self.var_image_all)
        self.entry_image_ttl_dur = tk.Entry(frame_misc, **opts_entry)
        self.entry_track_period = tk.Entry(frame_misc, **opts_entry)
        tk.Label(frame_misc, text='Image everything: ', anchor='e').grid(row=0, column=0, sticky='e')
        tk.Label(frame_misc, text='Imaging TTL duration (ms): ', anchor='e').grid(row=1, column=0, sticky='e')
        tk.Label(frame_misc, text='Track period (ms): ', anchor='e').grid(row=2, column=0, sticky='e')
        self.check_image_all.grid(row=0, column=1, sticky='w')
        self.entry_image_ttl_dur.grid(row=1, column=1, sticky='w')
        self.entry_track_period.grid(row=2, column=1, sticky='w')

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
        self.check_verbose = tk.Checkbutton(frame_debug, text='Verbose', variable=self.var_verbose)
        self.check_print_arduino = tk.Checkbutton(frame_debug, text='Print Arduino serial', variable=self.var_print_arduino)
        self.check_suppress_print_lick_form = tk.Checkbutton(frame_debug, text='Suppress lick output', variable=self.var_suppress_print_lick_form)
        self.check_suppress_print_movement = tk.Checkbutton(frame_debug, text='Suppress movement output', variable=self.var_suppress_print_movement)
        self.check_verbose.grid(row=0, column=0, sticky='w')
        self.check_print_arduino.grid(row=1, column=0, sticky='w')
        self.check_suppress_print_lick_form.grid(row=2, column=0, sticky='w')
        self.check_suppress_print_movement.grid(row=3, column=0, sticky='w')

        ## frame_info
        ## UI for session info.
        self.entry_subject = tk.Entry(frame_info)
        self.entry_weight = tk.Entry(frame_info)
        self.scrolled_notes = ScrolledText(frame_info, width=20, height=15)
        tk.Label(frame_info, text="Subject: ").grid(row=0, column=0, sticky='e')
        tk.Label(frame_info, text="Weight: ").grid(row=1, column=0, sticky='e')
        tk.Label(frame_info, text="Notes: ").grid(row=2, column=0, columnspan=2, sticky='w')
        self.entry_subject.grid(row=0, column=1, sticky='w')
        self.entry_weight.grid(row=1, column=1, sticky='w')
        self.scrolled_notes.grid(row=3, column=0, columnspan=2, sticky='wens')

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

        ## frame_sol
        ## UI for controlling solenoids.
        self.button_vac_on = tk.Button(frame_sol, text='ON', command=lambda: self.ser_write(code_vac_on))
        self.button_vac_off = tk.Button(frame_sol, text='OFF', command=lambda: self.ser_write(code_vac_off))
        self.button_vac_trig = tk.Button(frame_sol, text='Trigger', command=lambda: self.ser_write(code_vac_trig))
        self.button_sol0_on = tk.Button(frame_sol, text='ON', command=lambda: self.ser_write(code_sol0_on))
        self.button_sol0_off = tk.Button(frame_sol, text='OFF', command=lambda: self.ser_write(code_sol0_off))
        self.button_sol0_trig = tk.Button(frame_sol, text='Trigger', command=lambda: self.ser_write(code_sol0_trig))
        self.button_sol1_on = tk.Button(frame_sol, text='ON', command=lambda: self.ser_write(code_sol1_on))
        self.button_sol1_off = tk.Button(frame_sol, text='OFF', command=lambda: self.ser_write(code_sol1_off))
        self.button_sol1_trig = tk.Button(frame_sol, text='Trigger', command=lambda: self.ser_write(code_sol1_trig))
        self.button_sol2_on = tk.Button(frame_sol, text='ON', command=lambda: self.ser_write(code_sol2_on))
        self.button_sol2_off = tk.Button(frame_sol, text='OFF', command=lambda: self.ser_write(code_sol2_off))
        self.button_sol2_trig = tk.Button(frame_sol, text='Trigger', command=lambda: self.ser_write(code_sol2_trig))
        tk.Label(frame_sol, text='Vacuum: ', anchor='e').grid(row=0, column=0, sticky='we')
        tk.Label(frame_sol, text='Solenoid 0: ', anchor='e').grid(row=1, column=0, sticky='we')
        tk.Label(frame_sol, text='Solenoid 1: ', anchor='e').grid(row=2, column=0, sticky='we')
        tk.Label(frame_sol, text='Solenoid 2: ', anchor='e').grid(row=3, column=0, sticky='we')
        self.button_vac_on.grid(row=0, column=1, sticky='we')
        self.button_vac_off.grid(row=0, column=2, sticky='we')
        self.button_vac_trig.grid(row=0, column=3, sticky='we')
        self.button_sol0_on.grid(row=1, column=1, sticky='we')
        self.button_sol0_off.grid(row=1, column=2, sticky='we')
        self.button_sol0_trig.grid(row=1, column=3, sticky='we')
        self.button_sol1_on.grid(row=2, column=1, sticky='we')
        self.button_sol1_off.grid(row=2, column=2, sticky='we')
        self.button_sol1_trig.grid(row=2, column=3, sticky='we')
        self.button_sol2_on.grid(row=3, column=1, sticky='we')
        self.button_sol2_off.grid(row=3, column=2, sticky='we')
        self.button_sol2_trig.grid(row=3, column=3, sticky='we')

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
        ]
        self.obj_to_disable_at_start = [
            self.button_close_port,
            self.check_print_arduino,
            self.check_suppress_print_lick_form,
            self.check_suppress_print_movement,
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
        ]
        self.obj_to_enable_at_start = [
            self.button_stop,
        ]

        # Boolean of objects states at open
        # Useful if object states are volatile, but state should be returned 
        # once serial is closed.
        self.obj_enabled_at_open = [False] * len(self.obj_to_disable_at_open)

        # Default values
        self.entry_pre_session.insert(0, 60000)
        self.entry_post_session.insert(0, 60000)
        self.entry_cs0_num.insert(0, 20)
        self.entry_cs1_num.insert(0, 20)
        self.entry_cs2_num.insert(0, 0)
        self.entry_image_ttl_dur.insert(0, self.var_image_ttl_dur.get())
        self.entry_track_period.insert(0, self.var_track_period.get())

        # Finalize
        self.update_param_preview()
        self.parameters = collections.OrderedDict()
        self.ser = serial.Serial(timeout=1, baudrate=9600)
        self.update_ports()
        self.q_serial = Queue()
        self.counter = {}

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

    def set_params(self):
        session_type = self.var_session_type.get()

        title_session = 'Go/no-go' if session_type else 'Classical conditioning'
        window_param = tk.Toplevel(self)
        window_param.wm_title('{} parameters'.format(title_session))

        frame_trial = tk.Frame(window_param)
        frame_csus = tk.Frame(window_param)
        frame_vac = tk.Frame(window_param)
        frame_update = tk.Frame(window_param)
        frame_trial.grid(row=0, column=0, sticky='we', padx=px, pady=py)
        frame_csus.grid(row=1, column=0, sticky='we', padx=px, pady=py)
        frame_vac.grid(row=2, column=0, sticky='we', padx=px, pady=py)
        frame_update.grid(row=4, column=0, sticky='we', padx=px, pady=py)
        frame_trial.columnconfigure(0, weight=1)
        frame_csus.columnconfigure(0, weight=1)
        frame_vac.columnconfigure(0, weight=1)
        frame_update.columnconfigure(0, weight=1)

        frame_trial_col0 = tk.Frame(frame_trial)
        frame_trial_col1 = tk.Frame(frame_trial)
        frame_trial_col0.grid(row=0, column=0, padx=px, pady=py)
        frame_trial_col1.grid(row=0, column=1, padx=px, pady=py)

        frame_cs = tk.Frame(frame_csus)
        frame_us = tk.Frame(frame_csus)
        frame_cs.grid(row=0, column=0, sticky='we', padx=px, pady=py)
        frame_us.grid(row=0, column=1, sticky='we', padx=px, pady=py)

        # frame_trial
        # UI for trial.
        radio_fixed_iti = tk.Radiobutton(frame_trial_col0, text='Fixed', variable=self.var_iti_distro, value=0)#, command=lambda: self.gui_util('fixed'))
        radio_uniform_iti = tk.Radiobutton(frame_trial_col0, text='Uniform distro', variable=self.var_iti_distro, value=1)#, command=lambda: self.gui_util('not_fixed'))
        radio_expo_iti = tk.Radiobutton(frame_trial_col0, text='Exponential distro', variable=self.var_iti_distro, value=2)#, command=lambda: self.gui_util('not_fixed'))
        radio_fixed_iti.grid(row=0, column=1, sticky='w')
        radio_uniform_iti.grid(row=1, column=1, sticky='w')
        radio_expo_iti.grid(row=2, column=1, sticky='w')

        self.entry_mean_iti = tk.Entry(frame_trial_col1, **opts_entry)
        self.entry_min_iti = tk.Entry(frame_trial_col1, **opts_entry)
        self.entry_max_iti = tk.Entry(frame_trial_col1, **opts_entry)
        self.entry_pre_stim = tk.Entry(frame_trial_col1, **opts_entry)
        self.entry_post_stim = tk.Entry(frame_trial_col1, **opts_entry)
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
        self.entry_cs0_dur = tk.Entry(frame_cs, **opts_entry)
        self.entry_cs0_freq = tk.Entry(frame_cs, **opts_entry)
        self.entry_cs1_dur = tk.Entry(frame_cs, **opts_entry)
        self.entry_cs1_freq = tk.Entry(frame_cs, **opts_entry)
        tk.Label(frame_cs, text='t (ms)', anchor='center').grid(row=0, column=1, sticky='we')
        tk.Label(frame_cs, text='f (s' u'\u207b\u00b9' ')', anchor='center').grid(row=0, column=2, sticky='we')
        tk.Label(frame_cs, text='CS0: ', anchor='e').grid(row=1, column=0, sticky='e')
        tk.Label(frame_cs, text='CS1: ', anchor='e').grid(row=2, column=0, sticky='e')
        self.entry_cs0_dur.grid(row=1, column=1, sticky='w')
        self.entry_cs0_freq.grid(row=1, column=2, sticky='w')
        self.entry_cs1_dur.grid(row=2, column=1, sticky='w')
        self.entry_cs1_freq.grid(row=2, column=2, sticky='w')

        self.entry_us0_dur = tk.Entry(frame_us, **opts_entry)
        self.entry_us1_dur = tk.Entry(frame_us, **opts_entry)
        tk.Label(frame_us, text='t (ms)', anchor='center').grid(row=0, column=1, sticky='we')
        tk.Label(frame_us, text='US0: ', anchor='e').grid(row=1, column=0, sticky='e')
        tk.Label(frame_us, text='US1: ', anchor='e').grid(row=2, column=0, sticky='e')
        self.entry_us0_dur.grid(row=1, column=1, sticky='w')
        self.entry_us1_dur.grid(row=2, column=1, sticky='w')

        # frame_vac
        # UI for vacuum.
        self.entry_consumption_dur = tk.Entry(frame_vac, **opts_entry)
        self.entry_vac_dur = tk.Entry(frame_vac, **opts_entry)
        tk.Label(frame_vac, text='Consumption time limit (ms): ', anchor='e').grid(row=0, column=0, sticky='e')
        tk.Label(frame_vac, text='Vacuum duration (ms): ', anchor='e').grid(row=1, column=0, sticky='e')
        self.entry_consumption_dur.grid(row=0, column=1, sticky='w')
        self.entry_vac_dur.grid(row=1, column=1, sticky='w')

        # frame_update
        # UI for 'Update' button
        button_update = tk.Button(frame_update, text='Update', command=self.update_params)
        button_update.grid(row=0, column=0)

        entries = [
            self.entry_mean_iti,
            self.entry_min_iti,
            self.entry_max_iti,
            self.entry_pre_stim,
            self.entry_post_stim,
            self.entry_cs0_dur,
            self.entry_cs0_freq,
            self.entry_us0_dur,
            self.entry_cs1_dur,
            self.entry_cs1_freq,
            self.entry_us1_dur,
            self.entry_consumption_dur,
            self.entry_vac_dur,
        ]
        entry_vars = [
            self.var_mean_iti,
            self.var_min_iti,
            self.var_max_iti,
            self.var_pre_stim,
            self.var_post_stim,
            self.var_cs0_dur,
            self.var_cs0_freq,
            self.var_us0_dur,
            self.var_cs1_dur,
            self.var_cs1_freq,
            self.var_us1_dur,
            self.var_consumption_dur,
            self.var_vac_dur,
        ]

        if session_type == 0:
            # Classical conditioning

            frame_csus2 = tk.Frame(window_param)
            frame_csus2.grid(row=3, column=0, sticky='e', padx=px, pady=py)
            
            self.entry_cs2_dur = tk.Entry(frame_cs, **opts_entry)
            self.entry_cs2_freq = tk.Entry(frame_cs, **opts_entry)
            tk.Label(frame_cs, text='CS2: ', anchor='e').grid(row=3, column=0, sticky='e')
            self.entry_cs2_dur.grid(row=3, column=1, sticky='w')
            self.entry_cs2_freq.grid(row=3, column=2, sticky='w')

            self.entry_us2_dur = tk.Entry(frame_us, **opts_entry)
            self.entry_us0_delay = tk.Entry(frame_us, **opts_entry)
            self.entry_us1_delay = tk.Entry(frame_us, **opts_entry)
            self.entry_us2_delay = tk.Entry(frame_us, **opts_entry)
            tk.Label(frame_us, text='US2: ', anchor='e').grid(row=3, column=0, sticky='e')
            tk.Label(frame_us, text='Delay (ms)', anchor='e').grid(row=0, column=2, sticky='e')
            self.entry_us2_dur.grid(row=3, column=1, sticky='w')
            self.entry_us0_delay.grid(row=1, column=2, sticky='w')
            self.entry_us1_delay.grid(row=2, column=2, sticky='w')
            self.entry_us2_delay.grid(row=3, column=2, sticky='w')

            # self.entry_cs2_dur = tk.Entry(frame_csus2, width=entry_width)
            # self.entry_cs2_freq = tk.Entry(frame_csus2, width=entry_width)
            # self.entry_us2_dur = tk.Entry(frame_csus2, width=entry_width)
            # tk.Label(frame_csus2, text='CS2 duration (ms): ', anchor='e').grid(row=0, column=0, sticky='e')
            # tk.Label(frame_csus2, text='CS2 frequency (s' u'\u207b\u00b9' '): ', anchor='e').grid(row=1, column=0, sticky='e')
            # tk.Label(frame_csus2, text='US2 duration (ms): ', anchor='e').grid(row=2, column=0, sticky='e')
            # self.entry_cs2_dur.grid(row=0, column=1, sticky='w')
            # self.entry_cs2_freq.grid(row=1, column=1, sticky='w')
            # self.entry_us2_dur.grid(row=2, column=1, sticky='w')

            # self.entry_us0_delay = tk.Entry(frame_csus0, width=entry_width)
            # self.entry_us1_delay = tk.Entry(frame_csus1, width=entry_width)
            # self.entry_us2_delay = tk.Entry(frame_csus2, width=entry_width)
            # tk.Label(frame_csus0, text='US0 delay (ms): ', anchor='e').grid(row=3, column=0, sticky='e')
            # tk.Label(frame_csus1, text='US1 delay (ms): ', anchor='e').grid(row=3, column=0, sticky='e')
            # tk.Label(frame_csus2, text='US2 delay (ms): ', anchor='e').grid(row=3, column=0, sticky='e')
            # self.entry_us0_delay.grid(row=3, column=1, sticky='w')
            # self.entry_us1_delay.grid(row=3, column=1, sticky='w')
            # self.entry_us2_delay.grid(row=3, column=1, sticky='w')
            
            entries += [
                self.entry_cs2_dur,
                self.entry_cs2_freq,
                self.entry_us2_dur,
                self.entry_us0_delay,
                self.entry_us1_delay,
                self.entry_us2_delay,
            ]
            entry_vars += [
                self.var_cs2_dur,
                self.var_cs2_freq,
                self.var_us2_dur,
                self.var_us0_delay,
                self.var_us1_delay,
                self.var_us2_delay,
            ]
        elif session_type == 1:
            # Go/no-go

            frame_gonogo = tk.Frame(window_param)
            frame_gonogo.grid(row=3, column=0, sticky='e', padx=px, pady=py)

            ### frame_gonogo
            ### UI for trial start (signal)
            self.entry_trial_signal_offset = tk.Entry(frame_gonogo, **opts_entry)
            self.entry_trial_signal_dur = tk.Entry(frame_gonogo, **opts_entry)
            self.entry_trial_signal_freq = tk.Entry(frame_gonogo, **opts_entry)
            self.entry_grace_dur = tk.Entry(frame_gonogo, **opts_entry)
            self.entry_response_dur = tk.Entry(frame_gonogo, **opts_entry)
            self.entry_timeout_dur = tk.Entry(frame_gonogo, **opts_entry)
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

            entries += [
                self.entry_trial_signal_offset,
                self.entry_trial_signal_dur,
                self.entry_trial_signal_freq,
                self.entry_grace_dur,
                self.entry_response_dur,
                self.entry_timeout_dur,
            ]
            entry_vars += [
                self.var_trial_signal_offset,
                self.var_trial_signal_dur,
                self.var_trial_signal_freq,
                self.var_grace_dur,
                self.var_response_dur,
                self.var_timeout_dur,
            ]

        for entry, var in zip(entries, entry_vars):
            entry.delete(0, 'end')
            entry.insert(0, var.get())

    def update_params(self):
        '''Update parameters from GUI
        Executes when 'Update' button is pressed from parameters window.
        '''

        session_type = self.var_session_type.get()
        iti_type = self.var_iti_distro.get()

        self.var_mean_iti.set(int(self.entry_mean_iti.get()))
        self.var_min_iti.set(int(self.entry_min_iti.get()))
        self.var_max_iti.set(int(self.entry_max_iti.get()))
        self.var_pre_stim.set(int(self.entry_pre_stim.get()))
        self.var_post_stim.set(int(self.entry_post_stim.get()))
        self.var_cs0_dur.set(int(self.entry_cs0_dur.get()))
        self.var_cs0_freq.set(int(self.entry_cs0_freq.get()))
        self.var_us0_dur.set(int(self.entry_us0_dur.get()))
        self.var_cs1_dur.set(int(self.entry_cs1_dur.get()))
        self.var_cs1_freq.set(int(self.entry_cs1_freq.get()))
        self.var_us1_dur.set(int(self.entry_us1_dur.get()))
        self.var_consumption_dur.set(int(self.entry_consumption_dur.get()))
        self.var_vac_dur.set(int(self.entry_vac_dur.get()))

        if session_type == 0:
            # Classical conditioning
            self.var_us0_delay.set(int(self.entry_us0_delay.get()))
            self.var_us1_delay.set(int(self.entry_us1_delay.get()))
            self.var_cs2_dur.set(int(self.entry_cs2_dur.get()))
            self.var_cs2_freq.set(int(self.entry_cs2_freq.get()))
            self.var_us2_delay.set(int(self.entry_us2_delay.get()))
            self.var_us2_dur.set(int(self.entry_us2_dur.get()))

        elif session_type == 1:
            # Go/no-go
            self.var_trial_signal_offset.set(int(self.entry_trial_signal_offset.get()))
            self.var_trial_signal_dur.set(int(self.entry_trial_signal_dur.get()))
            self.var_trial_signal_freq.set(int(self.entry_trial_signal_freq.get()))
            self.var_grace_dur.set(int(self.entry_grace_dur.get()))
            self.var_response_dur.set(int(self.entry_response_dur.get()))
            self.var_timeout_dur.set(int(self.entry_timeout_dur.get()))

        self.update_param_preview()

    def update_param_preview(self):
        session_type = self.var_session_type.get()
        iti_type = self.var_iti_distro.get()

        if iti_type == 0:
            summary_iti = 'ITI: {}'.format(self.var_mean_iti.get())
        else:
            summary_iti = 'ITI: {} (mean), {} (min), {} (max)'.format(
                self.var_mean_iti.get(), self.var_min_iti.get(), self.var_max_iti.get()
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
            pdb.set_trace()
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
                sys.stdout.write(arduino_head + self.ser.readline())
        else:
            self.ser.flushInput()

        # Define parameters
        # NOTE: Order is important here since this order is preserved when 
        # sending via serial.
        self.parameters = collections.OrderedDict()   # Clear self.parameters (maybe not necessary)

        self.parameters['session_type'] = self.var_session_type.get()
        self.parameters['pre_session'] = int(self.entry_pre_session.get())
        self.parameters['post_session'] = int(self.entry_post_session.get())
        self.parameters['cs0_num'] = int(self.entry_cs0_num.get())
        self.parameters['cs1_num'] = int(self.entry_cs1_num.get())
        self.parameters['cs2_num'] = int(self.entry_cs2_num.get())
        self.parameters['iti_distro'] = self.var_iti_distro.get()
        self.parameters['mean_iti'] = self.var_mean_iti.get()
        self.parameters['min_iti'] = self.var_min_iti.get()
        self.parameters['max_iti'] = self.var_max_iti.get()
        self.parameters['pre_stim'] = self.var_pre_stim.get()
        self.parameters['post_stim'] = self.var_post_stim.get()
        self.parameters['cs0_dur'] = self.var_cs0_dur.get()
        self.parameters['cs0_freq'] = self.var_cs0_freq.get()
        self.parameters['us0_dur'] = self.var_us0_dur.get()
        self.parameters['us0_delay'] = self.var_us0_delay.get()
        self.parameters['cs1_dur'] = self.var_cs1_dur.get()
        self.parameters['cs1_freq'] = self.var_cs1_freq.get()
        self.parameters['us1_dur'] = self.var_us1_dur.get()
        self.parameters['us1_delay'] = self.var_us1_delay.get()
        self.parameters['cs2_dur'] = self.var_cs2_dur.get()
        self.parameters['cs2_freq'] = self.var_cs2_freq.get()
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
        self.ser.write(code_params + '+'.join(str(s) for s in values))

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

    def ser_write(self, code):
        self.ser.write(code)

    def get_save_file(self):
        '''Opens prompt for file for data to be saved on button press'''

        save_file = tkFileDialog.asksaveasfilename(
            initialdir=self.entry_file.get(),
            defaultextension='.h5',
            filetypes=[
                ('HDF5 file', '*.h5 *.hdf5'),
                ('All files', '*.*')
            ]
        )
        self.entry_file.delete(0, 'end')
        self.entry_file.insert(0, save_file)

    def start(self, code_start='E'):
        '''Start session on button press'''

        self.gui_util('start')

        # Create data file
        if self.entry_file.get():
            try:
                # Create file if it doesn't already exist, append otherwise ('a' parameter)
                self.data_file = h5py.File(self.entry_file.get(), 'a')
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
        index = 0
        file_index = ''
        while True:
            try:
                self.grp_exp = self.data_file.create_group(date + file_index)
            except (RuntimeError, ValueError):
                index += 1
                file_index = '-' + str(index)
            else:
                break

        # Initialize datasets
        n_trials = self.parameters['cs0_num'] + self.parameters['cs1_num'] + self.parameters['cs2_num']
        n_movement_frames = 2 * (n_trials * self.parameters['mean_iti'] + 
            self.parameters['pre_session'] + self.parameters['post_session']
            ) / self.parameters['track_period']
        chunk_size = (2, 1)

        self.grp_behav = self.grp_exp.create_group('behavior')
        self.grp_behav.create_dataset(name='lick', dtype='uint32',
            shape=(2, n_movement_frames), chunks=chunk_size)
        self.grp_behav.create_dataset(name='lick_form', dtype='uint32',
            shape=(2, n_movement_frames), chunks=chunk_size)
        self.grp_behav.create_dataset(name='movement', dtype='int32',
            shape=(2, n_movement_frames), chunks=chunk_size)
        self.grp_behav.create_dataset(name='trial_start', dtype='uint32',
            shape=(2, n_trials), chunks=chunk_size)
        self.grp_behav.create_dataset(name='trial_signal', dtype='uint32',
            shape=(2, n_trials), chunks=chunk_size)
        self.grp_behav.create_dataset(name='cs', dtype='uint32',
            shape=(2, n_trials), chunks=chunk_size)
        self.grp_behav.create_dataset(name='us', dtype='uint32',
            shape=(2, n_trials), chunks=chunk_size)
        self.grp_behav.create_dataset(name='response', dtype='uint32',
            shape=(2, n_trials), chunks=chunk_size)

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
        for key, value in self.parameters.iteritems():
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
            args=(self.q_serial, self.ser, self.var_print_arduino.get(), suppress)
        )

        # Reset things
        self.counter = {ev: 0 for ev in events}

        # Start session
        self.ser.write(code_start)
        thread_scan.start()
        start_time = datetime.now().time()
        print('Session started at {}'.format(start_time))
        self.grp_exp.attrs['start_time'] = str(start_time)

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

        # End on "Stop" button (by user)
        if self.var_stop.get():
            self.var_stop.set(False)
            self.ser.write('0')
            print('User triggered stop, sending signal to Arduino...')

        # Watch incoming queue
        # Data has format: [code, ts, extra values]
        if not self.q_serial.empty():
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
            if code not in [8]:
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

        print('Writing behavioral data into HDF5 group {}'.format(self.gr_exp.name))
        self.grp_exp.attrs['subject'] = self.entry_subject.get()
        self.grp_exp.attrs['weight'] = self.entry_weight.get()
        self.grp_behav.attrs['end_time'] = end_time
        self.grp_behav.attrs['notes'] = self.scrolled_notes.get(1.0, 'end')
        self.grp_behav.attrs['arduino_end'] = arduino_end
        for ev in events:
            self.grp_behav[ev].resize((2, self.counter[ev]))

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
def scan_serial(q_serial, ser, print_arduino=False, suppress=[]):
    '''Check serial for data
    Continually check serial connection for data sent from Arduino. Send data 
    through Queue to communicate with main GUI. Stop when `code_end` is 
    received from serial.
    '''

    while 1:
        input_arduino = ser.readline()
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
                if print_arduino: print("  Scan complete.")
                return


def main():
    # GUI
    root = tk.Tk()
    root.wm_title('Go/no go & classical conditining')
    # default_font = tkFont.nametofont('TkDefaultFont')
    # default_font.configure(family='Arial')
    # root.option_add('*Font', default_font)
    InputManager(root)
    root.grid()
    root.mainloop()


if __name__ == '__main__':
    main()
