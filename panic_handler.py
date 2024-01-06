
#!/usr/bin/env python3.11
from configparser import ConfigParser
from re import S
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
import gui
from datetime import datetime




# The OscServerHandler class is used to handle OSC messages from a specific IP address and port.
# The class is initialized with a dispatcher and a server address and port.
# The dispatcher is used to map OSC addresses to handler functions.
# The server is used to listen for OSC messages on the specified address and port.
class Osc_command_handler:
    def __init__(self, dispatcher, address, port, clients, gui_handler, commands ,text_handler):
        
        self.address = address  # Fix typo in the attribute name
        self.port = port
        self.osc_clients = clients
        self.gui_handler = gui_handler  # Store the gui_handler as an attribute
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
            if client.station_type == "trigger":
                self.trigger_osc_clients.append(client)
        #list of all station clients      
        self.station_osc_clients = []
        for client in self.osc_clients:
            if client.station_type != "station":
                self.station_osc_clients.append(client)

        self.status_timer = None  # Initialize the status timer to None
        self.ping_timer = time.time()  # Initialize the ping timer to None
        self.client_ping_index = 0
        
        self.gui_handler.print_command("Server started")
        time.sleep(0.4)
        self.gui_handler.print_command(f"LISTENING ON {self.address}:{self.port}")
        time.sleep(0.4)
        self.gui_handler.print_command(f"Number of clients: {len(self.osc_clients)} loaded")
        time.sleep(0.4)
        self.gui_handler.print_command("Type 'help' for a more info")
        time.sleep(0.4)
        self.gui_handler.print_command("Sending Ping to all clients")
        self.request_all_command(1)
        time.sleep(0.4)
        self.gui_handler.print_command("Waiting for clients")

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
            
       
                    
    #listen to incoming messages
    def receive_command(self, *args):
        self.gui_handler.print_command_log(f"\"/cmd\",{args}")
        #awaiting a command with 3 arguments or 2 arguments for gma3
        if len(args) == 2:
            for i in self.osc_clients:
                if i.station_type == "gma3":
                    client = i
                    cmd = str(args[1])
        elif len(args) == 3:
            
            #exeption handling for incoming arguments
            try:
            # Try casting to int to get client ID
                client_id = int(args[1])
            except (ValueError, TypeError):
                return False
            try:
                cmd = str(args[2])
            except (ValueError, TypeError):
                return False
       
            client = self.osc_clients[client_id-1]
        else:
            self.gui_handler.print_command_log("Receive error: Invalid number of arguments")
            return False          
        
        if client:            
            self.receive_queue.put((client.client_id , cmd))
            
            
        else:
            self.gui_handler.print_command(f"Client not found for ID {client_id}")
            return False
        
        #this function is usend to handle received commands from a queue        
    #handle received commands from queue
    def receive_queue_function(self):
       #handle the received commands queue
        received_msg = self.receive_queue.get()     
        client_id = int(received_msg[0])         
        command = str(received_msg[1])
        
        self.handle_command(client_id , command) 
        
     # This function is to handle the received commands
    #handle commands from queue
    def handle_command(self, client_id ,  command):
        
                        
        if command == "ping":
            self.response_command(client_id)
            
        elif command == "trigger":           
           self.send_trigger_command(client_id) 
           
     
        elif command == "confirm":            
            self.confirm_command(client_id)
            
        elif command == "released":            
            self.released_command(client_id)
            
            
        else:
            self.gui_handler.print_command(f"Handle error: Command not found")
            self.gui_handler.print_command(f"Command: {command} from ID: {client_id}")    


    #sending commands from queue
    def send_queue_function(self):
        send_msg = self.send_queue.get()
        
        print (send_msg[1])
        
        client = self.osc_clients[int(send_msg[0])-1]
        
        if(client.station_type != "gma3"):
          
            value = int(send_msg[1])
            command = send_msg[2]
        else:            
            value = send_msg[0]
            command = send_msg[1]
            
        
        client.send_data(value , command)
        #self.gui_handler.print_command_log(f"Sending {command}  command to {client.name}")
        
