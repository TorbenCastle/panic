
#!/usr/bin/env python3.11
from configparser import ConfigParser
from re import A
import socket
from tempfile import TemporaryDirectory

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

from osc_client import Osc_client
try:
    import RPi.GPIO as GPIO
    on_raspberry_pi = True
except ImportError:
    on_raspberry_pi = False




# The OscServerHandler class is used to handle OSC messages from a specific IP address and port.
# The class is initialized with a dispatcher and a server address and port.
# The dispatcher is used to map OSC addresses to handler functions.
# The server is used to listen for OSC messages on the specified address and port.
class Osc_server:
    def __init__(self, dispatcher, address, port, clients, gui, commands ,text_handler , relay_pin):
        
        self.address = address  # Fix typo in the attribute name
        self.port = port
        self.osc_clients = clients
        self.gui = gui  # Store the gui as an attribute
        self.commands = commands  # Store the Commands instance as an attribute
        self.text_handler = text_handler
        
        #i dont know yet, why i cant start the server somewhere else - fix it later
        self.dispatcher = dispatcher
        self.dispatcher.set_default_handler(self.receive_command)
        

        self.server = ThreadingOSCUDPServer((address, port), dispatcher)        
        self.handle_thread = None
        self.exit_flag = False
        
        self.receive_queue = queue.Queue()
        self.send_queue = queue.Queue()
        
        
        
        
        #the list of all commands that can be send to a client and received from a client
        self.send_cmd_list      =   ["status"  , "stop"    , "ping", "release" , "debug" , "exta", "msg" ,  "ping_all"]
        self.receive_cmd_list   =   ["trigger" , "confirm" , "ping", "release" , "debug" , "relay", "extra" ,"msg" , "released", "fog_on" , "fog_off" , "fog_value"]
        self.client_attribute   =   ["name"    , "client_id"      , "ip"  , "port"    , "client_type"  ]
        
        self.c_station = None  # Variable to store the C-type station
        #list of all trigger clients
        self.trigger_osc_clients = []
        for client in self.osc_clients:
            if client.client_type == "trigger":
                self.trigger_osc_clients.append(client)
        #list of all station clients      

        self.station_osc_clients = []
        for client in self.osc_clients:
            if client.client_type != "trigger":
                self.station_osc_clients.append(client)
              
        #lists of all clients ident variables 
        self.client_name_list = [client.name for client in self.osc_clients]        
        self.client_id_list = [client.client_id for client in self.osc_clients]        
        self.client_ip_list = [client.ip for client in self.osc_clients]
        

        self.status_timer = None  # Initialize the status timer to None
        self.ping_timer = time.time()  # Initialize the ping timer to None
        self.if_fog_on_timer = 0
        self.relay_pin = relay_pin
        self.relay_timer = None
        self.relay_duration = 15
        self.relay_is_on = False
        
        self.fog_on = False
        self.fog_fader_value = 0
        self.fog_time_values = []
        
        self.fog_event_id = 1 # needed to work with fog data
        self.fog_readouts = 0
        #index for the roating ping command
        self.client_ping_index = 0
        
        
        #check if we are in location A or B to get the right grandma IP
        if self.get_local_ip() == "10.187.177.128":
            self.osc_clients[6].set_ip("10.187.189.151")
        else:
            self.osc_clients[6].set_ip("192.168.0.46")
  











########################### PRINT INTO GUI AFTER INIT ##########################
        self.gui.print_command("Server started")
        time.sleep(0.4)
        self.gui.print_command(f"LISTENING ON {self.address}:{self.port}")
        time.sleep(0.4)
        self.gui.print_command(f"Number of clients: {len(self.osc_clients)} loaded")
        time.sleep(0.4)
        self.gui.print_command("Type 'help' for a more info")
        time.sleep(0.4)
        self.gui.print_command("Sending Ping to all clients")
        self.send_ping_all_command(0) # without a index of osc_clients list
        time.sleep(0.4)
        self.gui.print_command("Waiting for clients")


