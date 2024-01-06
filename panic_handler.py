
#!/usr/bin/env python3.11
from configparser import ConfigParser

import tkinter as tk
from tkinter import SE, ttk, messagebox
from tkinter import scrolledtext
from pythonosc import osc_message_builder, udp_client, dispatcher
from pythonosc import udp_client
from pythonosc.osc_server import ThreadingOSCUDPServer
import threading
import queue
import time
import os
import queue
import commands
from gui import GuiHandler
from datetime import datetime




# The OscServerHandler class is used to handle OSC messages from a specific IP address and port.
# The class is initialized with a dispatcher and a server address and port.
# The dispatcher is used to map OSC addresses to handler functions.
# The server is used to listen for OSC messages on the specified address and port.
class Osc_command_handler:
    def __init__(self, dispatcher, address, port, clients, gui, commands ,text_handler):
        
        self.address = address  # Fix typo in the attribute name
        self.port = port
        self.osc_clients = clients
        self.gui = gui  # Store the gui as an attribute
        self.commands = commands  # Store the Commands instance as an attribute
        self.text_handler = text_handler
        
        #i dont know yet, why i cant start the server somewhere else - fix it later
        self.dispatcher = dispatcher
        self.dispatcher.map("/cmd" , self.receive_command)
        self.server = ThreadingOSCUDPServer((address, port), dispatcher)        
        self.handle_thread = None
        self.exit_flag = False
        
        self.receive_queue = queue.Queue()
        self.send_queue = queue.Queue()
        
        self.command_list= ["status", "stop", "ping", "status", "confirm", "response", "trigger", "debug" , "special"]
        

        
        self.c_station = None  # Variable to store the C-type station
        #list of all trigger clients
        self.trigger_osc_clients = []
        for client in self.osc_clients:
            if client.client_type == "trigger":
                self.trigger_osc_clients.append(client)
        #list of all station clients      
        self.station_osc_clients = []
        for client in self.osc_clients:
            if client.client_type != "station":
                self.station_osc_clients.append(client)

        self.status_timer = None  # Initialize the status timer to None
        self.ping_timer = time.time()  # Initialize the ping timer to None
        self.client_ping_index = 0
        
        self.gui.print_command("Server started")
        time.sleep(0.4)
        self.gui.print_command(f"LISTENING ON {self.address}:{self.port}")
        time.sleep(0.4)
        self.gui.print_command(f"Number of clients: {len(self.osc_clients)} loaded")
        time.sleep(0.4)
        self.gui.print_command("Type 'help' for a more info")
        time.sleep(0.4)
        self.gui.print_command("Sending Ping to all clients")
        self.request_all_command(0)
        time.sleep(0.4)
        self.gui.print_command("Waiting for clients")

