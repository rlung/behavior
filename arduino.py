#!/usr/bin/env python

'''
Manage Arduino connection

Paremeters are sent to Arduino when serial connection is opened. Message 
contains parameters with prefix and specific delimiter set by code.

Will look for attributes from parent:
- var_print_arduino
- parameters
'''


import argparse
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.messagebox as tkMessageBox
import pathlib
import sys
import os
import time
from PIL import ImageTk
import serial
import serial.tools.list_ports


code_last_param = 271828

class Arduino(tk.Frame):
    def __init__(self, parent, main_window=None, verbose=False, print_arduino=False, params={'a': 1, 'b': 2}):
        super().__init__()   # https://stackoverflow.com/questions/576169/understanding-python-super-with-init-methods
        self.parent = parent
        self.main_window = main_window if main_window else self.parent

        self.print_arduino = '  [a]: ' if print_arduino else False
        self.verbose = verbose
        self.parameters = params
        self.var_uploaded = tk.BooleanVar(name='uploaded')

        self.ser = serial.Serial(timeout=1, write_timeout=3, baudrate=9600)

        self.var_port = tk.StringVar()

        px = 15
        py = 5
        px1 = 5
        frame_arduino1 = ttk.Frame(self.parent)
        frame_arduino2 = ttk.Frame(self.parent)
        frame_arduino1.grid(row=0, column=0, sticky='we', padx=px, pady=py)
        frame_arduino2.grid(row=1, column=0, sticky='we', padx=px, pady=py)
        frame_arduino1.grid_columnconfigure(1, weight=1)
        frame_arduino2.grid_columnconfigure(0, weight=1)
        frame_arduino2.grid_columnconfigure(1, weight=1)
        self.parent.grid_columnconfigure(0, weight=1)

        self.option_ports = ttk.OptionMenu(frame_arduino1, self.var_port, [])
        self.button_update_ports = ttk.Button(frame_arduino1, text='u', command=self.update_ports)
        self.entry_serial_status = ttk.Entry(frame_arduino1)
        self.button_settings = ttk.Button(frame_arduino2, text='Settings', command=self.settings)
        self.button_open_port = ttk.Button(frame_arduino2, text='Upload', command=self.open_serial)
        self.button_close_port = ttk.Button(frame_arduino2, text='Reset', command=self.close_serial)
        tk.Label(frame_arduino1, text='Port: ').grid(row=0, column=0, sticky='e')
        tk.Label(frame_arduino1, text='State: ').grid(row=1, column=0, sticky='e')
        self.option_ports.grid(row=0, column=1, sticky='we', padx=5)
        self.button_update_ports.grid(row=0, column=2, pady=py)
        self.entry_serial_status.grid(row=1, column=1, columnspan=2, sticky='we', padx=px1)
        self.button_settings.grid(row=0, column=0, columnspan=2, pady=py, sticky='we')
        self.button_open_port.grid(row=1, column=0, pady=py, sticky='we')
        self.button_close_port.grid(row=1, column=1, pady=py, sticky='we')

        update_icon_file = os.path.join(pathlib.Path(__file__).parent.absolute(), 'graphics/refresh.png')
        if os.path.isfile(update_icon_file):
            icon_refresh = ImageTk.PhotoImage(file=update_icon_file)
            self.button_update_ports.config(image=icon_refresh)
            self.button_update_ports.image = icon_refresh

        self.button_close_port['state'] = 'disabled'
        self.entry_serial_status.insert(0, 'Waiting for parameters')
        self.entry_serial_status['state'] = 'readonly'
        self.update_ports()

        # if self.ser.isOpen():
        #     self.var_port.set(self.ser.port)
        #     self.gui_util('uploaded')

    def gui_util(self, opt):
        def relabel(label, txt):
            label['state'] = 'normal'
            label.delete(0, 'end')
            label.insert(0, txt)
            label['state'] = 'readonly'
        if opt == 'upload':
            self.button_open_port['state'] = 'disabled'
            relabel(self.entry_serial_status, 'Uploading...')
        elif opt == 'uploaded':
            self.button_open_port['state'] = 'disabled'
            self.button_close_port['state'] = 'normal'
            relabel(self.entry_serial_status, 'Uploaded')
            self.var_uploaded.set(True)
        elif opt == 'resetting':
            self.button_close_port['state'] = 'disabled'
            relabel(self.entry_serial_status, 'Resetting connection...')
        elif opt == 'reset':
            relabel(self.entry_serial_status, 'Waiting for parameters')
            self.update_ports()
            self.var_uploaded.set(False)
        else:
            print('Unknown utility option')
        self.parent.update_idletasks()


    def update_ports(self):
        '''Update available ports'''

        # Get available ports
        ports_info = list(serial.tools.list_ports.comports())
        ports = [port.device for port in ports_info]
        ports_description = [port.description for port in ports_info]

        # Update GUI
        menu = self.option_ports['menu']
        menu.delete(0, 'end')
        if ports:
            for port, description in zip(ports, ports_description):
                menu.add_command(label=description, command=lambda com=port: self.var_port.set(com))
            self.var_port.set(ports[0])
            self.button_open_port['state'] = 'normal'
        else:
            self.var_port.set('No ports found')
            self.button_open_port['state'] = 'disabled'

    def settings(self):
        '''Sets serial settings'''

        win_settings = tk.Toplevel(self.main_window)
        tk.Label(win_settings, text='Under construction').grid()

    def open_serial(self, delay=3, timeout=10, code_params='D', delim='+'):
        ''' Open serial connection to Arduino
        Executes when 'Open' is pressed

        Opens connection via serial. Parameters are sent when connection is 
        opened with prefix `code_params` and delimited by `delim`
        '''

        self.gui_util('upload')

        # Open serial
        self.ser.port = self.var_port.get()
        try:
            self.ser.open()
        except serial.SerialException as err:
            # Error during serial.open()
            err_msg = err.args[0]
            tkMessageBox.showerror('Serial error', err_msg)
            print(f'Serial error: {err_msg}')
            self.close_serial()
            return
        else:
            # Serial opened successfully
            time.sleep(delay)
            if self.verbose: print('Connection to Arduino opened')

        # Handle opening message from serial
        if self.print_arduino:
            while self.ser.in_waiting:
                sys.stdout.write(self.print_arduino + self.ser.readline().decode())
        else:
            self.ser.flushInput()

        # Send parameters to Arduino
        values = list(self.parameters.values())
        if type(values[0]) == tk.IntVar:
            values = [x.get() for x in values]
        values.append(code_last_param)
        ser_msg = code_params + delim.join(str(s) for s in values)
        if self.verbose: print('Sending parameters as `{}`'.format(ser_msg))
        try:
            self.ser.write(ser_msg.encode())
        except serial.serialutil.SerialTimeoutException:
            # Write timeout
            print('Error uploading parameters: write timeout')
            self.close_serial()
            return

        # Ensure parameters processed
        start_time = time.time()
        while 1:
            if time.time() >= start_time + timeout:
                print('Error uploading parameters: start signal not found')
                self.close_serial()
                return
            if self.ser.in_waiting:
                upload_code = self.ser.readline().decode().rstrip()
                if self.print_arduino:
                    # Print incoming data
                    while self.ser.in_waiting:
                        sys.stdout.write(self.print_arduino + self.ser.readline().decode())
                if upload_code != '0':
                    print(f'Error uploading parameters: exit code {upload_code}')
                    self.close_serial()
                    return
                else:
                    print('Parameters uploaded to Arduino')
                    print('Ready to start')
                    self.gui_util('uploaded')
                    return
    
    def close_serial(self):
        ''' Close serial connection to Arduino '''
        print('Closing serial connection')
        self.gui_util('resetting')
        self.ser.close()
        self.gui_util('reset')
        print('Connection to Arduino closed')