###########################   MAIN PART FROM COMMAND HANDLING   ####################


    #this function is the main loop of the send command handler and other functions
    def handle_loop(self):
       
        while not self.exit_flag:
                
            #check if a incoming message is to handle
            if not self.receive_queue.empty():
                self.receive_queue_function()
                
            #check if a outgoing message has to be sent    
            if not self.send_queue.empty(): 
                self.send_queue_function()
            
            #after a timer f 60 seconds send a ping command to the next client
            self.send_single_pings_clients()
            
            #check if a client is requested and if the timeout is reached
            self.check_requested_clients()
            
            #check if its time to switch off the relay    
            self.check_relay_timer()
                
                    
    #listen to incoming messages, the dispatcher is calling this function and its filter is "/cmd" and take the command to the receive queue
    def receive_command(self, address, *args):        
        self.gui.print_command_log(f"Received command: {address},{args}")  # Print the full received command to the GUI command line
        if address == "/cmd":
            self.receive_queue.put(args)
        
                
            
        

        

    #get tuples from received commands from queue
    def receive_queue_function(self):
       #handle the received commands queue
        received_osc_msg = self.receive_queue.get()   
        
        
        
        # Check if the length of args is not equal to 3 if the firs arg is an int, and if the int is in the client id list
        if len(received_osc_msg) < 2:
            self.gui.print_command_log(f"Invalid command length: {received_osc_msg}")
            return False
        
        #check if the first arg is an int, and if the int is in the client id list, if not exit the function
        try:
        
            client_id = int(received_osc_msg[0])
            if client_id in self.client_id_list:
                client = self.osc_clients[client_id-1]
            else:
               self.gui.print_command_log("ID not found")            
               return False   
        except:
            self.gui.print_command_log("Wrong ID format") 
        
        command = received_osc_msg[1]
        if command not in self.receive_cmd_list:
            self.gui.print_command(f"Incoming command is invalid: {command}")
            return False
        
        #add the command value to a string
        
        #if the command  has at least 3 args, add the rest to the command msg
        command_value = ""
        if len(received_osc_msg) >= 2:
            for i in range(2,len(received_osc_msg)): 
                command_value += received_osc_msg[i]
            command_value = str(command_value)   
        
        self.handle_command(client , command , command_value) 
        
     # This function is to handle the received commands
    #handle the received commands from the receive queue
    def handle_command(self, client, command, command_value):

        command_actions = {
            "ping": lambda: self.received_ping_command(client),
            "ping_all": lambda: self.received_ping_all_command(client),
            "trigger": lambda: (self.received_button_command(client), self.relay_on()),
            "confirm": lambda: self.received_confirm_command(client),
            "released": lambda: self.received_released_command(client),
            "msg": lambda: (self.gui.create_chat_message(client.get_name(),command_value)),
            "debug": lambda: self.gui.print_command("Debug message"),
            "extra": lambda: self.gui.print_command("Extra message"),
            "special": lambda: self.gui.print_command("Special message"),            
            "released": lambda: self.gui.print_command("released"),
            "fog_on": lambda: self.toggle_fog_on(),
            "fog_off": lambda: self.toggle_fog_off(),
            "fog_value": lambda: self.set_fog_value(command_value),
            "relay": lambda: self.received_relay_command(client)
            }
        action = command_actions.get(command, lambda: self.gui.print_command(f"Command not found: {command}"))
        action()
        return True