###########################   MAIN PART FROM COMMAND HANDLING   ####################
    def handle_loop(self):
       
        while not self.exit_flag:
                
            #check if a incoming message is to handle
            if not self.receive_queue.empty():
                self.receive_queue_function()
                
                
            #check if a outgoing message has to be sent    
            if not self.send_queue.empty(): 
                self.send_queue_function()
                
            
            #after a timer f 60 seconds send a ping command to the next client
            self.ping_single_client()
            
            #check if a client is requested and if the timeout is reached
            self.check_requested_clients()
            
            time.sleep(0.005)
            
       
                    
    #listen to incoming messages, the dispatcher is calling this function and its filter is "/cmd"
    def receive_command(self, *args):
        self.gui.print_command_log(f"Received command: \"/cmd\",{args}") #print the full received command to the gui commandline
        #awaiting a command with 3 arguments or 2 arguments for gma3
        if len(args) == 2:
            for i in self.osc_clients:
                if i.client_type == "gma3":
                    client = i
                    command = str(args[1])
        elif len(args) == 3:
            
            #exeption handling for incoming arguments
            try:
            # Try casting to int to get client ID
                client_id = int(args[1])
            except (ValueError, TypeError):
                return False
            try:
                command = str(args[2])
            except (ValueError, TypeError):
                return False
       
            client = self.osc_clients[client_id-1]
        else:
            self.gui.print_command_log("Receive error: Invalid number of arguments")
            return False          
        # its easier to save only the client id in the queue, because the client object is not pickable
        if client:            
            self.receive_queue.put((client.client_id , command))
            
            
        else:
            self.gui.print_command(f"Client not found for ID {client_id}")
            return False
        
          
    #get tuples from received commands from queue
    def receive_queue_function(self):
       #handle the received commands queue
        received_msg = self.receive_queue.get()     
        client_id = int(received_msg[0])         
        input_command = str(received_msg[1])
        client = self.osc_clients[client_id-1]
        
        self.handle_command(client , input_command) 
        
     # This function is to handle the received commands
    
    def handle_command(self, client ,  input_command):
                                
        if input_command == "ping":
            self.response_command(client)
            
        elif input_command == "trigger":           
           self.send_status_command(client)           
     
        elif input_command == "confirm":            
            self.confirm_command(client.get_client_id())
            
        elif input_command == "released":            
            self.released_command(client)
            
        elif "debug" in input_command:            
            self.gui.print_command(f"debug command from {client.get_name()}")   
            
        else:
            
            self.gui.print_command(f"Message from: {client.get_name()}: {input_command}")    


    #sending commands from queue
    def send_queue_function(self):
        #read out send queue and send the command to the client of the corrosponding ID in the send_msg
        send_msg = self.send_queue.get()
                        
        client = self.osc_clients[int(send_msg[0])-1]
        

        if(client.client_type != "gma3"):
          
            value = int(send_msg[1])
            command = send_msg[2]
        else:            
            value = send_msg[0]
            command = send_msg[1]
            
        
        client.send_data(value , command)
        #self.gui.print_command_log(f"Sending {command}  command to {client.name}")
        