class Sample(ttk.Frame):
    def __init__(self, parent, verbose=False):
        self.parent = parent

        self.var_param1 = tk.IntVar(name='param1')
        self.var_param2 = tk.IntVar(name='param2')
        self.params = {'a': self.var_param1, 'b': self.var_param2}

        self.var_param1.set(10000)
        self.var_param2.set(50)

        frame_params = ttk.Frame(self.parent)
        frame_arduino = ttk.Frame(self.parent)
        frame_params.grid(row=0, column=0)
        frame_arduino.grid(row=0, column=1)

        entry_param1 = ttk.Entry(frame_params, textvariable=self.var_param1)
        entry_param2 = ttk.Entry(frame_params, textvariable=self.var_param2)
        entry_param1.grid(row=0, column=0)
        entry_param2.grid(row=1, column=0)

        self.Arduino = Arduino(frame_arduino, verbose=verbose, params=self.params)

        self.obj_to_disable_on_upload = [child for child in frame_params.winfo_children()]
        self.Arduino.var_uploaded.trace_add('write', self.toggle_gui)

    def toggle_gui(self, var, indx, mode):
        new_state = 'disable' if self.parent.getvar(var) else 'normal'
        for obj in self.obj_to_disable_on_upload:
            obj['state'] = new_state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()

    root = tk.Tk()
    Sample(root, verbose=args.verbose)
    root.mainloop()


if __name__ == '__main__':
    main()
