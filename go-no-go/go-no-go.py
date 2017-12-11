#!/usr/bin/env python

"""
Go/no go

Creates GUI to control behavioral and imaging devices for in vivo calcium
imaging. Script interfaces with Arduino microcontroller and imaging devices.
"""

import matplotlib
matplotlib.use('TKAgg')
import Tkinter as tk
import tkFont
import tkMessageBox
import tkFileDialog
from ScrolledText import ScrolledText
from PIL import ImageTk
import collections
import serial
import serial.tools.list_ports
import threading
from Queue import Queue
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
        self.var_verbose = tk.BooleanVar()
        self.check_verbose = tk.Checkbutton(frame_debug, variable=self.var_verbose)
        tk.Label(frame_debug, text='Verbose: ', anchor='e').grid(row=0, column=0, sticky='e')
        self.check_verbose.grid(row=0, column=1, sticky='w')

        ## frame_params
        ## Session parameters

        ### frame_session_type
        ### UI for choosing session type, ie, classical conditining vs go/no go.
        self.var_session_type = tk.IntVar()
        self.radio_conditioning = tk.Radiobutton(frame_session_type, variable=self.var_session_type, value=0)
        self.radio_gonogo = tk.Radiobutton(frame_session_type, variable=self.var_session_type, value=1)
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
        self.var_uniform_iti = tk.BooleanVar()
        self.entry_mean_iti = tk.Entry(frame_trial, width=entry_width)
        self.entry_min_iti = tk.Entry(frame_trial, width=entry_width)
        self.entry_max_iti = tk.Entry(frame_trial, width=entry_width)
        self.entry_pre_stim = tk.Entry(frame_trial, width=entry_width)
        self.entry_post_stim = tk.Entry(frame_trial, width=entry_width)
        self.check_uniform_iti = tk.Checkbutton(frame_trial, variable=self.var_uniform_iti)
        tk.Label(frame_trial, text='Uniform ITI: ', anchor='e').grid(row=0, column=0, sticky='e')
        tk.Label(frame_trial, text='Mean ITI (ms): ', anchor='e').grid(row=1, column=0, sticky='e')
        tk.Label(frame_trial, text='Min ITI (ms): ', anchor='e').grid(row=2, column=0, sticky='e')
        tk.Label(frame_trial, text='Max ITI (ms): ', anchor='e').grid(row=3, column=0, sticky='e')
        tk.Label(frame_trial, text='Prestim time (ms): ', anchor='e').grid(row=4, column=0, sticky='e')
        tk.Label(frame_trial, text='Poststim time (ms): ', anchor='e').grid(row=5, column=0, sticky='e')
        self.check_uniform_iti.grid(row=0, column=1, sticky='w')
        self.entry_mean_iti.grid(row=1, column=1, sticky='w')
        self.entry_min_iti.grid(row=2, column=1, sticky='w')
        self.entry_max_iti.grid(row=3, column=1, sticky='w')
        self.entry_pre_stim.grid(row=4, column=1, sticky='w')
        self.entry_post_stim.grid(row=5, column=1, sticky='w')

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
            self.check_uniform_iti,
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
        ## Example: 3000+3000+3+1+1+3000+3000+60000+500+1000+500+100+0+500+500+1000+0+500+0+100
        self.entry_pre_session.insert(0, 5000)
        self.entry_post_session.insert(0, 5000)
        self.entry_cs0_num.insert(0, 3)
        self.entry_cs1_num.insert(0, 1)
        
        self.var_uniform_iti.set(1)
        self.entry_mean_iti.insert(0, 3000)
        self.entry_min_iti.insert(0, 3000)
        self.entry_max_iti.insert(0, 60000)
        self.entry_pre_stim.insert(0, 500)
        self.entry_post_stim.insert(0, 1000)
        
        self.entry_cs0_dur.insert(0, 500)
        self.entry_cs0_freq.insert(0, 100)
        self.entry_us0_delay.insert(0, 0)
        self.entry_us0_dur.insert(0, 500)
        self.entry_cs1_dur.insert(0, 500)
        self.entry_cs1_freq.insert(0, 1000)
        self.entry_us1_delay.insert(0, 0)
        self.entry_us1_dur.insert(0, 500)

        self.entry_trial_signal_offset.insert(0, 1000)
        self.entry_trial_signal_dur.insert(0, 100)
        self.entry_trial_signal_freq.insert(0, 0)
        self.entry_grace_dur.insert(0, 2000)
        self.entry_response_dur.insert(0, 2000)
        self.entry_timeout_dur.insert(0, 8000)

        self.var_image_all.set(0)
        self.entry_image_ttl_dur.insert(0, 100)
        self.entry_track_period.insert(0, 50)

        # Finalize
        self.parameters = collections.OrderedDict()
        self.ser = serial.Serial(timeout=1, baudrate=9600)
        self.update_ports()

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

    def open_serial(self, delay=3):
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
            err_msg = err.args[0]
            tkMessageBox.showerror('Serial error', err_msg)
            print('Serial error: ' + err_msg)
            self.close_serial()
            self.gui_util('close')
        else:
            # Serial opened successfully
            time.sleep(delay)
            self.gui_util('opened')
            if self.var_verbose.get(): print('Connection to Arduino opened')

        # Send parameters to Arduino

        # Define parameters
        # NOTE: Order is important here since this order is preserved when 
        # sending via serial.
        self.parameters['session_type'] = self.var_session_type.get()
        self.parameters['pre_session'] = self.entry_pre_session.get()
        self.parameters['post_session'] = self.entry_post_session.get()
        self.parameters['cs0_num'] = self.entry_cs0_num.get()
        self.parameters['cs1_num'] = self.entry_cs1_num.get()

        self.parameters['uniform_iti'] = self.var_uniform_iti.get()
        self.parameters['mean_iti'] = self.entry_mean_iti.get()
        self.parameters['min_iti'] = self.entry_min_iti.get()
        self.parameters['max_iti'] = self.entry_max_iti.get()
        self.parameters['pre_stim'] = self.entry_pre_stim.get()
        self.parameters['post_stim'] = self.entry_post_stim.get()

        self.parameters['cs0_dur'] = self.entry_cs0_dur.get()
        self.parameters['cs0_freq'] = self.entry_cs0_freq.get()
        self.parameters['us0_delay'] = self.entry_us0_delay.get()
        self.parameters['us0_dur'] = self.entry_us0_dur.get()
        self.parameters['cs1_dur'] = self.entry_cs1_dur.get()
        self.parameters['cs1_freq'] = self.entry_cs1_freq.get()
        self.parameters['us1_delay'] = self.entry_us1_delay.get()
        self.parameters['us1_dur'] = self.entry_us1_dur.get()

        self.parameters['trial_signal_offset'] = self.entry_trial_signal_offset.get()
        self.parameters['trial_signal_dur'] = self.entry_trial_signal_dur.get()
        self.parameters['trial_signal_freq'] = self.entry_trial_signal_freq.get()
        self.parameters['grace_dur'] = self.entry_grace_dur.get()
        self.parameters['response_dur'] = self.entry_response_dur.get()
        self.parameters['timeout_dur'] = self.entry_timeout_dur.get()

        self.parameters['image_all'] = self.var_image_all.get()
        self.parameters['image_ttl_dur'] = self.entry_image_ttl_dur.get()
        self.parameters['track_period'] = self.entry_track_period.get()

        # Cast parameters to int
        self.parameters = {key: int(val) for key, val in self.parameters.iteritems()}

        send_status = send_to_arduino(self.ser, self.parameters, verbose=self.var_verbose.get())
        if send_status:
            print('Error sending parameters to Arduino')
            print(send_status)
            self.gui_util('close')
            self.close_serial()
        else:
            if self.var_verbose.get():
                print('Parameters uploaded to Arduino')
                print('Ready to start')


    def close_serial(self):
        '''Close serial connection to Arduino
        Executes when 'Close' button is pressed.
        '''
        self.ser.close()
        self.gui_util('close')
        if self.var_verbose.get(): print('Connection to Arduino closed')

    def update_ports(self):
        '''Updates list of available ports
        Executes when 'Update' button is pressed.
        '''
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
        ''' Opens prompt for file for data to be saved
        Runs when button beside save file is pressed.
        '''
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
        self.gui_util('start')

        # Clear Queues
        # for q in [self.q, self.q_to_thread_rec, self.q_from_thread_rec]:
        #     with q.mutex:
        #         q.queue.clear()

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
        self.grp_behav.create_dataset(name='trials', dtype='uint32',
            shape=(1000, ), chunks=(1, ))
        self.grp_behav.create_dataset(name='trial_manual', dtype=bool,
            shape=(1000, ), chunks=(1, ))
        self.grp_behav.create_dataset(name='movement', dtype='int32',
            shape=(2, int(nstepframes) * 1.1), chunks=(2, 1))

        # Store session parameters into behavior group
        for key, value in self.parameters.iteritems():
            self.behav_grp.attrs[key] = value

        self.ser.flushInput()                                   # Remove data from serial input
        self.ser.write('E')                                     # Start signal for Arduino