###########################  RECEIVING COMMAND HANDLE   ############################
     
    #if a trigger was not set before, the server will send a status to station clients, update the gui and writes a log entry
    def received_button_command(self, trigger_client):
        # get the id of the trigger client
        trigger_id = trigger_client.get_client_id()
        self.gui.print_command(f"{trigger_client.get_name()} was pressed")
        self.status_timer = time.time()           
        #exit the function if the client is already triggered
        if(trigger_client.get_button_was_pressed_state() == True):
            self.gui.print_command(f"{tigger_client.get_name()} is already triggered")
            return         
        
        
        else:        
            #send to all station clients a status update with the id value from trigger client        
            for client in self.osc_clients:           
                if client.get_client_type() != "A":
                    self.send_status_command(client , trigger_id)
                    print(f"trigger id: {trigger_id}")
                        
            #set the button_was_pressed_state to true and update the gui        
            self.set_client_gui_status(trigger_client, "pressed")
            
            #set a timer for the status of the trigger event
            self.start_time = time.time()               
            self.write_event_to_logfile({trigger_client.get_name()}, "pressed button", )  
    
            
    #if a station has confirmed a setted status, send a stop command to all stations, and update the clients and gui, write a log entry
    def received_confirm_command(self, client):
        #get the name of the client that sent the confirm command
        if isinstance(client, Osc_client):
            sender = client.get_name()            
        else:
            sender = "server"
        #when a trigger was set, send stop command, to stop running functions    
        for client in self.trigger_osc_clients:            
                if client.get_button_was_pressed_state() == True:
                    self.send_stop_command()
                    self.gui.print_command(f"{client.get_name()} status confirmed")          
                    self.relay_off()
                    self.write_event_to_logfile( sender, "confirmed")                          
                else:
                    # if no type A client is triggered, exit the function
                    self.gui.print_command_log(f"{sender} no status set before!")
                    return 
       
               
        #get the elapsed time since a trigger  was set
        if self.status_timer is not None:
            elapsed_time = time.time() - self.status_timer
            self.status_timer = None
            minutes = int(elapsed_time / 60)
            seconds = int(elapsed_time % 60)
            duration = (f"after {minutes}:{seconds}") 
            self.write_event_to_logfile( sender, "confirmed", duration)
            
    #update the client status and gui if ping received
    def received_ping_command(self, client):
        
        #if the client is offline, and comes online.
        if client.get_online_status() == False and client.get_ping_request_flag() == False: 
            self.gui.print_command_log(f"Client {client.name} is now online")
            self.set_client_gui_status(client, "online")
            
        elif(client.get_ping_request_flag() == True):
            self.gui.print_command(f"{client.name} ping: {client.get_response_time()} ms")            
            self.set_client_gui_status(client, "online")

       #if a station has confirmed a setted status, send a stop command to all stations, and update the clients and gui, write a log entry

    def received_released_command(self, client):
        self.gui.print_command_log(f"{client.name} released the button")
        #here we can add a function for further use

    def received_msg_command(self, client, msg):
        self.gui.print_command(f"{client.name} sent msg: {msg}")
        #here we can add a function for further use
        
    def received_relay_command(self, client):
        self.gui.print_command(f"{client.name} set the relay on")
        self.relay_on()
        #here we can add a function for further use

    def received_debug_command(self, client, msg):
        self.gui.print_command(f"{client.name} sent debug msg: {msg}")
        