###########################    COMMAND HANDLE LOGIC  ############################

    #if a type A client sends a status command, start a function on all type B and C clients
    #the server will set a status for the type A client and send it to the gui in the set_status function
    def send_trigger_command(self, trigger_client_id):
        if(self.osc_clients[trigger_client_id].get_trigger() == True):
            self.gui_handler.print_command_log("Client is already triggered")
            return #exit the function if the client is already triggered
        self.gui_handler.print_command(f"Status set by {self.osc_clients[trigger_client_id-1].get_name()}")
        # get a timestamp for a triggerd client and write into log file
        local_time = datetime.now()
        format_time = local_time.strftime("%Y-%m-%d %H:%M")
        self.text_handler.write_log(f"{format_time} Status triggerd on {self.osc_clients[trigger_client_id].get_name()}")
        
        #set a timer for the status of the client
        self.start_time = time.time()
        
        #self.osc_clients[trigger_client_id].status_timer = time.time()
        #save the sending client ID to trigger the corrosponding function on the type B and C clients
            
        self.set_status(trigger_client_id, True)#set the pressed button status to true and update the gui
                    
        #send to all station clients the trigger command from trigger client
        for client in self.station_osc_clients:
                self.send_queue.put(client.get_command(trigger_client_id, "trigger"))
                   
              

    #if a the server gets a "corfirm" command it                        
    #Send "stop" command to all B and C stations and update the gui     
    def confirm_command(self, sender_id):
        #get the name of the client that sent the confirm command
        if(sender_id == 0):
            sender = "server"
        else:
            sender = self.osc_clients[sender_id-1].name
            
        for client in self.trigger_osc_clients:
            if client.get_trigger() == True:
                break # if a type A client is triggered, continue with the function
            else:
                self.gui_handler.print_command(f"{sender} pressed without a reason!")
                return # if no type A client is triggered, exit the function
       
            
        #get the elapsed time since a trigger  was set
        if self.status_timer is not None:
            elapsed_time = time.time() - self.status_timer
            self.start_time = None
            minutes = int(elapsed_time / 60)
            seconds = int(elapsed_time % 60)
            self.text_handler.write_log(f"Status confirmed by {sender} after {minutes}:{seconds}")    

        for client in self.station_osc_clients:
            self.send_queue.put(client.get_command(client.client_id , "stop"))
        
        for client in self.trigger_osc_clients:
            if client.get_trigger() == True:
                self.set_status(client.client_id, False)
                       
  
   

    #this function is called if a response command is received from a client
    def response_command(self, client_id):
        self.osc_clients[client_id-1].set_online_status(True)
        self.gui_handler.print_command_log(f"Received ping from {self.osc_clients[client_id-1].name} ")
            
        if(self.osc_clients[client_id-1].get_requested() == True):
            self.gui_handler.print_command(f"Response time: {self.osc_clients[client_id-1].get_response_time():.3f} seconds")           
            self.osc_clients[client_id-1].set_requested(False)
            self.gui_handler.gui_set_client_online_status(client_id, True)
            self.osc_clients[client_id-1].set_online_status(True)
        else:            
            self.gui_handler.print_command(f"Client {self.osc_clients[client_id-1].name} is now online")
            self.osc_clients[client_id-1].set_online_status(True)
    
    #if a button was released. (it can set a grandma3 seq to off, or handle other commands.)        
    def released_command(self, client_id):
        if client_id == 1:
            self.send_queue.put(self.osc_clients[6].get_command(client_id , "released"))
            
    #this function is to ping a client
    def request_command(self, client_id):
        client = self.osc_clients[client_id-1]
        self.osc_clients[client_id-1].set_requested(True)
        self.gui_handler.gui_set_client_online_status(client_id, True) # can be false
        self.send_queue.put(client.get_command(client.client_id , "ping"))
        
   
    #request all clients except station id  "i"
    def request_all_command(self, i ):
        for client in self.osc_clients:
            
            if client.client_id != i:
                self.request_command(client.client_id)
            
 
    #this function is used if a type A client sends a status command to update the client status and gui
    def set_status(self, client_id, val):
                
            self.osc_clients[client_id-1].set_trigger(val)            
            self.gui_handler.set_status(self.osc_clients[client_id-1].client_id , val)
       
        
    #this function is used if a stop command is received to clear the status form type A clients
    def clear_status(self):
        for client in self.trigger_osc_clients:            
            self.set_status(client.client_id, False)
     

    def ping_single_client(self):
        elapsed_time = time.time() - self.ping_timer
        
        if elapsed_time >= 60:  # 60 seconds 
            # Reset the timer
            
            self.ping_timer = time.time()
            self.request_command(self.client_ping_index)
            self.client_ping_index += 1
            self.ping_timer += 1
            if self.client_ping_index == len(self.osc_clients):
                self.client_ping_index = 0 
                            
    def check_requested_clients(self):
        for client in self.osc_clients:
                if client.get_requested() == True:
                    client.check_timeout()
           
                   
