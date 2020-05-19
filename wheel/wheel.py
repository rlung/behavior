#!/usr/bin/env python

'''
Pupil-wheel

Creates GUI to control behavioral devices for recording video (pupil) and rotary
encoder (wheel). Script interfaces with Arduino microcontroller and cameras.

Outline of flow
1. Set parameters for experiment.
2. Establish serial connection with Arduino. Paremeters will be uploaded to
Arduino when this happens.
3. Set meta data for experiment and saved file location.
4. Start experiment!

'''

import sys
sys.path.insert(0, '../essentials/arduino-py/')
sys.path.insert(0, '../essentials/')

import tkinter as tk
import tkinter.ttk as ttk
import tkinter.font as tkFont
import tkinter.messagebox as tkMessageBox
import tkinter.filedialog as tkFileDialog
from tkinter.scrolledtext import ScrolledText
from PIL import ImageTk
import serial
import serial.tools.list_ports
import threading
from queue import Queue
import time
from datetime import datetime
import os
import h5py
import matplotlib
from matplotlib.figure import Figure
import arduino
import live_data_view
import pdb

matplotlib.use('TKAgg')


# Header to print with Arduino outputs
arduino_head = '  [a]: '

# Formatting
entry_width = 10
ew = 10  # Width of Entry UI
px = 15
py = 5
px1 = 5
py1 = 2

# Serial input codes
code_end = 0
code_wheel = 7

# Arduino code to save-file variable
arduino_events = {
    code_wheel: 'wheel'
}

# Events to count
# counter_ev =[]

# Path to this file
source_path = os.path.dirname(sys.argv[0])