###########################    COMMAND HANDLE LOGIC  ############################

    #if a type A client sends a status command, start a function on all type B and C clients
    #the server will set a status for the type A client and send it to the gui in the set_status function
    def send_status_command(self, trigger_client):
        
        trigger_id = trigger_client.get_client_id()
        
        if(trigger_client.get_button_was_pressed_state() == True):
            self.gui.print_command_log("Client is already triggered")
            return #exit the function if the client is already triggered
        self.gui.print_command(f"Button pressed on {trigger_client.get_name()}")
        # get a timestamp for a triggerd client and write into log file
        local_time = datetime.now()
        format_time = local_time.strftime("%Y-%m-%d %H:%M")
        self.text_handler.write_log(f"{format_time} Button pressed on {trigger_client.get_name()}")
        
        #set a timer for the status of the client
        self.start_time = time.time()
        
        #self.osc_clients[trigger_client_id].status_timer = time.time()
        #save the sending client ID to trigger the corrosponding function on the type B and C clients
            
        self.trigger_client.set_status(True)#set the triggerd status to true and update the gui
                    
        #send to all station clients a status update with the id value from trigger client
        for client in self.station_osc_clients:
            if client.get_client_type() == "station": # send trigger command to all receiving stations   
                self.send_queue.put(client.get_command(trigger_id, "trigger"))
                   
              

    #if a the server gets a "corfirm" command it                        
    #Send "stop" command to all B and C stations and update the gui     
    def confirm_command(self, sender_id):
        #get the name of the client that sent the confirm command
        if(sender_id == 0):
            sender = "server"
        else:
            sender = self.osc_clients[sender_id-1].name
            
        for client in self.osc_clients:
            if client.client_type == "trigger":
                if client.get_button_was_pressed_state() == True:
                    break # if a type A client is triggered, continue with the function
                else:
                    self.gui.print_command(f"{sender} confirmed without a reason!")
                    return # if no type A client is triggered, exit the function
       
            
        #get the elapsed time since a trigger  was set
        if self.status_timer is not None:
            elapsed_time = time.time() - self.status_timer
            self.start_time = None
            minutes = int(elapsed_time / 60)
            seconds = int(elapsed_time % 60)
            self.text_handler.write_log(f"Status confirmed by {sender} after {minutes}:{seconds}") 
            
        #send a stop command to all type B and C clients to stop a status funciton.
        for client in self.station_osc_clients:
            if client.get_client_type() == "station":
                self.send_queue.put(client.get_command(client.client_id , "stop"))
        
        for client in self.trigger_osc_clients:
            if client.get_client_type() == "trigger":
                if client.get_button_was_pressed_state() == True:
                    self.set_status(client.client_id, False)
                       
  
   

    #this function is called if a response command is received from a client
    def response_command(self, client):
        
        #if the client is offline, and comes online.
        if client.get_online_status() == False and client.get_requested_flag() == False:
            client.set_online_status(True)
            self.gui.gui_update_online_status(client, True)
            self.gui.print_command_log(f"Client {client.name} is now online")
            
        elif(client.get_requested_flag() == True):
            self.gui.print_command(f"{client.name} is online, ping:{client.get_response_time()} ms")           
            client.set_requested_flag(False)
            self.gui.gui_update_online_status(client, True)
            client.set_online_status(True)  
            

    
    #if a button was released. (it can set a grandma3 seq to off, or handle other commands.)  
    #at the moment only the t1 button can toggle osc effect sequences.      
    def released_command(self, client):
        if client.client_id == 1:
            self.send_queue.put(self.osc_clients[6].get_command(client.client_id  , "released"))
            
    #this function is to ping a client
    def request_command(self, client):      
        client.set_requested_flag(True)
        client_command = client.get_command(client.client_id , "ping")
        self.gui.gui_update_online_status(client, True) # can be false in gui
        self.send_queue.put(client_command)
        
        
   
    #request all clients except station id  "i"
    def request_all_command(self, i ):
        for client in self.osc_clients:
            if client.client_id != i:
                self.request_command(client)
            
 
    #this function is used if a type A client sends a status command to update the client status and gui
    def set_status(self, client, val):
                
            client.set_button_was_pressed_state(val)            
            self.gui.set_status(client.client_id , val)
       
        
    #this function is used if a stop command is received to clear the status form type A clients
    #TODO clear the last recieved status in the network
    def clear_status(self):
        for client in self.trigger_osc_clients:            
            self.set_status(client.client_id, False)
     
    #send a ping command to the next client in the list, to check if a client is online,
    #after 60 seconds the next client is pinged
    def ping_single_client(self):
        elapsed_time = time.time() - self.ping_timer
        
        if elapsed_time >= 60:  # 60 seconds 
            # Reset the timer
            
            self.ping_timer = time.time()
            self.request_command(self.osc_clients[self.client_ping_index])
            self.client_ping_index += 1
            self.ping_timer += 1
            #start the list from 0 if the last client is reached
            if self.client_ping_index == len(self.osc_clients):
                self.client_ping_index = 0 
    
    #in the main loop, we check if a client request flag is true, if the client is requested, ping the client.            
    def check_requested_clients(self):
        for client in self.osc_clients:
                if client.get_requested_flag() == True:
                    client.check_ping_timeout()
           

    #get a client by value name , id or ip.
    def get_client(self, search_value):
        #if the search value is an int, search for the client id
        if isinstance(search_value, int):
            client_value = "client_id"
        elif isinstance(search_value, str):
            if search_value.count('.') == 4:
               client_value = "ip"
            else:
                client_value = "name"
        for client in self.osc_clients:
            if getattr(client, client_value) == search_value:
                return client        
            return None            
        
################################# START GUI COMMAND #################################

