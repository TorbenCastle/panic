

import tkinter as tk
from tkinter import scrolledtext , ttk 
import sys
from osc_client import Osc_client
from commands import Commands
from configparser import ConfigParser

#from panic_handler import osc_clients




# base popup window class
class PopupWindow(tk.Toplevel):
    def __init__(self, parent, gui_handler, title, geometry, popup_id):
        super().__init__(parent)
        
        self.gui_handler = gui_handler
        self.osc_clients = gui_handler.osc_clients
        # List to store all frames
        self.frames = []
        self.buttons = []
        # Set the title and geometry of the window
        self.title(title)
        self.geometry = geometry
        
        self.popup_id = popup_id
      
        # Main Frame
        self.main_frame = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        self.main_frame.pack(expand=True, fill="both")
        self.frames.append(self.main_frame)
        # Head Frame
        self.head_frame = tk.Frame(self.main_frame, bg="white")
        self.head_frame.pack(side="top", fill=tk.BOTH, expand=True)
        self.frames.append(self.head_frame)
                           
        # Mid Frame
        self.mid_frame = tk.Frame(self.main_frame, bg="white")
        self.mid_frame.pack(side="top", fill=tk.BOTH, expand=True)
        self.frames.append(self.mid_frame)
        # Bottom Frame
        self.bottom_frame = tk.Frame(self.main_frame, bg="white")
        self.bottom_frame.pack(side="bottom", fill=tk.BOTH, expand=True)
        # Load close button
        self.close_button = tk.Button(self.bottom_frame, text="Close", command=self.on_close)
        self.close_button.pack(side="right", pady=10, padx=10)

        self.frames.append(self.bottom_frame)
        
     

    def on_close(self):
        # Update the flag in the main GUI when the popup is closed
        if self.popup_id in self.gui_handler.popup_statuses:
            self.gui_handler.popup_statuses[self.popup_id] = 0
        self.destroy()

        

#popup window for edit clients
class EditClientWindow(PopupWindow):
    def __init__(self, parent, gui_handler, popup_id):
        super().__init__(parent, gui_handler, "EDIT CLIENTS", "500x700", popup_id)       
        
       
        self.selected_client = tk.StringVar()
        self.client_dropdown = ttk.Combobox(self.head_frame, textvariable=self.selected_client)
        self.client_dropdown["values"] = [client.get_name() for client in self.osc_clients]
        self.client_dropdown.pack(pady=10)
        self.client_dropdown.bind("<<ComboboxSelected>>", self.update_text_frames)
       

               # Data Frame (label_frame + entry_frame)
        self.data_frame = tk.Frame(self.mid_frame)
        self.data_frame.pack(side="left", expand=True)
        self.frames.append(self.data_frame)
        
        # Labeled frames in column 0
        labels = ["NAME:", "ID:", "IP:", "PORT:", "TYPE:"]
        for i, label_text in enumerate(labels):
             label_frame = tk.LabelFrame(self.data_frame, text=label_text)
             label_frame.grid(row=i, column=0, padx=10, pady=5, sticky="w" )  

        # Editable text frames in column 1
        self.text_vars = [tk.StringVar() for _ in range(5)]
        for i, text_var in enumerate(self.text_vars):
            entry_frame = tk.Entry(self.data_frame, textvariable=text_var)
            entry_frame.grid(row=i, column=1,columnspan=3, padx=10, pady=5, sticky="w" )
      
        save_button = tk.Button(self.bottom_frame, text="Save Changes", command=self.save_changes)
        save_button.pack(expand=True, pady=10)
        
        
              

        # Bind the window closing event to a method
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def update_text_frames(self, event):
         
        selected_name = self.selected_client.get()

        # Find the selected client
        selected_client = next((client for client in self.osc_clients if client.get_name() == selected_name), None)

        if selected_client:
            # Update text frames with client information
            self.text_vars[0].set(selected_client.get_name())
            self.text_vars[1].set(str(selected_client.get_client_id()))
            self.text_vars[2].set(selected_client.get_ip())
            self.text_vars[3].set(str(selected_client.get_port()))
            self.text_vars[4].set(selected_client.get_client_type())


    def save_changes(self):
        # Save changes to the selected client

        selected_name = self.selected_client.get()
        selected_client = next((client for client in self.osc_clients if client.get_name() == selected_name), None)

        if selected_client:
            client_new = selected_client
            # Update the client with the changes

            selected_client.set_name(self.text_vars[0].get())
            selected_client.set_client_id(int(self.text_vars[1].get()))
            selected_client.set_ip(self.text_vars[2].get())
            selected_client.set_port(int(self.text_vars[3].get()))
            selected_client.set_client_type(self.text_vars[4].get())

            # Optionally, update other elements in your GUI
            # Example: self.name_entry.delete(0, tk.END)
            # Example: self.name_entry.insert(0, selected_client.get_name())
            
            #print out edited client. True = existing client
            self.gui_handler.print_osc_client(selected_client , True)
            
        self.gui_handler.text_handler.write_config(self.osc_clients)
        self.gui_handler.update_labels()
        