###########################  SENDING COMMAND HANDLE   ############################
    #["status"  , "stop"    , "ping" , "release" , "debug" , "exta", "msg"]        
    #if a trigger was set, send a status command with the triggerd client to all stations.        
    def send_status_command(self, client , trigger_id):
                     
        self.send_queue.put(client.get_command("status" , trigger_id))
        #self.gui.print_command(f"Sending {self.osc_clients[client_id-1] } s status command to {client.get_name()}")


    #if the server received a confirmation, it is sending a stop command to all station clients                   
    def send_stop_command(self):
        self.gui.print_command("Stopping all alerts")
       #send a stop command to all type B and C clients to stop a status funciton, and update the client and gui
        for client in self.station_osc_clients:
                self.send_queue.put(client.get_command("stop",client.get_client_id()))        
        for client in self.trigger_osc_clients:              
              self.set_client_gui_status(client, "clear") 
              
    #this function is to ping a client
    def send_ping_command(self, client):      
        self.set_client_gui_status(client, "requested")
        self.send_queue.put(client.get_command("ping",client.get_client_id()) )
        
      #send a ping command to the next client in the list, to check if a client is online,
        
    def send_release_command(self, client):
        self.send_queue.put(client.get_command("release" ,client.get_client_id()))
        self.gui.print_command_log(f"Sending release command to {client.get_name()}")

    def send_debug_command(self, client):
        self.send_queue.put(client.get_command("debug",client.get_client_id()))
        self.gui.print_command_log(f"Sending debug command to {client.get_name()}")
        
    def send_special_command(self, client):
        self.send_queue.put(client.get_command("special",client.get_client_id()))
        self.gui.print_command_log(f"Sending extra command to {client.get_name()}")
        

    #send a chat message to a station
    def send_msg(self, client, msg):
        if not isinstance(client, Osc_client):
            client = self.osc_clients[client-1]
        if client.client_type == "gma3" or "gma2":
            client.send_msg("msg" ,  msg)            
        else: self.gui.print_command(f"Messages can only send to grandma")
        
    #after 60 seconds the next client is pinged
    def send_single_pings_clients(self):
        elapsed_time = time.time() - self.ping_timer
        
        if elapsed_time >= 60:  
            # Reset the timer            
            self.ping_timer = time.time()
            self.send_ping_command(self.osc_clients[self.client_ping_index])
            self.client_ping_index += 1
            self.ping_timer += 1
            #start the list from 0 if the last client is reached
            if self.client_ping_index == len(self.osc_clients):
                self.client_ping_index = 0 
          
    #request all clients except station id  "i"
    def send_ping_all_command(self, i = None ):
        if i == None:
            except_id = 0
        else:
            except_id = i
        for client in self.osc_clients:
            if client.client_id != except_id:
                self.send_ping_command(client)
                
       #if a the server gets a "corfirm" command it                        
    #Send "stop" command to all B and C stations and update the gui   
    
 

    #sending commands from queue
    def send_queue_function(self):
        try:
            #read out send queue and send the command to the client of the corrosponding ID in the send_msg
            send_msg = self.send_queue.get()
            
            client_id = int(send_msg[0])
            client = self.osc_clients[client_id-1]  
            value = send_msg[0]
            command = send_msg[1]
            
            #check send command list, if its grandma, dont care about the command for now
            
            client.send_data(value , command)
            
              
        except Exception as e:
            self.gui.print_command_log(f"Send queue error: {e}")
            return
    
    #grandma sends the fog_value and the server writes it to log automaticly. when the seq is turned off, the grandma plugin stops
    def set_fog_value(self, value):        
        float_fog_value = "{:.3f}".format(float(value))
        self.fog_fader_value = float_fog_value # format the string of value to float 
        self.create_fog_time_value(self.fog_fader_value)     # create fog data tuple
        

    def toggle_fog_on(self):       
        self.fog_on = True        
        # when fog is toggled on write into the fog_log.ini the start and fader value at time 0 then start the timer,
        #  the fog_event_id and  local time is needed for further data calculation
        self.fog_readouts += 1
        
    #set boolean to false and write into log file
    def toggle_fog_off(self):
        self.fog_on = False
        self.create_fog_time_value(self.fog_fader_value) # create entry for the last time
        self.text_handler.write_fog_log(self.fog_time_values)
        self.fog_time_values = [] #reset fog time values to an empty list

     #call the write_fog_log function every 0.5 second
    def create_fog_time_value(self, float_fader_value):        
         # reset fog request timer
        self.fog_time_values.append((self.get_local_time() , float_fader_value)) # create time fader tuples
        
       
   
        
#################################  GUI COMMANDLINE #################################

