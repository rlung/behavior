#!/usr/bin/env python

'''
Manage Arduino connection

Paremeters are sent to Arduino when serial connection is opened. Message 
contains parameters with prefix and specific delimiter set by code.

Will look for attributes from calling tkinter frame:
- ser
- var_verbose
- var_print_arduino
- parameters
'''

import sys
is_py2 = sys.version[0] == '2'

if is_py2:
    import Tkinter as tk
    import ttk
    import tkMessageBox
else:
    import tkinter as tk
    import tkinter.ttk as ttk
    import tkinter.messagebox as tkMessageBox    
import os
import time
from PIL import ImageTk
import serial
import serial.tools.list_ports


class Arduino(tk.Toplevel):
    def __init__(self, parent, main):
        self.parent = parent
        self.parent.title('Connect to Arduino')
        self.main = main
        try:
            self.verbose = main.var_verbose.get()
        except AttributeError:
            self.verbose = True
        try: self.print_arduino = self.var_print_arduino.get()
        except AttributeError: self.print_arduino = '  [a]: '
        try: self.parameters = self.main.parameters
        except AttributeError: self.parameters = {'a': 1, 'b': 2, 'c': 3}

        try:
            self.ser = self.main.ser
        except AttributeError:
            self.main.ser = serial.Serial(timeout=1, baudrate=9600)
            self.ser = self.main.ser

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
        self.button_open_port = ttk.Button(frame_arduino2, text='Open', command=self.open_serial)
        self.button_close_port = ttk.Button(frame_arduino2, text='Close', command=self.close_serial)
        tk.Label(frame_arduino1, text='Port: ').grid(row=0, column=0, sticky='e')
        tk.Label(frame_arduino1, text='State: ').grid(row=1, column=0, sticky='e')
        self.option_ports.grid(row=0, column=1, sticky='we', padx=5)
        self.button_update_ports.grid(row=0, column=2, pady=py)
        self.entry_serial_status.grid(row=1, column=1, columnspan=2, sticky='we', padx=px1)
        self.button_open_port.grid(row=0, column=0, pady=py, sticky='we')
        self.button_close_port.grid(row=0, column=1, pady=py, sticky='we')

        update_icon_file = 'refresh.png'
        if os.path.isfile(update_icon_file):
            icon_refresh = ImageTk.PhotoImage(file=update_icon_file)
            self.button_update_ports.config(image=icon_refresh)
            self.button_update_ports.image = icon_refresh

        self.button_close_port['state'] = 'disabled'
        self.entry_serial_status.insert(0, 'Closed')
        self.entry_serial_status['state'] = 'readonly'
        self.update_ports()

        if self.ser.isOpen():
            self.var_port.set(self.ser.port)
            self.gui_util('opened')

    def gui_util(self, opt):
        if opt == 'open':
            self.button_open_port['state'] = 'disabled'
            self.entry_serial_status['state'] = 'normal'
            self.entry_serial_status.delete(0, 'end')
            self.entry_serial_status.insert(0, 'Opening...')
            self.entry_serial_status['state'] = 'readonly'
        elif opt == 'opened':
            self.button_open_port['state'] = 'disabled'
            self.button_close_port['state'] = 'normal'
            self.entry_serial_status['state'] = 'normal'
            self.entry_serial_status.delete(0, 'end')
            self.entry_serial_status.insert(0, 'Opened')
            self.entry_serial_status['state'] = 'readonly'
        elif opt == 'close':
            self.button_close_port['state'] = 'disabled'
            self.entry_serial_status['state'] = 'normal'
            self.entry_serial_status.delete(0, 'end')
            self.entry_serial_status.insert(0, 'Closed')
            self.entry_serial_status['state'] = 'readonly'
            self.update_ports()
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

    def open_serial(self, delay=3, timeout=10, code_params='D', delim='+'):
        ''' Open serial connection to Arduino
        Executes when 'Open' is pressed

        Opens connection via serial. Parameters are sent when connection is 
        opened with prefix `code_params` and delimited by `delim`
        '''

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
            return
        else:
            # Serial opened successfully
            time.sleep(delay)
            if self.verbose: print('Connection to Arduino opened')

        # Handle opening message from serial
        if self.print_arduino:
            while self.ser.in_waiting:
                sys.stdout.write(self.print_arduino + ser_readline(self.ser))
        else:
            self.ser.flushInput()

        # Send parameters and make sure it's processed
        values = self.parameters.values()
        if self.verbose: print('Sending parameters: {}'.format(values))
        ser_write(self.ser, code_params + delim.join(str(s) for s in values))
        print(code_params + delim.join(str(s) for s in values))

        start_time = time.time()
        while 1:
            if self.ser.in_waiting:
                if self.print_arduino:
                    # Print incoming data
                    while self.ser.in_waiting:
                        sys.stdout.write(self.print_arduino + ser_readline(self.ser))
                print('Parameters uploaded to Arduino')
                print('Ready to start')
                self.gui_util('opened')
                return
            elif time.time() >= start_time + timeout:
                print('Error sending parameters to Arduino')
                print('Uploading timed out. Start signal not found.')
                self.close_serial()
                self.gui_util('close')
                return
    
    def close_serial(self):
        ''' Close serial connection to Arduino '''
        self.ser.close()
        self.gui_util('close')
        print('Connection to Arduino closed.')

class ArduinoTest(tk.Frame):
    def __init__(self, parent):
        self.parent = parent

        self.button = tk.Button(self.parent, text='Start', command=self.test)
        self.button.pack()

    def test(self):
        test_window = tk.Toplevel(self.parent)
        Arduino(test_window, self)

def ser_write(ser, code):
    '''Manage writing in Python 2 vs 3'''
    if (not is_py2) and (type(code) is not bytes):
        code = code.encode()
    ser.write(code)

def ser_readline(ser):
    '''Manage reading in Python 2 vs 3'''
    if is_py2:
        return ser.readline()
    else:
        return ser.readline().decode()

def main():
    root = tk.Tk()
    Arduino(root, tk.Frame)
    root.mainloop()


if __name__ == '__main__':
    main()