class ShowDataPopup(PopupWindow):
    def __init__(self, parent, gui_handler, popup_id , name=None, size=None,  arg1=None, arg2=None, arg3=None , arg4=None):
        if(name == None):
            name = "Window " + str(popup_id)
        if(size == None):
            size = "400x500"
        
        super().__init__(parent, gui_handler, name , size, popup_id)
        
        self.arg1 = arg1
        self.arg2 = arg2
        self.arg3 = arg3
        self.arg4 = arg4
        self.text_handler = gui_handler.text_handler
        
        
        if arg1 == "read_file" and arg2 is not None:
            self.scrolled_text = scrolledtext.ScrolledText(self.mid_frame, wrap=tk.WORD, width=50, height=30)
            self.scrolled_text.grid(row=0, column=0, padx=10, pady=10)
            file_path = arg2  # Assuming arg2 is the path to the file
            data = self.gui_handler.text_handler.read_file(file_path)  # Assuming read_file returns a list
            ini_contents = []
            
            for entry in data:
                ini_contents.append(f"{entry}")

            self.scrolled_text.insert(tk.END, "\n".join(ini_contents))
            self.scrolled_text.configure(state=tk.DISABLED)    
        if arg1 == "close_program":
            
            # Edit Button
            exit_button = tk.Button(self.bottom_frame, text="Exit", command=gui_handler.exit_programm, width=5, height=2)
            exit_button.pack(side="left", pady=10, padx=(15, 0))
            self.close_button.config(text="Back", width=5, height=2)
            self.size = ("+100+300")
            
       
        
        