#this function is called when a command is entered in the gui commandline
    def gui_command(self, command):
       

        if len(command) == 0:
            return

        args = command.split(" ")
        if len(args) >= 3 and args[0] in ["send", "get"]:
            if len(args) == 3:
                msg = ""
            else:
                msg = " ".join(args[3:])
            #try:
           
            # type in name, id, or ip to get the target client
            #client = self.get_client(args[1])
            client = self.osc_clients[int(args[1])-1]
           
            if client in self.osc_clients:
                if "send" in args[0]:
                    self.commandline_send_cmd(client, args[2], msg)
                elif "get" in args[0]:
                    self.commandline_receive_cmd(client, args[2], msg)
                else:
                    self.gui.print_command("Error: Invalid cmd argument")
            else:
                self.gui.print_command_log("Error: No client has found")
            #except ValueError:
             #   self.gui.print_command(f"{args[2]} error: No client has {args[1]}")

        if  "help" in args[0] and args[1] == None:
            self.gui.print_command("--------------------------------------")
            self.gui.print_command("Send command ID")                   
            self.gui.print_command(f"\"clients\" return all clients")                   
            self.gui.print_command(f"\"send ID send_command\" send a test command to an id")
            self.gui.print_command(f"\"get ID receive_command\" server gets a test command from an id") 
            self.gui.print_command(f"Type \"help cmd\" for more info") 
            self.gui.print_command(f"\"test\" will do nothing")
                
        elif "help" in args[0] and "cmd" in args[1]:
            self.gui.print_command("--------------------------------------")
            self.gui.print_command("Send commands are:")
            self.gui.print_command(self.commands.all_send_commands)
            self.gui.print_command("For example type \"send 1 ping\" into the commandline to send a ping to client id 1") 
            self.gui.print_command("Or to send a msg \"cmd grandma3 msg Hello Sun\" into the commandline")
            self.gui.print_command(" to send a Message to Client with Name grandma3")
            self.gui.print_command("The second argument can be Client Name ID or IP address")

        #if commandline input is "clients" print all clients, or print a specific value if a second argument is given
        if  "clients" in args[0] and args[1] == None:
            self.gui.print_command("--------------------------------------")
            self.gui.print_command(f"All registered clients:") 
            for client in self.osc_clients:
                self.gui.print_command(f"Name:      {client.name}")
                self.gui.print_command(f"ID:        {client.client_id} Type: {client.client_type}")
                self.gui.print_command(f"IP/Port:   {client.ip}:{client.port}")
                    
            
        elif  "clients" in args[0] and args[1] != None:
            if (args[1] not in self.client_attribute):
                self.gui.print_command("--------------------------------------")                    
                self.gui.print_command("Type \"clients\" \"name , client_id , ip , port or client_type\"")
                self.gui.print_command("to get a list all clients with type station or other value")
                return
            else:
                self.gui.print_command(f"-----------clients with {args[1]}------------")
                matching_clients = self.get_clients_by_identifier({args[1]})
                if matching_clients:
                    for client in matching_clients:
                        if {args[1]} == "name":
                            self.gui.print_command(f"Found: {client.get_name()} ID: {client.get_id()}")
                        else:    
                            self.gui.print_command(f"Found: {client.get_name()} with {args[1]}")
                else:
                    self.gui.print_command(f"No clients found with {args[1]}")
                    return
                
        #if the command is "test" do nothing yet
        elif "test" in args[0]:
                self.gui.print_command(f"Not yet")
                      
    #commands the server can send      
    def commandline_send_cmd(self, client , command , msg):        
        print (command)
        if command in self.send_cmd_list:
            self.gui.print_command(f"Sending test: {command} to {client.get_name()} with {msg} ")
            #send gloabal status update to all station clients
            if "status" in command:
                self.send_status_command(client)             
            #send global stop command to all station clients   
            elif "stop" in command:
                self.send_stop_command(client)
            
            elif "debug" in command:
                self.send_debug_command(client)
                
            elif "msg" in command:
                client.send_msg("msg", msg)
            elif "var1" in command:
                client.send_msg_command("var1", msg)
            elif "ping" in command:
                if msg == "-a":
                    self.send_ping_all_command()
                else: self.send_ping_command(client)            
            else:
                self.send_queue.put(client.get_command(client, command))     
        else:
            self.gui.print_command(f"command not found")
            return
                            
        
    #test commands the server can receive   
    def commandline_receive_cmd(self, client , command , msg): 
         
            if command in self.receive_cmd_list:
               self.gui.print_command(f"Receiving test: {command} from {client.name}  {msg} ")
               self.handle_command(client , command , msg)
            else:
                self.gui.print_command(f"Receiving command not found")                            
                
 
 ####################################### OTHER COMMANDS #####################################################

             
    #this function is used if a type A client sends a status command to update the client status and gui
    def set_client_gui_status(self, client, val):       
            if val == "pressed":
                val = client.set_button_was_pressed_state(True)
                self.gui.gui_update_button_status(client , "pressed")
                
            elif val == "clear":                
                val = client.set_button_was_pressed_state(False)
                self.gui.gui_update_button_status(client , "clear") 
                
            elif val == "online":
                client.set_online_status(True)
                self.gui.gui_update_button_status(client , "online")
                client.set_ping_request_flag(False)
                
            elif val == "offline":
                client.set_online_status(False)
                self.gui.gui_update_button_status(client , "offline")
                
            elif val == "requested":
                client.set_ping_request_flag(True)
                self.gui.gui_update_button_status(client , "requested") 
                  
     
   
    #in the main loop, we check if a client request flag is true, if the client is requested, ping the client.            
    def check_requested_clients(self):
        for client in self.osc_clients:
                if client.get_ping_request_flag() == True:
                    client.check_ping_timeout()
           


    def get_client(self, search_value):
        
        try:
            input_search_value = search_value
            client_value = None

            input_search_value = str(search_value)

            if str(search_value) in map(str, self.client_id_list):
                    print(f"found {self.osc_clients[search_value - 1]}")
                    return self.osc_clients[search_value - 1]
            
            else: 
                cmd_id = False
                print(f"cmd_id {cmd_id} false")
            if isinstance(search_value, str):
                search_value = str(search_value)
                # Check if the search value is an IP address
                if search_value.count('.') == 3 and all(part.isdigit() and 0 <= int(part) <= 255 for part in search_value.split('.')):
                    client_value = "ip"
                else:
                    client_value = "name"

                print(f"Looking for {client_value}: {input_search_value}")

                search_value_lower = search_value.lower()

                for client in self.osc_clients:
                    if str(getattr(client, str(client_value))).lower() == str(search_value_lower) or str(getattr(client, str(client_value))).lower() == str(search_value_lower):
                        return client

                
                
                print(f"Client {search_value} with {client_value}: and {cmd_id} {input_search_value} not in the list")
                return None
        except Exception as e:
            print(f"Get client error: {e}")
            return None


        

        
    def get_clients_by_identifier(self, search_value):
        search_value_lower = str(search_value).lower()  # Convert search value to lowercase for case-insensitive comparison

        matching_clients = []

        for client in self.osc_clients:
            if str(client.client_id).lower() == search_value_lower or client.name.lower() == search_value_lower or str(client.ip).lower() or str(client.port).lower() == search_value_lower or str(client.client_type).lower():
                
                matching_clients.append(client)

        return matching_clients if matching_clients else None

     
    def write_event_to_logfile(self,event , name = None , msg = None):
        if isinstance(name , Osc_client):
            name = name.get_name()
        elif name == None:
            name = "SERVER"
        
        if msg == None:
            msg = ""
            
        # Get the current local time
        time_stamp = self.get_local_time()
        
        event_log_entry = f"{time_stamp} {name} {event} {msg}"
        self.gui.print_command_log(event_log_entry)
        self.text_handler.write_log(event_log_entry, "log.ini")               
    
    def get_local_time(self):
        local_time = datetime.now()
        format_time = local_time.strftime("%Y-%m-%d %H:%M:%S")
        return format_time