class Main(tk.Frame):

    def __init__(self, parent):
        tk.Frame.__init__(self, parent)

        self.parent = parent
        parent.columnconfigure(0, weight=1)
        # parent.rowconfigure(1, weight=1)

        self.var_port = tk.StringVar()
        self.var_verbose = tk.BooleanVar()
        self.var_print_arduino = tk.BooleanVar()
        self.var_stop = tk.BooleanVar()

        # Counters
        # IMPORTANT: need to keep `counter_vars` in same order as `arduino_events`
        self.var_counter_wheel = tk.IntVar()
        counter_vars = [self.var_counter_wheel]
        self.counter = {ev: var_count for ev, var_count in zip(arduino_events.values(), counter_vars)}

        # Lay out GUI

        frame_setup = tk.Frame(parent)
        frame_setup.grid(row=0, column=0)
        frame_setup_col0 = tk.Frame(frame_setup)
        frame_setup_col1 = tk.Frame(frame_setup)
        frame_setup_col2 = tk.Frame(frame_setup)
        frame_setup_col0.grid(row=0, column=0, sticky='we')
        frame_setup_col1.grid(row=0, column=1, sticky='we')
        frame_setup_col2.grid(row=0, column=2, sticky='we')

        frame_monitor = tk.Frame(parent)
        frame_monitor.grid(row=1, column=0)
        # frame_monitor.rowconfigure(0, weight=1)
        # frame_monitor.columnconfigure(1, weight=1)

        # Session frame
        frame_params = tk.Frame(frame_setup_col0)
        frame_params.grid(row=0, column=0, padx=15, pady=5)
        frame_params.columnconfigure(0, weight=1)

        frame_session = tk.Frame(frame_params)
        frame_misc = tk.Frame(frame_params)
        frame_session.grid(row=0, column=0, sticky='e', padx=px, pady=py)
        frame_misc.grid(row=2, column=0, sticky='e', padx=px, pady=py)
 
        # Arduino frame
        frame_arduino = ttk.LabelFrame(frame_setup_col1, text='Arduino')
        frame_arduino.grid(row=0, column=0, padx=px, pady=py, sticky='we')
        frame_arduino1 = tk.Frame(frame_arduino)
        frame_arduino2 = tk.Frame(frame_arduino)
        frame_arduino1.grid(row=0, column=0, sticky='we', padx=px, pady=py)
        frame_arduino2.grid(row=1, column=0, sticky='we', padx=px, pady=py)
        frame_arduino2.grid_columnconfigure(0, weight=1)
        frame_arduino.grid_columnconfigure(0, weight=1)

        # Notes frame
        frame_notes = tk.Frame(frame_setup_col2)
        frame_notes.grid(row=0, sticky='wens', padx=px, pady=py)
        frame_notes.grid_columnconfigure(0, weight=1)

        # Saved file frame
        frame_file = tk.Frame(frame_setup_col2)
        frame_file.grid(row=1, column=0, padx=px, pady=py, sticky='we')
        frame_file.columnconfigure(0, weight=3)
        frame_file.columnconfigure(1, weight=1)

        # Start-stop frame
        frame_start = tk.Frame(frame_setup_col2)
        frame_start.grid(row=3, column=0, sticky='we', padx=px, pady=py)
        frame_start.grid_columnconfigure(0, weight=1)
        frame_start.grid_columnconfigure(1, weight=1)

        # Monitor frame
        frame_counter = tk.Frame(frame_monitor)
        frame_live = tk.Frame(frame_monitor)
        frame_counter.grid(row=0, column=0, padx=px, pady=py, sticky='we')
        frame_live.grid(row=1, column=0, padx=px, pady=py, sticky='wens')
        # frame_live.rowconfigure(0, weight=1)
        # frame_live.columnconfigure(1, weight=1)

        # Add GUI components

        ## frame_params

        ### frame_session
        ## UI for trial control
        self.entry_session_dur = ttk.Entry(frame_session, width=entry_width)
        tk.Label(frame_session, text='Session duration (ms): ', anchor='e').grid(row=0, column=0, sticky='e')
        self.entry_session_dur.grid(row=0, column=1, sticky='w')

        ### frame_misc
        ### UI for miscellaneous parameters
        self.entry_track_period = ttk.Entry(frame_misc, width=entry_width)
        tk.Label(frame_misc, text='Track period (ms): ', anchor='e').grid(row=2, column=0, sticky='e')
        self.entry_track_period.grid(row=2, column=1, sticky='w')

        ### frame_arduino
        ### UI for Arduino
        self.entry_serial_state = ttk.Entry(frame_arduino1, textvariable=self.var_port)
        self.button_arduino = ttk.Button(frame_arduino2, text='Set up', command=self.arduino_setup)
        tk.Label(frame_arduino1, text='State: ').grid(row=0, column=0, sticky='e')
        self.entry_serial_state.grid(row=0, column=1, sticky='we', padx=5)
        self.button_arduino.grid(row=0, column=0, pady=py, sticky='we')

        ## Notes
        self.entry_subject = ttk.Entry(frame_notes)
        self.entry_weight = ttk.Entry(frame_notes)
        self.scrolled_notes = ScrolledText(frame_notes, width=20, height=15)
        tk.Label(frame_notes, text='Subject: ').grid(row=0, column=0, sticky='e')
        tk.Label(frame_notes, text='Weight (g): ').grid(row=1, column=0, sticky='e')
        tk.Label(frame_notes, text='Notes:').grid(row=2, column=0, columnspan=2, sticky='w')
        self.entry_subject.grid(row=0, column=1, sticky='w')
        self.entry_weight.grid(row=1, column=1, sticky='w')
        self.scrolled_notes.grid(row=3, column=0, columnspan=2, sticky='wens')

        ## UI for saved file
        self.entry_save_file = ttk.Entry(frame_file)
        self.button_set_file = ttk.Button(frame_file, command=self.get_save_file)
        tk.Label(frame_file, text='File to save data:', anchor='w').grid(row=0, column=0, columnspan=2, sticky='w')
        self.entry_save_file.grid(row=1, column=0, sticky='wens')
        self.button_set_file.grid(row=1, column=1, sticky='e')

        icon_folder = ImageTk.PhotoImage(file=os.path.join(source_path, 'graphics/folder.png'))
        self.button_set_file.config(image=icon_folder)
        self.button_set_file.image = icon_folder
        
        ## Start frame
        self.button_start = ttk.Button(frame_start, text='Start', command=lambda: self.parent.after(0, self.start))
        self.button_stop = ttk.Button(frame_start, text='Stop', command=lambda: self.var_stop.set(True))
        self.button_start.grid(row=2, column=0, sticky='we')
        self.button_stop.grid(row=2, column=1, sticky='we')

        ## Counter frame
        tk.Label(frame_counter, text='Under construction').grid()

        ## Live frame
        data_types = {
            arduino_events[code_wheel]: 'line'
        }
        # tk.Label(frame_live, text='Also under construction').grid()
        self.live_view = live_data_view.LiveDataView(frame_live, x_history=30000, data_types=data_types, ylim=(-25, 50), xlabel='Time (ms)')
        
        ###### GUI OBJECTS ORGANIZED BY TIME ACTIVE ######
        # List of components to disable at open
        self.obj_to_disable_at_open = [
            self.entry_session_dur,
            self.entry_track_period,
        ]
        
        self.obj_to_enable_at_open = [
            self.button_start,
        ]
        self.obj_to_disable_at_start = [
            self.entry_subject,
            self.entry_weight,
            self.entry_save_file,
            self.button_set_file,
            self.button_start,
        ]
        self.obj_to_enable_at_start = [
            self.button_stop
        ]

        # Default values
        self.entry_session_dur.insert(0, 60000)
        self.entry_track_period.insert(0, 50)
        self.button_start['state'] = 'disabled'
        self.button_stop['state'] = 'disabled'

        ###### SESSION VARIABLES ######
        self.parameters = {}
        self.ser = serial.Serial(timeout=1, baudrate=9600)
        self.q_serial = Queue()

        self.update_serial()

    def get_save_file(self):
        ''' Opens prompt for file for data to be saved
        Runs when button beside save file is pressed.
        '''

        save_file = tkFileDialog.asksaveasfilename(
            initialdir=self.entry_save_file.get(),
            defaultextension='.h5',
            filetypes=[
                ('HDF5 file', '*.h5 *.hdf5'),
                ('All files', '*.*')
            ]
        )
        self.entry_save_file.delete(0, 'end')
        self.entry_save_file.insert(0, save_file)

    def gui_util(self, option):
        ''' Updates GUI components
        Enable and disable components based on events to prevent bad stuff.
        '''

        if option == 'uploaded':
            # Enable start objects
            for obj in self.obj_to_enable_at_open:
                obj['state'] = 'normal'
            for obj in self.obj_to_disable_at_open:
                obj['state'] = 'disabled'

        elif option == 'reset':
            for obj in self.obj_to_disable_at_open:
                obj['state'] = 'normal'
            for obj in self.obj_to_enable_at_open:
                obj['state'] = 'disabled'

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

    def update_serial(self):
        self.entry_serial_state['state'] = 'normal'
        self.entry_serial_state.delete(0, 'end')
        if self.ser.isOpen():
            self.entry_serial_state.insert(0, 'Uploaded to {}'.format(self.ser.port))
            self.gui_util('uploaded')
        else:
            self.entry_serial_state.insert(0, 'Waiting for parameters')
            self.gui_util('reset')
        self.entry_serial_state['state'] = 'readonly'

    def close_serial(self):
        self.ser.close()
        self.update_serial()

    def arduino_setup(self):
        # *** Gather parameters to send ***
        self.parameters = {
            'session_dur': int(self.entry_session_dur.get()),
            'track_period': int(self.entry_track_period.get()),
        }

        # Create new window
        self.nw = tk.Toplevel(self.parent)
        self.nw.bind('<Destroy>', lambda x: self.update_serial())  # "Throw away" '<Destroy' input on callback
        self.nw.grab_set()
        arduino.Arduino(self.nw, self)
    
    def start(self, code_start='E'):
        self.gui_util('start')

        # Create data file
        if self.entry_save_file.get():
            try:
                # Create file if it doesn't already exist, append otherwise ('a' parameter)
                self.data_file = h5py.File(self.entry_save_file.get(), 'a')
            except IOError:
                tkMessageBox.showerror('File error', 'Could not create file to save data.')
                self.gui_util('stop')
                self.gui_util('uploaded')
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
        subj = self.entry_subject.get() or '?'
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
        self.grp_exp['weight'] = int(self.entry_weight.get()) if self.entry_weight.get() else 0

        # *** Create file structure ***
        session_length = self.parameters['session_dur']
        nstepframes = 2 * session_length / float(self.entry_track_period.get())
        chunk_size = (2, 1)

        self.grp_behav = self.grp_exp.create_group('behavior')
        self.grp_behav.create_dataset(name='wheel', dtype='int32', shape=(2, int(nstepframes) * 1.1), chunks=chunk_size)

        # Reset counters
        for counter in self.counter.values(): counter.set(0)

        # Clear Queues
        for q in [self.q_serial]:
            with q.mutex:
                q.queue.clear()

        # Store session parameters into behavior group
        for key, value in self.parameters.items():
            self.grp_behav.attrs[key] = value

        # Create thread to scan serial
        suppress = [
            # code_wheel if self.var_suppress_print_movement.get() else None
        ]
        thread_scan = threading.Thread(
            target=scan_serial,
            args=(self.q_serial, self.ser, self.var_print_arduino.get(), suppress, code_end)
        )
        thread_scan.daemon = True    # Don't remember why this is here

        # Start session
        self.ser.flushInput()                                   # Remove data from serial input
        self.ser.write(code_start.encode())
        thread_scan.start()
        self.start_time = datetime.now()
        print('Session start {}'.format(self.start_time))
        self.grp_behav.attrs['start_time'] = self.start_time.strftime('%H:%M:%S')

        # Update GUI
        self.update_session()

    def update_session(self):
        # Checks Queue for incoming data from arduino. Data arrives as comma-separated values with the first element
        # ('code') defining the type of data.

        # Rate to update GUI
        # Should be faster than data coming in, ie tracking rate
        refresh_rate = 10

        # End on 'Stop' button (by user)
        if self.var_stop.get():
            self.var_stop.set(False)
            self.ser.write('0'.encode())
            print('User triggered stop, sending signal to Arduino...')

        # Watch incoming queue
        # Data has format: [code, ts, extra values]
        # Empty queue before leaving. Otherwise, a backlog will grow.
        while not self.q_serial.empty():
            code, ts, data = self.q_serial.get()
            print(code, ts, data)

            # End session
            if code == code_end:
                arduino_end = ts
                print('Arduino ended, finalizing data...')
                self.stop_session(arduino_end=arduino_end)
                return

            # Record data
            self.grp_behav[arduino_events[code]][:, self.counter[arduino_events[code]].get()] = [ts, data]
            self.counter[arduino_events[code]].set(self.counter[arduino_events[code]].get() + 1)

            # Update live view
            if code == code_wheel:
                self.live_view.update_view([ts, data], name=arduino_events[code_wheel])

        self.parent.after(refresh_rate, self.update_session)

    def stop_session(self, frame_cutoff=None, arduino_end=None):
        '''Finalize session
        Closes hardware connections and saves HDF5 data file. Resets GUI.
        '''

        end_time = datetime.now().strftime('%H:%M:%S')
        print('Session ended at ' + end_time)
        self.gui_util('stop')
        self.close_serial()

        # Finalize data
        print('Finalizing behavioral data')
        self.grp_behav.attrs['end_time'] = end_time
        self.grp_behav.attrs['arduino_end'] = arduino_end
        for ev in arduino_events.values():
            self.grp_behav[ev].resize((2, self.counter[ev].get()))
        self.grp_exp.attrs['notes'] = self.scrolled_notes.get(1.0, 'end')

        # Close HDF5 file object
        print('Closing {}'.format(self.data_file.filename))
        self.data_file.close()
        
        # Clear self.parameters
        self.parameters = {}

        print('All done!')


def scan_serial(q_serial, ser, print_arduino=False, suppress=[], code_end=0):
    '''Check serial for data
    Continually check serial connection for data sent from Arduino. Send data 
    through Queue to communicate with main GUI. Stop when `code_end` is 
    received from serial.
    '''

    if print_arduino: print('  Scanning Arduino outputs.')
    while 1:
        input_arduino = ser.readline().decode()
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
                if print_arduino: print('  Scan complete.')
                return


def main():
    # GUI
    root = tk.Tk()
    root.wm_title('Wheel')
    Main(root)
    root.grid()
    root.mainloop()


if __name__ == '__main__':
    main()