################################# START GUI COMMAND #################################

#this function is called when a command is entered in the gui
    def gui_command(self, command):
        args = command.split()
        
        #commandline commands start with cmd , ID , osc_command
        if (args[0] == "cmd"):                
            if len(args) == 3:
                    
                ID = int(args[1])
                i = ID - 1
                if 0 <= i < (len(self.osc_clients)):
                    command = str(args[2])
                    client = self.osc_clients[i]
                    
                    if command in self.command_list:
                        if "trigger" in command:
                            
                            self.osc_clients[i].send_data(1 , command) # always sends a trigger status from t1
                                
                        #debug test for t1
                        elif "debug" in command:
                            self.osc_clients[0].send_data(1 , "debug")# always debug t1 button
                                  
                        elif "ping" in command:
                            self.send_queue.put(client.get_command(ID, command))
                            
                                
                        elif "confirm" in command:                            
                            self.send_queue.put(client.get_command(ID, command))   
                                                            
                                                      
                        elif "stop" in command:                            
                            self.send_queue.put(client.get_command(ID, command))                                
                                
                        elif "special" in command:                            
                            self.osc_clients[0].send_data(1 , "special")
                            
                        else:
                            self.gui_handler.print_command(f"Send command not found")
                            return
                            
                        self.gui_handler.print_command(f"Send test: {command} to ID:{ID} - {self.osc_clients[i].name} ")
                    else:
                        self.gui_handler.print_command("Command not found")
                else:
                    self.gui_handler.print_command("Error: Client ID out of range:")
            else:   
                self.gui_handler.print_command("Error: Missing arguments for set command")
                    
        elif len(args) >= 1 <= 2:
                                    
            if len(args) == 2 and "help" in args[0] and "cmd" in args[1]:
                self.gui_handler.print_command("--------------------------------------")
                self.gui_handler.print_command("Send commands are:")
                self.gui_handler.print_command(self.commands.all_send_commands)
                self.gui_handler.print_command("For example type \"cmd 1 ping\" into the commandline to send a ping")

            if len(args) == 1 and "help" in args[0]:
                self.gui_handler.print_command("--------------------------------------")
                self.gui_handler.print_command("Send command ID")                   
                self.gui_handler.print_command(f"\"clients\" return all clients")                   
                self.gui_handler.print_command(f"\"cmd ID send_command\" send a test command to an id") 
                self.gui_handler.print_command(f"Type \"help cmd\" for more info") 
                self.gui_handler.print_command(f"\"test\" will do nothing")
                   
            elif "clients" in args[0]:
                self.gui_handler.print_command("--------------------------------------")
                self.gui_handler.print_command(f"All registered clients:") 
                for client in self.osc_clients:
                    self.gui_handler.print_command(f"Name:      {client.name}")
                    self.gui_handler.print_command(f"ID:        {client.client_id} Type: {client.station_type}")
                    self.gui_handler.print_command(f"IP/Port:   {client.ip}:{client.port}")
            elif "test" in args[0]:
                    self.gui_handler.print_command(f"Not yet")
                    
            elif "confirm" in args[0]:
                                              
                return        
                      
          
    


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
    
    def __init__(self, name, client_id, ip, port, station_type):      
        
        self.name = name
        self.client_id = client_id
        self.ip = ip
        self.port = port
        self.station_type = station_type        
        self.gui_handler = None
        #self.trigger = False   # is true if the client is triggered by a type A client
        self.is_triggered = False
        self.mode = "normal"
        
        #the status of the client if False, because the gui_handler is not created yet
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
        if self.station_type == "gma3":
            receiver.send_message("/cmd", [cmd])
            self.gui_handler.print_command_log(f"\"/cmd\",{value},{cmd} ")
            return        
        receiver.send_message("/cmd", [value , cmd])        
        
        
    def get_command(self, val, cmd):
        
        if self.station_type == "gma3":
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
                cmd = (f"Go+ Sequence {str(6000 + val)}") 
            elif(self.mode == "stage"):
                cmd = (f"On Sequence 6008") 
        
        elif cmd == "released":
             cmd = "Off Sequence 6008"
            
        elif cmd == "stop":
            cmd = "Go+ Sequence 6009"    
        elif cmd == "confirm":
            cmd = "Go+ Sequence 6010"
        elif cmd == "ping":
            cmd = "Go+ Sequence 6011"
            
        
        return (cmd)


    def set_mode(self, modus):
        self.mode = modus
    
    def get_mode(self):
        return self.mode

    def set_gui_handler(self, gui_handler):
        self.gui_handler = gui_handler
            
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
            
            self.gui_handler.print_command("Invalid IP address format.")
            
    
    def get_port(self):
        return self.port

    
    def set_port(self, value):
        if not value:
            return
        if isinstance(value, int):
            self.port = value
        else:
            self.gui_handler.print_command("Port must be an integer. (9069)")
    
    def get_client_id(self):
        return self.client_id

   
    def set_client_id(self, value):        
            self.client_id = value        
    
    def get_station_type(self):
        return self.station_type
   
    def set_station_type(self, value):
        if value in {'trigger', 'station', 'gma3'}:
            self.station_type = value
        else:
            self.gui_handler.print_command_log("Invalid station type. Should be 'trigger', 'station', 'gma3'.")
            #self.gui_handler.print_command("Invalid station type. Should be 'trigger', 'station', 'gma3'.")
            
    def set_trigger(self, value):
        self.is_triggered = value
    
    def get_trigger(self):
        return self.is_triggered

    def set_requested(self, value):
            self.requested = value
            if value:                
                self.start_timer()
            else:                
                self.stop_timer()
                
    def get_requested(self):
        return self.requested

    def check_timeout(self):
        if self.timer_start is not None:
            elapsed_time = time.time() - self.timer_start
            if elapsed_time > self.timeout_threshold:
                self.stop_timer()
                self.set_requested(False)
                self.gui_handler.print_command(f"Timeout: Client {self.name} {self.ip}:{self.port} is not available.")  
                self.online = False                
                self.gui_handler.gui_set_client_online_status(self.client_id , False)
                
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
        self.response_time = time.time() - self.timer_start
        self.online = True
        self.gui_handler.print_command(f"Client {self.name} is online.")
        return self.response_time
    

    

               