#this function is called when a command is entered in the gui commandline
    def gui_command(self, command):
        args = command.split()
        
        #commandline commands start with: "cmd" will send to client with the corrosponding ID, a command
        # "cmd 1 ping" will send a ping command to client 1
        if (args[0] == "cmd"):                
            if len(args) == 3:
                # get the client by name, id or ip
                client = self.get_client(args[1])                    
                if client:
                    cmd_line_client_id = client.client_id
                    command = str(args[2])                    
                    
                    if command in self.command_list:
                        if "trigger" in command:
                            client.send_data(1 , command) # always sends a the trigger station id from t1
                                
                        #debug test for t1
                        elif "debug" in command:
                            self.osc_clients[0].send_data(1 , "debug")# always debug t1 button
                                  
                        elif "ping" in command:
                            self.send_queue.put(client.get_command(cmd_line_client_id, command))
                            
                                
                        elif "confirm" in command:                            
                            self.send_queue.put(client.get_command(cmd_line_client_id, command))   
                                                            
                                                      
                        elif "stop" in command:                            
                            self.send_queue.put(client.get_command(cmd_line_client_id, command))                                
                                
                        elif "special" in command:                            
                            self.osc_clients[0].send_data(1 , "special")
                            
                        else:
                            self.gui.print_command(f"Send command not found")
                            return
                            
                        self.gui.print_command(f"Send test: {command} to ID:{cmd_line_client_id} - {client.name} ")
                    else:
                        self.gui.print_command("Command not found")
                else:
                    self.gui.print_command("Error: Client ID out of range:")
            else:   
                self.gui.print_command("Error: Missing arguments for set command")
                    
        elif len(args) >= 1 <= 2:
                                    
            

            if  "help" in args[0] and args[1] == None:
                self.gui.print_command("--------------------------------------")
                self.gui.print_command("Send command ID")                   
                self.gui.print_command(f"\"clients\" return all clients")                   
                self.gui.print_command(f"\"cmd ID send_command\" send a test command to an id") 
                self.gui.print_command(f"Type \"help cmd\" for more info") 
                self.gui.print_command(f"\"test\" will do nothing")
            elif "help" in args[0] and "cmd" in args[1]:
                self.gui.print_command("--------------------------------------")
                self.gui.print_command("Send commands are:")
                self.gui.print_command(self.commands.all_send_commands)
                self.gui.print_command("For example type \"cmd 1 ping\" into the commandline to send a ping") 
            

            #if commandline input is "clients" print all clients, or print a specific value if a second argument is given
            if  "clients" in args[0] and args[1] == None:
                self.gui.print_command("--------------------------------------")
                self.gui.print_command(f"All registered clients:") 
                for client in self.osc_clients:
                    self.gui.print_command(f"Name:      {client.name}")
                    self.gui.print_command(f"ID:        {client.client_id} Type: {client.client_type}")
                    self.gui.print_command(f"IP/Port:   {client.ip}:{client.port}")
                    
            
            elif  "clients" in args[0] and args[1] != None:
                if args[1] == "name":
                    get_value = get_name
                elif args[1] == "id":
                    get_value = get_client_id
                elif args[1] == "ip":
                    get_value = get_ip
                elif args[1] == "help":
                    self.gui.print_command("--------------------------------------")
                    self.gui.print_command("Clients help:")
                    self.gui.print_command("Type \"clients\" \"name , id or ip\" to get values from clients")
                    return
                else:
                    self.gui.print_command("Error: Invalid argument")
                    return
                
                self.gui.print_command("--------------------------------------")
                for client in self.osc_clients:
                    self.gui.print_command(get_value(client))
                


            #if the command is "test" do nothing yet
            elif "test" in args[0]:
                    self.gui.print_command(f"Not yet")
                      
                      
          
    


#this function is used to start the osc server
    def start_server(self):
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.start()

    def stop_server(self):
        
        
        time.sleep(0.05)
        
#this function is used to start the command handler
    def start_handle(self):
        self.handle_thread = threading.Thread(target=self.handle_loop)
        self.handle_thread.start()

    def stop_threads(self): 
        self.server.shutdown()
        self.server.shutdown()
        self.handle_thread.join()
        self.server_thread.join()
        
    def set_exit_flag(self):
        self.exit_flag = True
        





        