def slack_msg(slack_recipient, msg, test=False, verbose=False):
    '''Sends message through Slack
    Creates Slack message `msg` to `slack_recipient` from Bot.
    '''
    bot_username = 'Go/no go bot'
    bot_icon = ':squirrel:'

    if test: msg='Test'
    slack.api_call(
      'chat.postMessage',
      username=bot_username,
      icon_emoji=bot_icon,
      channel=slack_recipient,
      text=msg
    )


def send_to_arduino(ser, params, timeout=5, verbose=False):
    '''Write parameters to Arduino
    Sends parameters over serial as numbers (integers). Delimited by '+'.
    '''

    # Handle opening message from serial
    if verbose:
        while ser.in_waiting:
            sys.stdout.write('[a]\t' + ser.readline())
    else:
        ser.flushInput()
    
    values = params.values()
    if verbose: print('Sending parameters: {}'.format(values))
    
    ser.write('+'.join(str(s) for s in values))
    start_time = time.time()

    while 1:
        if ser.in_waiting:
            if verbose:
                # Print incoming data
                while ser.in_waiting:
                    sys.stdout.write('[a]\t' + ser.readline())
            break
        elif time.time() >= start_time + timeout:
            err_msg = 'Uploading timed out. Start signal not found.'
            return serial.SerialException(err_msg)



        ## Camera parameters
        # self.var_fps.set(10)
        # self.var_vsub.set(50)
        # self.var_hsub.set(50)
        # self.var_gain.set(15)
        # self.var_expo.set(40)

        ## GUI components
        # self.button_close_port['state'] = 'disabled'
        # self.button_start['state'] = 'disabled'
        # self.button_stop['state'] = 'disabled'
        
        # # Options frame
        # opt_session_frame = tk.Frame(frame_setup)
        # opt_session_frame.grid(row=0, column=0)