class File_handler:
    def __init__(self, name):
        self.name = name    
        # Define the folder paths for config and log files
        self.config_folder = "data/config"
        self.log_folder = "data/log"     
        self.info_folder = "data/info"
        self.gui_handler = None
        

    def set_gui_handler(self, gui_handler):
        self.gui_handler = gui_handler

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
                        station_type = config[section]['station_type']

                        osc_object = Osc_client(name, client_id, ip, port, station_type)
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
                self.gui_handler.print_command_log("Invalid file type")
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
                'station_type': osc_object.station_type
            }
            self.gui_handler.print_command_log(f"Writing config for {osc_object.name} {osc_object.station_type} {osc_object.client_id}")
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
            self.gui_handler.print_command_log(f"Error writing to log file: {e}")

   

def main():
    try:
        
        server_commands = commands.Commands("server_commands")
        text_handler = File_handler("text_handler")
        

        osc_objects =  text_handler.read_file("config")    
        osc_clients = [Osc_client(obj.name, obj.client_id, obj.ip, obj.port, obj.station_type) for obj in osc_objects]
        
        
        
        # Start the OSC server and Tkinter GUI
        root = tk.Tk()
        gui_handler = gui.GuiHandler(root, osc_clients , "#DDDDDD", "#FFFFFF", "#000000", text_handler ,  server_commands)
        
        
        
        osc_dispatcher = dispatcher.Dispatcher()   
        osc_handler = Osc_command_handler(osc_dispatcher, "0.0.0.0", 9091, osc_clients , gui_handler , server_commands , text_handler)
        
        

        # Pass a reference to osc_handler to text_handler
        gui_handler.set_osc_handler(osc_handler)
        for client in osc_clients:
            client.set_gui_handler(gui_handler)            
        text_handler.set_gui_handler(gui_handler)
        # Get the current local time and write it to the log file
        
        
        
    
        
        osc_handler.start_server()
        
        osc_handler.start_handle()
        
        gui_handler.start_gui()
       
        time.sleep(2) # Wait for the GUI to start before sending commands
        
        
    except Exception as e:
        # Handle exceptions here
        print(f"Error: {e}")

if __name__ == "__main__":
    
    main()
    