class Osc_client:
    
    def __init__(self, name, client_id, ip, port, client_type):      
        
        self.name = name
        self.client_id = client_id
        self.ip = ip
        self.port = port
        self.client_type = client_type        
        self.gui = None
        #self.trigger = False   # is true if the client is triggered by a type A client
        self.button_status = False
        self.mode = "normal"
        
        #the status of the client if False, because the gui is not created yet
        #self.status = False
        self.client = None
        
        self.requested = False  # Initialize the requested flag to false 
        self.timer_start = None  # Initialize the timer start time to None
        self.response_time = None  # Initialize the response time to None
        self.timeout_threshold = 5  # Set the timeout threshold to 5 seconds
        self.online = False # Initialize the online status to False
        

    #send command function
    def send_data(self , value , cmd):
        
        #set up the udp client
        receiver = udp_client.SimpleUDPClient(self.ip, self.port)
        #gma3 is recieving a command with only one argument
        if self.client_type == "gma3":
            receiver.send_message("/cmd", [cmd])
            self.gui.print_command_log(f"Sending /cmd , {cmd} command to {self.name}")
            
            return        
        receiver.send_message("/cmd", [value , cmd])        
        
        
    def get_command(self, val, cmd):
        
        if self.client_type == "gma3":
            return(str(self.client_id) , self.get_C_command(val, cmd))
        elif cmd == "trigger":
                cmd = (f"trigger {str(val)}")
        else:
            val = self.client_id
        return (str(self.client_id) , str(val) , str(cmd))
    

    #commands send to grandma3
    def get_C_command(self, val, cmd):
        try:
            
            val = int(val)
        except (ValueError, TypeError):
            return False
        if cmd == "trigger":
            if(self.mode == "normal"):
                gma3_cmd = (f"Go+ Sequence {str(6000 + val)}") 
            elif(self.mode == "stage"):
                gma3_cmd = "On Sequence 6008" # we can set the button modus here
                
        elif cmd == "debug":
             gma3_cmd = "Go+ Sequence 6006"
             
        elif cmd == "special":
             gma3_cmd = "Go+ Sequence 6007"
             
        elif cmd == "released":
             gma3_cmd = "Off Sequence 6008"
            
        elif cmd == "stop":
            gma3_cmd = "Go+ Sequence 6009" 
            
        elif cmd == "confirm":
            gma3_cmd = "Go+ Sequence 6010"
            
        elif cmd == "ping":
            gma3_cmd = "Go+ Sequence 6011"
        else:
            self.gui.print_command("Command not found for grandma3")
        
        return (gma3_cmd)


    def set_mode(self, modus):
        self.mode = modus
    
    def get_mode(self):
        return self.mode

    def set_gui(self, gui):
        self.gui = gui
            
    def get_name(self):
        return self.name
        
    def set_name(self, value):
        self.name = value

    
    def get_ip(self):
        return self.ip

    
    def set_ip(self, value):
        if not value:
            return
        ip_parts = value.split('.')
        if len(ip_parts) == 4 and all(part.isdigit() and 0 <= int(part) <= 255 for part in ip_parts):
            self.ip = value
        else:
            
            self.gui.print_command("Invalid IP address format.")
            
    
    def get_port(self):
        return self.port

    
    def set_port(self, value):
        if not value:
            return
        if isinstance(value, int):
            self.port = value
        else:
            self.gui.print_command("Port must be an integer. (9069)")
    
    def get_client_id(self):
        return self.client_id

   
    def set_client_id(self, value):        
            self.client_id = value        
    
    def get_client_type(self):
        return self.client_type
   
    def set_client_type(self, value):
        if value in {'trigger', 'station', 'gma3'}:
            self.client_type = value
        else:
            self.gui.print_command_log("Invalid station type. Should be 'trigger', 'station', 'gma3'.")
            
            
    def set_button_was_pressed_state(self, value):
        self.button_status = value
    
    def get_button_was_pressed_state(self):
        return self.button_status

    def set_requested_flag(self, value):
            self.requested = value
            if value:                
                self.start_timer()
            else:                
                self.stop_timer()
                
    def get_requested_flag(self):
        return self.requested

    def check_ping_timeout(self):
        if self.timer_start is not None:
            elapsed_time = time.time() - self.timer_start
            if elapsed_time > self.timeout_threshold:
                self.stop_timer()
                self.set_requested_flag(False)
                self.gui.print_command(f"Timeout: Client {self.name} ID:{self.client_id} is not available.")  
                self.online = False                
                self.gui.gui_update_online_status(self , False)
                
    def get_online_status(self):
        return self.online  
    
    def set_online_status(self, val):
        self.online = val
        
    def set_status(self, value):
        self.status = value
    
    def get_status(self):
        return self.status
  

    def start_timer(self):
        self.timer_start = time.time()

    def stop_timer(self):
        if self.timer_start is not None:
            self.timer_start = None

    def get_response_time(self):
        self.response_time = int((time.time() - self.timer_start)*1000)
        self.online = True        
        return self.response_time
    

    

               



