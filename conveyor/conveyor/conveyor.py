#!/usr/bin/env python

'''
Odor presentation

Creates GUI to control behavioral and imaging devices for in vivo calcium
imaging. Script interfaces with Arduino microcontroller and imaging devices.

TO-DO:
- disable manual stepper at start
- add pre/post trial periods
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
from slackclient import SlackClient
import time
from datetime import datetime
from datetime import timedelta
import os
import sys
import h5py
import numpy as np

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

# Styling
px = 15
py = 5
px1 = 5
py1 = 2

opts_frame0 = {'pady': 15, }
opts_frame_sep = {'padx': 50, 'pady': 15, }
opts_entry10 = {'width': 10, 'justify': 'right'}

# Serial input codes
code_end = 0
code_trial_start = 1
code_trial_end = 2
code_at_mouse = 3
code_to_mouse = 5
code_at_home = 6
code_move = 7
code_next_trial = 8

# Serial output codes
code_step_forward = '3'
code_step_backward = '4'

events = ['trial_start', 'trial_end', 'at_mouse', 'to_mouse', 'at_home', 'movement']


class InputManager(ttk.Frame):

    def __init__(self, parent):
        ttk.Frame.__init__(self, parent)

        # GUI layout
        # parent
        # - frame_setup
        #   + frame_params
        #     ~ frame_session
        #     ~ frame_misc
        #   + hardware_frame
        #     ~ frame_preview
        #     ~ frame_arduino
        #     ~ frame_debug
        #   + frame_file
        #   + slack_frame
        # - monitor_frame
        #   + (figure)
        #   + scoreboard_frame

        self.parent = parent
        parent.columnconfigure(0, weight=1)

        # Variables
        self.var_pre_session = tk.IntVar()
        self.var_post_session = tk.IntVar()
        self.var_trial_num = tk.IntVar()
        self.var_pre_stim = tk.IntVar()
        self.var_post_stim = tk.IntVar()
        self.var_stim_dur = tk.IntVar()
        self.var_iti = tk.IntVar()
        self.var_image_all = tk.BooleanVar()
        self.var_img_ttl_dur = tk.IntVar()
        self.var_track_period = tk.IntVar()
        self.var_port = tk.StringVar()
        self.var_serial_status = tk.StringVar()
        self.var_verbose = tk.BooleanVar()
        self.var_print_arduino = tk.BooleanVar()
        self.var_subject = tk.StringVar()
        self.var_stop = tk.BooleanVar()
        self.var_counter_trial_start = tk.IntVar()
        self.var_counter_trial_end = tk.IntVar()
        self.var_counter_at_mouse = tk.IntVar()
        self.var_counter_to_mouse = tk.IntVar()
        self.var_counter_at_home = tk.IntVar()
        self.var_counter_movement = tk.IntVar()

        self.var_pre_session.set(30000)
        self.var_post_session.set(30000)
        self.var_trial_num.set(15)
        self.var_pre_stim.set(0)
        self.var_post_stim.set(0)
        self.var_stim_dur.set(10000)
        self.var_iti.set(60000)
        self.var_img_ttl_dur.set(100)
        self.var_track_period.set(50)
        self.var_serial_status.set('Closed')

        # Lay out GUI

        frame_setup = ttk.Frame(parent)
        frame_setup.grid(row=0, column=0, **opts_frame0)
        frame_setup_col0 = ttk.Frame(frame_setup)
        frame_setup_col1 = ttk.Frame(frame_setup)
        frame_setup_col2 = ttk.Frame(frame_setup)
        frame_setup_col0.grid(row=0, column=0, sticky='we')
        frame_setup_col1.grid(row=0, column=1, sticky='we')
        frame_setup_col2.grid(row=0, column=2, sticky='we')

        # Session frame
        frame_params = ttk.Frame(frame_setup_col0)
        frame_params.grid(row=0, column=0, padx=15, pady=5)
        frame_params.columnconfigure(0, weight=1)

        frame_session = ttk.Frame(frame_params)
        frame_misc = ttk.Frame(frame_params)
        frame_session.grid(row=0, column=0, sticky='e', padx=px, pady=py)
        frame_misc.grid(row=2, column=0, sticky='e', padx=px, pady=py)
 
        # Arduino frame
        frame_arduino = ttk.LabelFrame(frame_setup_col1, text='Arduino')
        frame_arduino.grid(row=1, column=0, padx=px, pady=py, sticky='we')
        frame_arduino1 = ttk.Frame(frame_arduino)
        frame_arduino2 = ttk.Frame(frame_arduino)
        frame_arduino1.grid(row=0, column=0, sticky='we', padx=px, pady=py)
        frame_arduino2.grid(row=1, column=0, sticky='we', padx=px, pady=py)
        frame_arduino2.grid_columnconfigure(0, weight=1)
        frame_arduino2.grid_columnconfigure(1, weight=1)
        frame_arduino.grid_columnconfigure(0, weight=1)
        
        # Debug frame
        frame_debug = ttk.LabelFrame(frame_setup_col1, text='Debug')
        frame_debug.grid(row=2, column=0, padx=px, pady=py, sticky='we')
        frame_debug.grid_columnconfigure(0, weight=1)

        # Info frame
        frame_info = ttk.Frame(frame_setup_col2)
        frame_info.grid(row=0, sticky='wens', padx=px, pady=py)
        frame_info.grid_columnconfigure(0, weight=1)

        # Saved file frame
        frame_file = ttk.Frame(frame_setup_col2)
        frame_file.grid(row=1, column=0, padx=px, pady=py, sticky='we')
        frame_file.columnconfigure(0, weight=3)
        frame_file.columnconfigure(1, weight=1)

        # Slack frame
        frame_slack = ttk.Frame(frame_setup_col2)
        frame_slack.grid(row=2, column=0, sticky='we', padx=px, pady=py)
        frame_slack.grid_columnconfigure(0, weight=3)
        frame_slack.grid_columnconfigure(1, weight=1)

        # Start-stop frame
        frame_start = ttk.Frame(frame_setup_col2)
        frame_start.grid(row=3, column=0, sticky='we', padx=px, pady=py)
        frame_start.grid_columnconfigure(0, weight=1)
        frame_start.grid_columnconfigure(1, weight=1)

        ## Separator frame
        tk.Frame(parent, height=1, bg='gray').grid(row=1, column=0, sticky='we', **opts_frame_sep)

        ## Monitor frame
        frame_monitor = ttk.Frame(parent)
        frame_monitor.grid(row=2, column=0, **opts_frame0)
        frame_setup_col0 = ttk.Frame(frame_monitor)
        frame_setup_col0.grid(row=0, column=0, sticky='we')

        ### Stepper frame
        frame_stepper = ttk.Frame(frame_monitor)
        frame_stepper.grid(row=0, column=0, sticky='we')
        frame_stepper.grid_columnconfigure(0, weight=1)  # Fills into frame

        ### Counter frame
        frame_counter = ttk.Frame(frame_monitor)
        frame_counter.grid(row=0, column=1, sticky='we')
        frame_counter.grid_columnconfigure(0, weight=1)

        # Add GUI components

        ## frame_params

        ### frame_session
        ## UI for trial control
        self.entry_pre_session = ttk.Entry(frame_session, textvariable=self.var_pre_session, **opts_entry10)
        self.entry_post_session = ttk.Entry(frame_session, textvariable=self.var_post_session, **opts_entry10)
        self.entry_trial_num = ttk.Entry(frame_session, textvariable=self.var_trial_num, **opts_entry10)
        self.entry_pre_stim = ttk.Entry(frame_session, textvariable=self.var_pre_stim, **opts_entry10)
        self.entry_post_stim = ttk.Entry(frame_session, textvariable=self.var_post_stim, **opts_entry10)
        self.entry_stim_dur = ttk.Entry(frame_session, textvariable=self.var_stim_dur, **opts_entry10)
        self.entry_iti = ttk.Entry(frame_session, textvariable=self.var_iti, **opts_entry10)
        ttk.Label(frame_session, text='Presession time (ms): ', anchor='e').grid(row=0, column=0, sticky='e')
        ttk.Label(frame_session, text='Postsession time (ms): ', anchor='e').grid(row=1, column=0, sticky='e')
        ttk.Label(frame_session, text='Number of trials: ', anchor='e').grid(row=2, column=0, sticky='e')
        ttk.Label(frame_session, text='Prestim time (ms): ', anchor='e').grid(row=3, column=0, sticky='e')
        ttk.Label(frame_session, text='Poststim time (ms): ', anchor='e').grid(row=4, column=0, sticky='e')
        ttk.Label(frame_session, text='Stim duration (ms): ', anchor='e').grid(row=5, column=0, sticky='e')
        ttk.Label(frame_session, text='ITI (ms): ', anchor='e').grid(row=6, column=0, sticky='e')
        self.entry_pre_session.grid(row=0, column=1, sticky='w')
        self.entry_post_session.grid(row=1, column=1, sticky='w')
        self.entry_trial_num.grid(row=2, column=1, sticky='w')
        self.entry_pre_stim.grid(row=3, column=1, sticky='w')
        self.entry_post_stim.grid(row=4, column=1, sticky='w')
        self.entry_stim_dur.grid(row=5, column=1, sticky='w')
        self.entry_iti.grid(row=6, column=1, sticky='w')

        self.entry_pre_stim['state'] = 'disabled'
        self.entry_post_stim['state'] = 'disabled'

        ### frame_misc
        ### UI for miscellaneous parameters
        self.check_image_all = ttk.Checkbutton(frame_misc, variable=self.var_image_all)
        self.entry_image_ttl_dur = ttk.Entry(frame_misc, textvariable=self.var_img_ttl_dur, **opts_entry10)
        self.entry_track_period = ttk.Entry(frame_misc, textvariable=self.var_track_period, **opts_entry10)
        ttk.Label(frame_misc, text='Image everything: ', anchor='e').grid(row=0, column=0, sticky='e')
        ttk.Label(frame_misc, text='Imaging TTL duration (ms): ', anchor='e').grid(row=1, column=0, sticky='e')
        ttk.Label(frame_misc, text='Track period (ms): ', anchor='e').grid(row=2, column=0, sticky='e')
        self.check_image_all.grid(row=0, column=1, sticky='w')
        self.entry_image_ttl_dur.grid(row=1, column=1, sticky='w')
        self.entry_track_period.grid(row=2, column=1, sticky='w')

        ### frame_arduino
        ### UI for Arduino
        self.option_ports = ttk.OptionMenu(frame_arduino1, self.var_port, [])
        self.button_update_ports = ttk.Button(frame_arduino1, command=self.update_ports)
        self.entry_serial_status = ttk.Entry(frame_arduino1, textvariable=self.var_serial_status, state='readonly')
        self.button_open_port = ttk.Button(frame_arduino2, text='Open', command=self.open_serial)
        self.button_close_port = ttk.Button(frame_arduino2, text='Close', command=self.close_serial)
        ttk.Label(frame_arduino1, text='Port: ').grid(row=0, column=0, sticky='e')
        ttk.Label(frame_arduino1, text='State: ').grid(row=1, column=0, sticky='e')
        self.option_ports.grid(row=0, column=1, sticky='we', padx=5)
        self.button_update_ports.grid(row=0, column=2, pady=py)
        self.entry_serial_status.grid(row=1, column=1, columnspan=2, sticky='w', padx=px1)
        self.button_open_port.grid(row=0, column=0, pady=py, sticky='we')
        self.button_close_port.grid(row=0, column=1, pady=py, sticky='we')

        icon_refresh = ImageTk.PhotoImage(file='graphics/refresh.png')
        self.button_update_ports.config(image=icon_refresh)
        self.button_update_ports.image = icon_refresh

        self.button_close_port['state'] = 'disabled'

        ## UI for debug options
        self.check_verbose = ttk.Checkbutton(frame_debug, text=' Verbose', variable=self.var_verbose)
        self.check_print = ttk.Checkbutton(frame_debug, text=' Print Arduino output', variable=self.var_print_arduino)
        self.check_verbose.grid(row=0, column=0, padx=px1, sticky='w')
        self.check_print.grid(row=1, column=0, padx=px1, sticky='w') 

        ## Notes
        self.scrolled_notes = ScrolledText(frame_info, width=20, height=15)
        ttk.Label(frame_info, text='Subject: ', anchor='e').grid(row=0, column=0)
        ttk.Entry(frame_info, textvariable=self.var_subject).grid(row=0, column=1)
        ttk.Label(frame_info, text='Notes:').grid(row=1, column=0, columnspan=2, sticky='w')
        self.scrolled_notes.grid(row=2, column=0, columnspan=2, sticky='wens')

        ## UI for saved file
        self.entry_file = ttk.Entry(frame_file)
        self.button_save_file = ttk.Button(frame_file, command=self.get_save_file)
        ttk.Label(frame_file, text='File to save data:', anchor='w').grid(row=0, column=0, columnspan=2, sticky='w')
        self.entry_file.grid(row=1, column=0, sticky='wens')
        self.button_save_file.grid(row=1, column=1, sticky='e')

        icon_folder = ImageTk.PhotoImage(file='graphics/folder.png')
        self.button_save_file.config(image=icon_folder)
        self.button_save_file.image = icon_folder
        
        
        ## Slack
        ttk.Label(frame_slack, text='Slack address: ', anchor='w').grid(row=0, column=0, sticky='we')
        self.entry_slack = ttk.Entry(frame_slack)
        self.button_slack = ttk.Button(frame_slack, command=lambda: slack_msg(self.entry_slack.get(), 'Test', test=True))
        self.entry_slack.grid(row=1, column=0, sticky='wens')
        self.button_slack.grid(row=1, column=1, sticky='e')

        icon_slack = ImageTk.PhotoImage(file='graphics/slack.png')
        self.button_slack.config(image=icon_slack)
        self.button_slack.image = icon_slack

        ## Start frame
        self.button_start = ttk.Button(frame_start, text='Start', command=lambda: self.parent.after(0, self.start))
        self.button_stop = ttk.Button(frame_start, text='Stop', command=lambda: self.var_stop.set(True))
        self.button_start.grid(row=2, column=0, sticky='we')
        self.button_stop.grid(row=2, column=1, sticky='we')

        self.button_start['state'] = 'disabled'
        self.button_stop['state'] = 'disabled'

        ## Stepper frame
        self.button_to_mouse = ttk.Button(frame_stepper, text = '<', command=lambda: ser_write(self.ser, code_step_forward))
        self.button_to_home = ttk.Button(frame_stepper, text = '>', command=lambda: ser_write(self.ser, code_step_backward))
        ttk.Label(frame_stepper, text='Move stepper', anchor='center').grid(row=0, column=0, columnspan=2, sticky='we')
        self.button_to_mouse.grid(row=1, column=0, sticky='e')
        self.button_to_home.grid(row=1, column=1, sticky='w')

        self.button_to_mouse['state'] = 'disabled'
        self.button_to_home['state'] = 'disabled'

        ## Counter frame
        ttk.Label(frame_counter, text='Trials: ', anchor='e').grid(row=0, column=0, sticky='e')
        ttk.Entry(frame_counter, textvariable=self.var_counter_trial_start, state='readonly', **opts_entry10).grid(row=0, column=1, sticky='w')
        
        ###### GUI OBJECTS ORGANIZED BY TIME ACTIVE ######
        # List of components to disable at open
        self.obj_to_disable_at_open = [
            self.entry_pre_session,
            self.entry_post_session,
            self.entry_trial_num,
            # self.entry_pre_stim,
            # self.entry_post_stim,
            self.entry_stim_dur,
            self.entry_iti,
            self.check_image_all,
            self.entry_image_ttl_dur,
            self.entry_track_period,
            self.option_ports,
            self.button_update_ports,
            self.button_open_port,
        ]
        # Boolean of objects in list above that should be enabled when time...
        self.obj_enabled_at_open = [False] * len(self.obj_to_disable_at_open)
        
        self.obj_to_enable_at_open = [
            self.button_close_port,
            self.button_start,
            self.button_to_mouse,
            self.button_to_home,
        ]
        self.obj_to_disable_at_start = [
            self.button_close_port,
            self.check_print,
            self.entry_file,
            self.button_save_file,
            self.button_start,
            self.button_slack,
            self.button_to_mouse,
            self.button_to_home,
        ]
        self.obj_to_enable_at_start = [
            self.button_stop
        ]

        # Update
        self.update_ports()

        # Other variables
        self.parameters = collections.OrderedDict()
        self.ser = serial.Serial(timeout=1, baudrate=9600)
        self.q_serial = Queue()
        self.gui_update_ct = 0  # count number of times GUI has been updated
        self.counter = {
            ev: var_count
            for ev, var_count in zip(events, [
                self.var_counter_trial_start,
                self.var_counter_trial_end,
                self.var_counter_at_mouse,
                self.var_counter_to_mouse,
                self.var_counter_at_home,
                self.var_counter_movement,
            ])
        }

    def update_ports(self):
        ports_info = list(serial.tools.list_ports.comports())
        ports = [port.device for port in ports_info]
        ports_description = [port.description for port in ports_info]

        menu = self.option_ports['menu']
        menu.delete(0, 'end')
        if ports:
            for port, description in zip(ports, ports_description):
                menu.add_command(label=description, command=lambda com=port: self.var_port.set(com))
            self.var_port.set(ports[0])
        else:
            self.var_port.set('No ports found')

    def get_save_file(self):
        ''' Opens prompt for file for data to be saved
        Runs when button beside save file is pressed.
        '''

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

    def gui_util(self, option):
        ''' Updates GUI components
        Enable and disable components based on events to prevent bad stuff.
        '''

        if option == 'open':
            for i, obj in enumerate(self.obj_to_disable_at_open):
                # Determine current state of object                
                if obj['state'] == 'disabled':
                    self.obj_enabled_at_open[i] = False
                else:
                    self.obj_enabled_at_open[i] = True
                
                # Disable object
                obj['state'] = 'disabled'

            self.var_serial_status.set('Opening...')

        elif option == 'opened':
            # Enable start objects
            for obj in self.obj_to_enable_at_open:
                obj['state'] = 'normal'

            self.var_serial_status.set('Opened')

        elif option == 'close':
            for obj, to_enable in zip(self.obj_to_disable_at_open, self.obj_enabled_at_open):
                if to_enable: obj['state'] = 'normal'         # NOT SURE IF THAT'S CORRECT
            for obj in self.obj_to_enable_at_open:
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

    def open_serial(self, delay=3, timeout=5, code_params='D'):
        ''' Open serial connection to Arduino
        Executes when 'Open' is pressed
        '''

        # Disable GUI components
        self.gui_util('open')

        # Open serial
        self.ser.port = self.var_port.get()
        try:
            self.ser.open()
        except serial.SerialException as err:
            # Error during serial.open()
            err_msg = err.args[0]
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
                sys.stdout.write(arduino_head + ser_readline(self.ser))
        else:
            self.ser.flushInput()

        # Define parameters
        # NOTE: Order is important here since this order is preserved when sending via serial.
        self.parameters['pre_session'] = self.var_pre_session.get()
        self.parameters['post_session'] = self.var_post_session.get()
        self.parameters['trial_num'] = self.var_trial_num.get()
        # self.parameters['prestim'] = self.var_pre_stim.get()
        # self.parameters['prestim'] = self.var_post_stim.get()
        self.parameters['stim_duration'] = self.var_stim_dur.get()
        self.parameters['iti'] = self.var_iti.get()
        self.parameters['img_all'] = int(self.var_image_all.get())
        self.parameters['img_ttl_dur'] = self.var_img_ttl_dur.get()
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
                print('Uploading timed out. Start signal not found.')
                self.gui_util('close')
                self.close_serial()
                return
    
    def close_serial(self):
        ''' Close serial connection to Arduino '''
        self.ser.close()
        self.gui_util('close')
        print('Connection to Arduino closed')
    
    def start(self, code_start='E'):
        self.gui_util('start')

        # Clear Queues
        for q in [self.q_serial]:
            with q.mutex:
                q.queue.clear()

        # Create data file
        if self.entry_file.get():
            try:
                # Create file if it doesn't already exist ('x' parameter)
                self.data_file = h5py.File(self.entry_file.get(), 'x')
            except IOError:
                tkMessageBox.showerror('File error', 'Could not create file to save data.')
                self.gui_util('stop')
                self.gui_util('open')
                self.gui_util('opened')
                return
        else:
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
                self.grp_exp = self.data_file.create_group('{}/{}'.format(self.var_subject.get(), date + file_index))
            except (RuntimeError, ValueError):
                index += 1
                file_index = '-' + str(index)
            else:
                break

        self.grp_behav = self.grp_exp.create_group('behavior')

        n_trials = self.parameters['trial_num']
        session_length = (
            self.parameters['pre_session'] + self.parameters['post_session'] + 
            self.parameters['iti'] * self.parameters['trial_num']
            # (self.parameters['pre_stim'] + self.parameters['pre_stim'] + self.parameters['iti']) * self.parameters['trial_num']
        )
        nstepframes = 2 * session_length / self.var_track_period.get()
        chunks = (2, 1)

        self.grp_behav.create_dataset(name='trial_start', dtype='uint32', shape=(2, n_trials, ), chunks=chunks)
        self.grp_behav.create_dataset(name='trial_end', dtype='uint32', shape=(2, n_trials, ), chunks=chunks)
        self.grp_behav.create_dataset(name='at_mouse', dtype='uint32', shape=(2, n_trials, ), chunks=chunks)
        self.grp_behav.create_dataset(name='to_mouse', dtype='uint32', shape=(2, n_trials, ), chunks=chunks)
        self.grp_behav.create_dataset(name='at_home', dtype='uint32', shape=(2, n_trials, ), chunks=chunks)
        self.grp_behav.create_dataset(name='movement', dtype='int32', shape=(2, nstepframes), chunks=chunks)

        # self.counter = {ev: 0 for ev in events}
        for counter in self.counter.values(): counter.set(0)

        # Store session parameters into behavior group
        for key, value in self.parameters.items():
            self.grp_behav.attrs[key] = value

        # Create thread to scan serial
        thread_scan = threading.Thread(
            target=scan_serial,
            args=(self.q_serial, self.ser, self.var_print_arduino.get())
        )

        # Run session
        self.start_time = datetime.now()
        print('Session start ~ {}'.format(self.start_time.strftime('%H:%M:%S')))
        self.grp_behav.attrs['start_time'] = str(self.start_time)

        self.ser.flushInput()                                   # Remove data from serial input
        ser_write(self.ser, code_start)                                     # Start signal for Arduino
        thread_scan.start()

        # Update GUI
        self.update_session()

    def update_session(self):
        # Checks Queue for incoming data from arduino. Data arrives as comma-separated values with the first element
        # ('code') defining the type of data.

        refresh_rate = 10  # Rate to update GUI. Should be faster than data coming in, eg tracking rate

        # Code-event dictionary
        event = {
            code_at_mouse: 'at_mouse',
            code_to_mouse: 'to_mouse',
            code_at_home: 'at_home',
            code_move: 'movement',
        }

        # End on 'Stop' button (by user)
        if self.var_stop.get():
            self.var_stop.set(False)
            ser_write(self.ser, '0')
            print('User triggered stop.')

        # Incoming queue has format:
        #   [code, ts [, extra values...]]
        while not self.q_serial.empty():
            code, ts, data = self.q_serial.get()

            # stop_session is called only when Arduino sends stop code
            if code == code_end:
                print('Stopping session.')
                self.stop_session(arduino_end=ts)
                return

            # Record event
            if code not in [code_next_trial]:
                # self.grp_behav[event[code]][:, self.counter[event[code]]] = [ts, data]
                # self.counter[event[code]] += 1
                self.grp_behav[event[code]][:, self.counter[event[code]].get()] = [ts, data]
                self.counter[event[code]].set(self.counter[event[code]].get() + 1)

            # Update GUI
            if code == code_next_trial:
                self.var_next_trial_time.set((self.start_time + timedelta(milliseconds=ts)).strftime('%H:%M:%S'))
            elif code == code_trial_start:
                self.var_counter_trial_start.set(self.var_counter_trial_start.get() + 1)

        self.parent.after(refresh_rate, self.update_session)

    def stop_session(self, frame_cutoff=None, arduino_end=None):
        '''Finalize session
        Closes hardware connections and saves HDF5 data file. Resets GUI.
        '''
        end_time = datetime.now().strftime('%H:%M:%S')
        print('Session ended at ' + end_time)
        self.gui_util('stop')
        self.close_serial()

        print('Writing behavioral data into HDF5 group {}'.format(self.grp_behav.name))
        self.grp_behav.attrs['end_time'] = end_time
        self.grp_behav.attrs['subject'] = self.var_subject.get()
        self.grp_behav.attrs['notes'] = self.scrolled_notes.get(1.0, 'end')
        self.grp_behav.attrs['arduino_end'] = arduino_end

        for ev in events:
            # self.grp_behav[ev].resize((2, self.counter[ev]))
            self.grp_behav[ev].resize((2, self.counter[ev].get()))

        # Close HDF5 file object
        print('Closing {}'.format(self.data_file.filename))
        self.data_file.close()
        
        # Slack that session is done
        if self.entry_slack.get():
            slack_msg(self.entry_slack.get(), 'Session ended')
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
        bot_username = 'Conveyor bot'
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


def scan_serial(q_serial, ser, print_arduino=False, suppress=[]):
    #  Continually check serial connection for data sent from Arduino. Stop when '0 code' is received.

    code_end = 0

    if print_arduino: print('  Scanning Arduino outputs.')
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
                sys.stdout.write(arduino_head + input_arduino)
            if input_arduino: q_serial.put(input_split)
            if input_split[0] == code_end:
                if print_arduino: print("  Scan complete.")
                return


def main():
    # GUI
    root = tk.Tk()
    root.wm_title('Conveyor')
    InputManager(root)
    root.grid()
    root.mainloop()


if __name__ == '__main__':
    main()