'''
        # Hardware parameters
        hardware_frame = tk.Frame(frame_setup)
        hardware_frame.grid(row=0, column=1)
        hardware_frame.grid_columnconfigure(0, weight=1)

        ## UI for camera
        self.frame_cam = tk.LabelFrame(hardware_frame, text="Camera")
        self.frame_cam.grid(row=0, column=0, padx=px, pady=py, sticky='we')

        self.var_preview = tk.BooleanVar()
        self.var_fps = tk.DoubleVar()
        self.var_vsub = tk.IntVar()
        self.var_hsub = tk.IntVar()
        self.var_gain = tk.IntVar()
        self.var_expo = tk.IntVar()
        self.var_instr = tk.StringVar()

        self.option_instr = tk.OptionMenu(self.frame_cam,
            self.var_instr, [])
        self.option_instr.configure(anchor=tk.W)
        self.button_refresh_instr = tk.Button(self.frame_cam,
            text="Update", command=self.update_instruments)
        self.button_preview = tk.Button(self.frame_cam,
            text="Preview", command=self.cam_preview)
        self.button_settings = tk.Button(self.frame_cam,
            text="Settings", command=self.cam_settings)

        self.option_instr.grid(row=1, column=0, columnspan=3, padx=px1, pady=py1, sticky='we')
        self.button_refresh_instr.grid(row=2, column=0, padx=px1, pady=py1, sticky='we')
        self.button_preview.grid(row=2, column=1, padx=px1, pady=py1, sticky='we')
        self.button_settings.grid(row=2, column=2, padx=px1, pady=py1, sticky='we')
        self.instrument_panels = [
            self.option_instr,
            self.button_refresh_instr,
        ]

        ## UI for debug options
        debug_frame = tk.LabelFrame(hardware_frame, text="Debugging")
        debug_frame.grid(row=2, column=0, padx=px, pady=py, sticky='we')
        
        self.print_var = tk.BooleanVar()
        self.var_sim_cam = tk.BooleanVar()
        self.var_sim_arduino = tk.BooleanVar()

        self.check_print = tk.Checkbutton(debug_frame, text=" Print Arduino output", variable=self.print_var)
        self.check_sim_cam = tk.Checkbutton(debug_frame, text=" Simulate camera", variable=self.var_sim_cam)
        self.check_sim_arduino = tk.Checkbutton(debug_frame, text=" Simulate Arduino", variable=self.var_sim_arduino)
        self.pdb = tk.Button(debug_frame, text="pdb", command=pdb.set_trace)

        self.check_print.grid(row=0, column=0, padx=px1, sticky='w')
        self.check_sim_cam.grid(row=1, column=0, padx=px1, sticky='w')
        self.check_sim_arduino.grid(row=2, column=0, padx=px1, sticky='w')
        self.pdb.grid(row=3, column=0, padx=px1, sticky='w')

        # Frame for file
        frame_file = tk.Frame(frame_setup)
        frame_file.grid(row=0, column=2, padx=5, pady=5, sticky='wens')
        frame_file.columnconfigure(0, weight=1)

        ## Notes
        frame_notes = tk.Frame(frame_file)
        frame_notes.grid(row=0, sticky='wens', padx=px, pady=py)
        frame_notes.grid_columnconfigure(0, weight=1)

        tk.Label(frame_notes, text="Notes:").grid(row=0, column=0, sticky='w')
        self.scrolled_notes = ScrolledText(frame_notes, width=20, height=15)

        self.scrolled_notes.grid(row=1, column=0, sticky='wens')

        

        ## Start frame
        start_frame = tk.Frame(frame_file)
        start_frame.grid(row=2, column=0, columnspan=2, padx=px, pady=py, sticky='we')
        start_frame.columnconfigure(0, weight=1)
        start_frame.columnconfigure(1, weight=1)
        start_frame.columnconfigure(2, weight=1)
        start_frame.columnconfigure(3, weight=1)

        self.stop = tk.BooleanVar()
        self.stop.set(False)

        tk.Label(start_frame, text="File to save data:", anchor=tk.W).grid(row=0, column=0, columnspan=4, sticky=tk.W)
        self.entry_save = tk.Entry(start_frame)
        self.button_save_file = tk.Button(start_frame, text="...", command=self.get_save_file)
        self.button_start = tk.Button(start_frame, text="Start", command=lambda: self.parent.after(0, self.start))
        self.button_stop = tk.Button(start_frame, text="Stop", command=lambda: self.stop.set(True))

        self.entry_save.grid(row=1, column=0, columnspan=3, sticky='wens')
        self.button_save_file.grid(row=1, column=4, sticky='e')
        self.button_start.grid(row=2, column=0, sticky='w')
        self.button_stop.grid(row=2, column=1, sticky='w')

        ###########################
        ###### MONITOR FRAME ######
        ###########################
        monitor_frame = tk.Frame(parent, bg='white')
        monitor_frame.grid(row=1, column=0, sticky=tk.W+tk.E+tk.N+tk.S)
        monitor_frame.columnconfigure(0, weight=4)

        ##### PLOTS #####
        self.num_rail_segments = 10  # Number of segments to split rail--for plotting
        trial_window = 30000

        sns.set_style('dark')
        self.color_vel = 'darkslategray'

        # self.fig, self.ax = plt.subplots(figsize=(8, 2))
        self.fig = Figure(figsize=(8, 2))
        self.ax = self.fig.add_subplot(1, 1, 1)
        self.ax.set_xlabel("Trial time (ms)")
        self.ax.set_ylabel("Relative velocity")
        self.ax.set_xlim(0, history)
        self.ax.set_ylim(-50, 50)
        self.vel_trace, = self.ax.plot([], [], c=self.color_vel)
        self.ax.axhline(y=0, linestyle='--', linewidth=1, color='0.5')

        self.plot_canvas = FigureCanvasTkAgg(self.fig, monitor_frame)
        self.fig.tight_layout()
        self.plot_canvas.show()
        self.plot_canvas.draw()
        self.plot_canvas.get_tk_widget().grid(row=0, column=0, rowspan=2, sticky=tk.W+tk.E+tk.N+tk.S)

        ##### SCOREBOARD #####
        scoreboard_frame = tk.Frame(monitor_frame, bg='white')
        scoreboard_frame.grid(row=0, column=1, padx=20, sticky=tk.N)

        self.manual = tk.BooleanVar()
        self.entry_start = tk.Entry(scoreboard_frame, width=entry_width)
        self.entry_end = tk.Entry(scoreboard_frame, width=entry_width)
        self.button_manual = tk.Button(scoreboard_frame, command=lambda: self.manual.set(True))
        tk.Label(scoreboard_frame, text="Session start:", bg='white', anchor=tk.W).grid(row=0, sticky=tk.W)
        tk.Label(scoreboard_frame, text="Session end:", bg='white', anchor=tk.W).grid(row=2, sticky=tk.W)
        self.entry_start.grid(row=1, sticky=tk.W)
        self.entry_end.grid(row=3, sticky=tk.W)
        self.button_manual.grid(row=4, sticky=tk.W+tk.E)

        self.scoreboard_objs = [
            self.entry_start,
            self.entry_end
        ]
        
        ###### GUI OBJECTS ORGANIZED BY TIME ACTIVE ######
        # List of components to disable at open
        self.obj_to_disable_at_open = [
            self.option_ports,
            self.button_update_ports,
            self.button_open_port,
            self.entry_session_dur,
            self.entry_trial_dur,
            self.entry_track_period,
            self.entry_track_steps,
            self.check_print
        ]
        # Boolean of objects in list above that should be enabled when time...
        self.obj_enabled_at_open = [False] * len(self.obj_to_disable_at_open)
        
        self.obj_to_enable_at_open = [
            self.button_close_port,
            self.button_start
        ]
        self.obj_to_disable_at_start = [
            self.button_close_port,
            self.entry_save,
            self.button_save_file,
            self.button_start,
            self.button_slack
        ]
        self.obj_to_enable_at_start = [
            self.button_stop
        ]

        # Update
        self.update_ports()
        self.update_instruments()

        ###### SESSION VARIABLES ######
        self.cam = None
        self.scale_fps = None
        self.parameters = collections.OrderedDict()
        self.ser = serial.Serial(timeout=1, baudrate=9600)
        self.start_time = ""
        self.counter = {}
        self.q = Queue()
        self.q_to_thread_rec = Queue()
        self.q_from_thread_rec = Queue()
        self.gui_update_ct = 0  # count number of times GUI has been updated

    def update_instruments(self):
        self.instrs = {}
        instrs = list_instruments()
        menu = self.option_instr['menu']
        menu.delete(0, tk.END)
        if instrs:
            for instr in instrs:
                menu.add_command(label=instr.name, command=lambda x=instr.name: self.var_instr.set(x))
                self.instrs[instr.name] = instr
            self.var_instr.set(instrs[0].name)
        else:
            self.var_instr.set("No instruments found")
            self.instrs = {}

            '''


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