class File_handler:
    def __init__(self, name):
        self.name = name    
        # Define the folder paths for config and log files
        self.config_folder = "data/config"
        self.log_folder = "data/log"     
        self.info_folder = "data/info"
        self.gui = None
        

    def set_gui(self, gui):
        self.gui = gui

    def read_file(self, input_file):
        # Determine the folder based on the file_type argument
        if input_file == "config":
            folder_path = self.config_folder
        elif input_file == "log":
            folder_path = self.log_folder
        elif input_file == "info":
            folder_path = self.info_folder
        else:
            raise ValueError("Invalid file_type. Use 'config', 'info', or 'log'.")

        data = []

        if input_file == "config":
            id_counter = 1  # Initialize the ID counter to 1
            # Iterate through files in the specified folder
            for file_name in os.listdir(folder_path):
                if file_name.endswith(".ini"):
                    file_path = os.path.join(folder_path, file_name)
                    config = ConfigParser()
                    config.read(file_path)

                    for section in config.sections():
                        # Create Osc_client objects
                        name = config[section]['name']
                        client_id = id_counter   # Assign a unique ID to each client
                        ip = config[section]['ip']
                        port = int(config[section]['port'])
                        client_type = config[section]['client_type']

                        osc_object = Osc_client(name, client_id, ip, port, client_type)
                        data.append(osc_object)
                        id_counter += 1
        elif input_file == "log":
            # For non-config files, read line by line
            for file_name in os.listdir(folder_path):
                if file_name.endswith(".ini"):
                    file_path = os.path.join(folder_path, file_name)
                    with open(file_path, 'r') as file:
                        for line in file:
                            data.append(line.strip())
                            
        elif input_file == "info":
            for file_name in os.listdir(folder_path):
                if file_name.endswith(".ini"):
                    file_path = os.path.join(folder_path, file_name)
                    with open(file_path, 'r') as file:
                        for line in file:
                            data.append(line.strip())
                            
        else:   
                self.gui.print_command_log("Invalid file type")
        return data

    def write_config(self, osc_objects):
        config = ConfigParser()

        for i, osc_object in enumerate(osc_objects, start=1):
            section_name = f"Client_{i}"
            config[section_name] = {
                'name': osc_object.name,
                'client_id': str(osc_object.client_id),
                'ip': osc_object.ip,
                'port': str(osc_object.port),
                'client_type': osc_object.client_type
            }
            self.gui.print_command_log(f"Writing config for {osc_object.name} {osc_object.client_type} {osc_object.client_id}")
        config_file_path = os.path.join(self.config_folder, 'config.ini')    
        with open(config_file_path, 'w') as configfile:
            config.write(configfile)
            configfile.flush()    
    
    def write_log(self, log_entry):
        log_file_path = os.path.join(self.log_folder, 'log.ini')

        try:
            if not os.path.exists(self.log_folder):
                os.makedirs(self.log_folder)

            with open(log_file_path, 'a') as log_file:
                # Append the log entry to a new line in the log file
                log_file.write(f"{log_entry}\n")
                

        except Exception as e:
            self.gui.print_command_log(f"Error writing to log file: {e}")

   

def main():
    try:
        
        server_commands = commands.Commands("server_commands")
        text_handler = File_handler("text_handler")
        

        osc_objects =  text_handler.read_file("config")    
        osc_clients = [Osc_client(obj.name, obj.client_id, obj.ip, obj.port, obj.client_type) for obj in osc_objects]
        
        
        
        # Start the OSC server and Tkinter GUI
        root = tk.Tk()
        gui = GuiHandler(root, osc_clients , "#DDDDDD", "#FFFFFF", "#000000", text_handler ,  server_commands)
        
        
        
        osc_dispatcher = dispatcher.Dispatcher()   
        osc_handler = Osc_command_handler(osc_dispatcher, "0.0.0.0", 9050, osc_clients , gui , server_commands , text_handler)
        
        

        # Pass a reference to osc_handler to text_handler
        gui.set_osc_handler(osc_handler)
        for client in osc_clients:
            client.set_gui(gui)
            
        text_handler.set_gui(gui)
        # Get the current local time and write it to the log file
        
        
        
    
        
        osc_handler.start_server()
        
        osc_handler.start_handle()
        
        gui.start_gui()
       
        time.sleep(2) # Wait for the GUI to start before sending commands
        
        
    except Exception as e:
        # Handle exceptions here
        print(f"Error: {e}")

if __name__ == "__main__":
    
    main()
    
