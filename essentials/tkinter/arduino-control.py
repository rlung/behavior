#!/usr/bin/env python

import Tkinter as tk
import tkMessageBox
import serial
import serial.tools.list_ports



class GUI(tk.Frame):
    def __init__(self, parent):
        tk.Frame.__init__(self, parent)

        px = 15
        py = 5
        px1 = 5
        py1 = 2

        # Lay out GUI
        frame_arduino = tk.Frame(parent)
        frame_arduino.grid(row=0, column=0)

        self.port_var = tk.StringVar()
        self.entry_serial_status = tk.Entry(frame_arduino)
        self.option_ports = tk.OptionMenu(frame_arduino, self.port_var, [])
        tk.Label(frame_arduino, text='Serial port: ').grid(row=0, column=0, sticky='e', padx=px1)
        tk.Label(frame_arduino, text='Serial status: ').grid(row=1, column=0, sticky='e', padx=px1)
        self.option_ports.grid(row=0, column=1, columnspan=2, sticky=tk.W+'e', padx=px1)
        self.entry_serial_status.grid(row=1, column=1, columnspan=2, sticky='w', padx=px1)

        self.entry_serial_status.insert(0, 'Closed')
        self.entry_serial_status['state'] = 'normal'
        self.entry_serial_status['state'] = 'readonly'

        self.button_open_port = tk.Button(frame_arduino, text='Open', command=self.open_serial)
        self.button_close_port = tk.Button(frame_arduino, text='Close', command=self.close_serial)
        self.button_update_ports = tk.Button(frame_arduino, text='Update', command=self.update_ports)
        self.button_open_port.grid(row=2, column=0, pady=py)
        self.button_close_port.grid(row=2, column=1, pady=py)
        self.button_update_ports.grid(row=2, column=2, pady=py)

        # Initialize serial object
        self.ser = serial.Serial(timeout=1, baudrate=9600)

        # Group GUI objects
        self.obj_to_disable_at_open = [
            self.button_open_port,
            self.button_update_ports,
        ]
        self.obj_to_enable_when_open = [
            self.button_close_port,
        ]

        # Boolean of objects states at open
        # Useful if object states are volatile, but state should be returned 
        # once serial is closed.
        self.obj_enabled_at_open = [False] * len(self.obj_to_disable_at_open)

        # Default states
        self.button_close_port['state'] = 'disabled'

        # Functions to run at start
        self.update_ports()

    def open_serial(self):
        '''Open serial connection to Arduino
        Executes when 'Open' button is pressed.
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
            self.gui_util('opened')
            print('Connection to Arduino opened.')

    def close_serial(self):
        '''Close serial connection to Arduino
        Executes when 'Close' button is pressed.
        '''
        self.ser.close()
        self.gui_util('close')
        print('Connection to Arduino closed.')

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


def main():
    root = tk.Tk()
    root.wm_title('Arduino control')
    GUI(root)
    root.grid()
    root.mainloop()


if __name__ == '__main__':
    main()