class GuiHandler:
    def __init__(self, root, osc_clients, color_1 , color_2 , color_3, text_handler, commands):
        self.root = root
        self.osc_clients = osc_clients       
        self.bg_color = color_1
        self.fg_color = color_2
        self.txt_color = color_3
        self.text_handler = text_handler
        self.commands = commands
         # Create an instance of the PopupWindow class
        
        self.clients_window = None
        self.log_window = None
        self.clear_window = None
        self.info_window = None
        self.exit_window = None        
        self.popup_statuses = {}
        
       
        
        
        self.client_buttons = []
        
        
        self.client_frame = []
        self.client_button = []
        
        self.main_button_list = []
        

        # Flag to track whether a popup is open
        self.popup_open = False
        self.logging = False
        
        self.create_gui()
        self.print_command("GUI initialized")
        self.next_command = None        
        self.osc_handler = None
        self.root.protocol("WM_DELETE_WINDOW", self.exit_programm)
        

    def set_osc_handler(self, osc_handler):
        self.osc_handler = osc_handler    

        
        
    def create_gui(self):
        self.root.title("INSTITUT FUER ZAHLENDREHER")
        self.root.geometry("800x550")
        self.root.resizable(True, True)  # Make the window resizable

        # Set the background color of the root window
        self.root.configure(bg=self.bg_color)

        # Main Frame
        self.main_frame = tk.Frame(self.root, bg=self.bg_color)
        self.main_frame.grid(row=0, column=0,  padx=35 , pady=50 , sticky="nsew")
        

        self.head_frame = tk.Frame(self.main_frame, bg=self.bg_color)
        self.head_frame.grid(row=0, column=0,sticky="nsew")
        
        self.mid_frame = tk.Frame(self.main_frame, bg=self.bg_color)
        self.mid_frame.grid(row=1, column=0,pady=10 , sticky="nsew")

        self.bot_frame = tk.Frame(self.main_frame, bg=self.bg_color)
        self.bot_frame.grid(row=2, column=0, pady=10 , sticky="nsew")


        # Create frames for each OSC client with type A
        self.client_A_buttons = tk.Frame(self.head_frame, bg=self.bg_color)
        self.client_A_buttons.grid(row=0, column=1, rowspan=1, columnspan=3, sticky="nsew")
        
        # Clear Button
        self.confirm_button = tk.Button(self.client_A_buttons, text="Confirm", command=lambda: self.button_function(0), bg="green", fg="black", width=6, height = 6)
        self.confirm_button.grid(row=1, column=0,padx=(0, 60), sticky="nsew")
        self.main_button_list.append(self.confirm_button)
        current_column = 1
        
        for client in self.osc_clients:
            if client.get_client_type() == 'trigger':
                self.button = tk.Button(self.client_A_buttons,width=6, height=6, text=client.name, command=lambda c=client: self.gui_ping_client(c), fg="black", bg="white" )
                self.button.grid(row=1, column=current_column,columnspan=2 ,  padx=(5 , 5) , pady=5)
                
                self.client_buttons.append(self.button)
                # Increment the column counter
                current_column += 2          
        
        self.osc_client_BC_frame = tk.Frame(self.mid_frame, bg=self.bg_color)
        self.osc_client_BC_frame.grid(row=0, column=1, rowspan=1, columnspan=1,padx=4 , sticky="nsew")
        current_row = 0
        for client in self.osc_clients:
            if client.get_client_type() in ['station', 'gma3']:  # Use 'in' to check against multiple values
                self.button = tk.Button(self.osc_client_BC_frame, text=client.name, command=lambda c=client: self.gui_ping_client(c), fg="black", bg="white" , width=8)
                self.button.grid(row=current_row, column=1, padx=(3 , 3) , pady=5)
                self.client_buttons.append(self.button)
                current_row += 1          
       

        
        self.scroll_frame = tk.Frame(self.mid_frame, bg=self.bg_color)
        self.scroll_frame.grid(row=0, column=0 , sticky="nsew")
        
        # Scrollable Text Window
        self.output_text = scrolledtext.ScrolledText(self.scroll_frame, wrap=tk.WORD, width=80, height=10, bg=self.bg_color, fg="black")
        self.output_text.grid(row=0, rowspan = 6, column=0, columnspan=6, pady=(0, 5), sticky="nsew")

        # Command Line
        self.command_line = tk.Entry(self.scroll_frame, bg="#CCCCCC", fg="black", width=5 )  
        self.command_line.grid(row=6, column=0, columnspan=6, pady=(0, 5), sticky="nsew")

        # Send Button
        self.send_button = tk.Button(self.scroll_frame, text="Send", command=lambda: self.button_function(1), bg=self.bg_color, fg="black", width=4 )
        self.send_button.grid(row=6, column=5, sticky="e" )
        self.main_button_list.append(self.send_button)   
        
        # Edit Button
        self.edit_button = tk.Button(self.bot_frame, text="Edit", command=lambda: self.button_function(2), bg=self.bg_color, fg="black", width=15)
        self.edit_button.grid(row=0, column=0, pady=5, padx=5, sticky="nsew", columnspan=2)
        self.main_button_list.append(self.edit_button)
     

        # Info Button
        self.info_button = tk.Button(self.bot_frame, text="Info", command=lambda: self.button_function(3), bg=self.bg_color, fg="black")
        self.info_button.grid(row=0, column=2, pady=5, padx=20, sticky="nsew", columnspan=1)
        self.main_button_list.append(self.info_button)  
        
        # Show Log Button
        self.show_log_button = tk.Button(self.bot_frame, text="Show Log", command=lambda: self.button_function(4), bg=self.bg_color, fg="black")
        self.show_log_button.grid(row=1, column=2, pady=5, padx=20, sticky="nsew", columnspan=1)
        self.main_button_list.append(self.show_log_button)
        
        # Show ToggleLog Button

        self.toggle_log_button = tk.Button(self.bot_frame, text="Toggle cmd log", command=lambda: self.button_function(5), bg=self.bg_color, fg="black")
        self.toggle_log_button.grid(row=2, column=2, pady=5, padx=20, sticky="nsew", columnspan=1)
        self.main_button_list.append(self.toggle_log_button)
       
        
        # Exit Button
        self.exit_button = tk.Button(self.bot_frame , text="EXIT", command=lambda: self.button_function(6), bg=self.bg_color, fg="black", width= 10 , heigh= 3)
        self.exit_button.grid(row=2, column=3, rowspan=2, columnspan=2, pady=10, padx=200,  sticky="es")
        self.main_button_list.append(self.exit_button)

    def start_gui(self):
        self.root.mainloop()       
    

    def print_command_log(self, command):
        if self.logging:
            self.output_text.insert(tk.END, f"{command}\n")
            self.output_text.see(tk.END)
            
    def print_command(self, command):
        self.output_text.insert(tk.END, f"{command}\n") 
        self.output_text.see(tk.END)
            
    def send_command_line(self):
        command = self.command_line.get()  # Get the command from the entry
        if command != None:
            
            self.print_command(command)
            self.osc_handler.gui_command(command)            
            
        
        self.command_line.delete(0, tk.END)
        
    def gui_ping_all_clients(self):
        self.print_command("Ping all clients")
        self.osc_handler.request_all_command()
        
    def gui_ping_client(self, client):
        self.print_command(f"Ping {client.get_name()} at {client.get_ip()}:{client.get_port()}")
        
        self.osc_handler.request_command(client)
     
        
    #we need the value only to set the online status
    def gui_update_button_status(self, client ,  command):
        client_button_id = client.get_client_id() - 1
        
        #only update the button if the clients button was not pressed
        if client.get_client_type() == "trigger":
            if client.get_button_was_pressed_state():
                self.client_buttons[client_button_id].configure(bg="red")
                return
        
        if command == "online":self.client_buttons[client_button_id].configure(bg="white")
            
        if command == "offline":self.client_buttons[client_button_id].configure(bg="#555555")
          
        if command == "clear":
            if client.get_online_status: self.client_buttons[client_button_id].configure(bg="white")
            else: self.client_buttons[client_button_id].configure(bg="#555555")
            
        if command == "requested":self.client_buttons[client_button_id].configure(bg="#00FFFF")
           
           
        
         
                
        #button list: 0 = confirm_button, 1 = send, 2 = edit, 3 = info, 4 = show log, 5 = exit
        #functions.
    def button_function(self, button_id):
        
        if button_id == 0:
            
            # send a stop / confirm command to all stations
            self.print_command_log("sending stop command to all stations")
            self.osc_handler.confirm_command(0)
            
            #self.show_popup("stop")      
            
        #send the commandline to commandline_handler           
        elif button_id == 1:
            
            self.send_command_line()
            
        elif button_id == 2:
            self.print_command_log("Edit clients")
            self.show_popup("Edit_clients")
            
        elif button_id == 3:
            self.print_command_log("Info")
            self.show_popup("Info")
            
        elif button_id == 4:
            #self.simpledialog.messagebox.showinfo(self.text_handler("log"))
            self.show_popup("Log")
            
        elif button_id == 5:
            self.toggle_logging()  
            if not self.logging:
                self.toggle_log_button.config(relief=tk.RAISED)
            else:
                self.toggle_log_button.config(relief=tk.SUNKEN)
            
        elif button_id == 6:            
             self.show_popup("Exit")
         
            
        else:
            self.print_command("Invalid button ID")
     

    def toggle_logging(self):
    
        if self.logging:
            self.logging = False
            self.print_command("Logging off")
        else:
            self.logging = True
            self.print_command("Logging on")
            
    def update_labels(self):
        for i in range(0,3):
            self.client_buttons[i].configure(text=self.osc_clients[i].get_name())
        
    #create popup windows here.
    def show_popup(self, popup_id, client = None):
        if popup_id not in self.popup_statuses or not self.popup_statuses[popup_id]:
            # Open the popup if it's not open or closed
            self.popup_statuses[popup_id] = 1  # Set status to open
        # Only open a new popup if one is not already open
            if(popup_id == "Clear"):
                self.print_command_log("Clear")
                f#self.clear_window = ShowDataPopup(self.root, self, popup_id)
                #self.clear_window.grab_set()  # Make the popup modal
                #self.log_window.transient(self.root)  # Set the popup as transient to the main window
                #self.clear_window.mainloop()
       
            elif(popup_id == "Edit_clients"):
            
                self.clients_window = EditClientWindow(self.root, self, popup_id)
                #self.clients_window.grab_set()  # Make the popup modal
                self.clients_window.transient(self.root)  # Set the popup as transient to the main window
                
                
            elif(popup_id == "Log"):
                # Create the popup id = 1
                self.log_window = ShowDataPopup(self.root, self, popup_id, "Log data", "600x800", "read_file", "log", None , self.text_handler )
                #self.log_window.grab_set()  # Make the popup modal
                #self.log_window.transient(self.root)  # Set the popup as transient to the main window
                
                
            elif(popup_id == "Info"):
                self.info_window = ShowDataPopup(self.root, self, popup_id ,"INFO", "600x800", "read_file", "info", None , self.text_handler)
                self.info_window.grab_set()  # Make the popup modal
                self.info_window.transient(self.root)  # Set the popup as transient to the main window
                
                
            elif(popup_id == "Client_Info"):
                self.client_info_window = ShowDataPopup(self.root, self, popup_id,client)
                self.client_info_window.grab_set()  # Make the popup modal
                self.client_info_window.transient(self.root)  # Set the popup as transient to the main window
                





            elif(popup_id == "Exit"):
                self.exit_window = ShowDataPopup(self.root, self, popup_id, "CONFIRMATION", "200x120", "close_program")
                self.exit_window.grab_set()  # Make the popup modal
                #self.exit_window.transient(self.root)  # Set the popup as transient to the main window
 
        else:
            self.close_popup(popup_id)
            
    def close_popup(self, popup_id):
        if popup_id in self.popup_statuses and self.popup_statuses[popup_id]:
            # Close the popup if it's open
            self.popup_statuses[popup_id] = 0  # Set status to closed

            # Destroy or close the popup window based on the popup_id
            if popup_id == "Clear":
                "self.clear_window.destroy()"
                self.print_command_log("Clear")
            elif popup_id == "Edit clients":
                self.clients_window.destroy()
            elif popup_id == "Log":
                self.log_window.destroy()
            elif popup_id == "Info":
                self.info_window.destroy() 

#update the status of the buttons
    def set_pressed_status(self, client_button_id , value):
        client_button_id -= 1 # get the right index
        
        if(value == True):
            self.client_buttons[client_button_id].configure(bg="red")
            
        else:
            #if the client is online set the button to white if online or dark grey if offline
            if(self.osc_clients[client_button_id].get_online_status() == True):
                self.client_buttons[client_button_id].configure(bg="white")
            else:
                self.client_buttons[client_button_id].configure(bg="#555555")
            
    def print_osc_client(self, client, old):
        if old:self.print_command("Client saved")
        else: self.print_command("Client added")
        self.print_command(f"Name:    {client.get_name()} ID: {client.get_client_id()} type: {client.get_client_type()} ")
        self.print_command(f"Address: {client.get_ip()}:{client.get_port()}")    
    
        

    def exit_programm(self):
             
        try:
            
            self.osc_handler.set_exit_flag()
            self.osc_handler.handle_thread.join()
                        
            self.osc_handler.server.shutdown()
            print("programm closed")
            sys.exit(0)
        except Exception as e:
            print(f"Error: {e}")
            
            
    