#this function is used to start the osc server
    def start_server(self):
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.start()

    def stop_server(self):
        self.server.shutdown()
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
        
    #turning on a relay if not already on
    def relay_on(self):
        if not self.relay_is_on:
            self.relay_timer = time.time()
            if on_raspberry_pi:           
                GPIO.output(self.relay_pin, GPIO.HIGH) 
            else:
                self.gui.print_command("Simulation __relay on__")
            self.relay_is_on = True   
    #or off     
    #turning off a relay         
    def relay_off(self):
        if self.relay_is_on:
            self.relay_timer = 0
            if not self.relay_is_on:
                self.relay_is_on = True
            if on_raspberry_pi:           
                GPIO.output(self.relay_pin, GPIO.LOW) 
            else:
                self.gui.print_command("Simulation  __relay off__")
            self.relay_is_on = False
    #check if the relay is on and if the time is up
    def check_relay_timer(self):
        if self.relay_is_on:
            elapsed_time = time.time() - self.relay_timer
            if elapsed_time > self.relay_duration:
                self.relay_off()



    def get_local_ip(self):
        try:
            # Create a socket object
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
            # Connect to an external server (doesn't actually send data)
            s.connect(("8.8.8.8", 80))
        
            # Get the local IP address
            local_ip = s.getsockname()[0]
        
            # Close the socket
            s.close()
        
            return local_ip
        except socket.error as e:
            print("Error:", e)
            return None

    

   
