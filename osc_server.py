
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
import RPi.GPIO as GPIO



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
        
        #the list of all commands that can be send to a client and received from a client
        self.send_cmd_list      =   ["status"  , "stop"    , "ping", "release" , "debug" , "special", "msg"]
        self.receive_cmd_list   =   ["trigger" , "confirm" , "ping", "release" , "debug" , "special", "msg"]
        
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


   # GPIO pin for the relay
        self.RELAY_PIN = 18  # Change this to the actual GPIO pin you are using

          # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.RELAY_PIN, GPIO.OUT, initial=GPIO.LOW)  # Set initial state to LOW
        
       

###########################   MAIN PART FROM COMMAND HANDLING   ####################
     
    def trigger_relay(self):
        print("Triggering relay!")
        # Add code here to trigger the relay (e.g., set GPIO pin high)
        GPIO.output(self.RELAY_PIN, GPIO.HIGH)
        time.sleep(15)  # Wait for 45 seconds
        GPIO.output(self.RELAY_PIN, GPIO.LOW)  # Turn off the relay

    
    
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
        msg_cmd = False
        msg = " " # empty msg for non "msg" commands
        #if the second command is "msg" the value is printed to the gui.
        #grandma3 sends a command with 3 arguments, /cmd prefix the command and the value
        if len(args) == 4 and args[3] != "msg": 
            msg = str(args[3])
            client_id = int(args[1])
            client = self.osc_clients[client_id-1]
            msg_cmd = True
        elif len(args) == 3 and args[2] == "msg":
            msg_cmd = True
            for i in self.osc_clients:
                if i.client_type == "gma3":
                        client = i
                msg = str(args[2])
                
        if  not msg_cmd:
            #handling normal commands with 3 arguments or 2 arguments for gma3
            if len(args) == 3 and args[2] != "msg":
                client_id = int(args[1])
                command = str(args[2])
                   
                client = self.osc_clients[client_id-1]
            elif len(args) == 2:
                for i in self.osc_clients:
                    if i.client_type == "gma3":
                        client = i
                        command = str(args[1])
            else:
                self.gui.print_command_log("Receive error: Invalid number of arguments")
                return False         
        
        # its easier to save only the client id in the queue, because the client object is not pickable
        if client: 
            self.receive_queue.put((client.client_id , command , msg  ))
        else:
            self.gui.print_command(f"Client not found for ID {client_id}")
            return False
        
          
    #get tuples from received commands from queue
    def receive_queue_function(self):
       #handle the received commands queue
        received_msg = self.receive_queue.get()     
        client_id = int(received_msg[0])         
        input_command = str(received_msg[1])        
        msg = str(received_msg[2]) # commes with empty msg for non "msg" commands
        client = self.osc_clients[client_id-1]
        
        self.handle_command(client , input_command , msg) 
        
     # This function is to handle the received commands
    
    def handle_command(self, client ,  input_command, msg):
                                
        if input_command == "ping":
            self.response_command(client)
            
        elif input_command == "trigger":           
           self.send_status_command(client)           
     
        elif input_command == "confirm":            
            self.confirm_command(client.get_client_id())
            
        elif input_command == "released":            
            self.released_command(client)
        elif input_command == "msg":            
            self.gui.print_command(msg)
            
        elif input_command == "debug":            
            self.trigger_relay()
            
        elif "special" in input_command:            
            self.gui.print_command(f"special command from {client.get_name()}") 
               
        else:
            self.gui.print_command(f"Command not found: {input_command}")
            return False


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
            
        #set the status of trigger client to true and update the gui
        self.set_client_gui_status(trigger_client, "triggered")            
        
        #send to all station clients a status update with the id value from trigger client
        for client in self.station_osc_clients:
            if client.get_client_type() != "trigger": # send trigger command to all receiving stations   
                self.send_queue.put(client.get_command(trigger_id, "status"))
                self.gui.print_command(f"Sending status command to {client.name}")
                   
              

    #if a the server gets a "corfirm" command it                        
    #Send "stop" command to all B and C stations and update the gui     
    def confirm_command(self, confirm_id):
        #get the name of the client that sent the confirm command
        if(confirm_id == 0):
            sender = "server"
        else:
            sender = self.osc_clients[confirm_id-1].name
            
        for client in self.osc_clients:
            if client.client_type == "trigger":
                if client.get_button_was_pressed_state() == True:
                    self.gui.print_command(f"{client.get_name()} is triggered")
                    self.send_stop_command()
                    break # if a type A client is triggered, continue with the function
                #else:
                    #self.gui.print_command(f"{sender} confirmed without a reason!")
                    #return # if no type A client is triggered, exit the function
       
               
        #get the elapsed time since a trigger  was set
        if self.status_timer is not None:
            elapsed_time = time.time() - self.status_timer
            self.start_time = None
            minutes = int(elapsed_time / 60)
            seconds = int(elapsed_time % 60)
            self.text_handler.write_log(f"Status confirmed by {sender} after {minutes}:{seconds}") 
            

        
        
                       
    def send_stop_command(self):
        
        self.gui.print_command("Sending stop command to all stations")
       #send a stop command to all type B and C clients to stop a status funciton.
        for client in self.station_osc_clients:
            if client.get_client_type() != "trigger":
                self.send_queue.put(client.get_command(client.client_id , "stop"))
        
        for client in self.trigger_osc_clients:
            if client.get_client_type() == "trigger":
                if client.get_button_was_pressed_state() == True:
                    self.set_client_gui_status(client, "clear") 
   

    #this function is called if a response command is received from a client
    def response_command(self, client):
        
        #if the client is offline, and comes online.
        if client.get_online_status() == False and client.get_requested_flag() == False: 
            self.gui.print_command_log(f"Client {client.name} is now online")
            self.set_client_gui_status(client, "online")
            
        elif(client.get_requested_flag() == True):
            self.gui.print_command_log(f"{client.name} ping: {client.get_response_time()} ms")            
            self.set_client_gui_status(client, "online")
           

    
    #if a button was released. (it can set a grandma3 seq to off, or handle other commands.)  
    #at the moment only the t1 button can toggle osc effect sequences.      
    def released_command(self, client):
        if client.client_id == 1:
            self.send_queue.put(self.osc_clients[6].get_command(client.client_id  , "released"))
            
    #this function is to ping a client
    def request_command(self, client):      
        self.set_client_gui_status(client, "requested")
        client_command = client.get_command(client.client_id , "ping")        
        self.send_queue.put(client_command)
        
        
   
    #request all clients except station id  "i"
    def request_all_command(self, i ):
        for client in self.osc_clients:
            if client.client_id != i:
                self.request_command(client)
            
 
    #this function is used if a type A client sends a status command to update the client status and gui
    def set_client_gui_status(self, client, val):       
            if val == "triggered":
                val = client.set_button_was_pressed_state(True)
                self.gui.gui_update_button_status(client , "triggered")
                
            elif val == "clear":                
                val = client.set_button_was_pressed_state(False)
                self.gui.gui_update_button_status(client , "clear") 
                
            elif val == "online":
                client.set_online_status(True)
                self.gui.gui_update_button_status(client , "online")
                client.set_requested_flag(False)
                
            elif val == "offline":
                client.set_online_status(False)
                self.gui.gui_update_button_status(client , "offline")
                
            elif val == "requested":
                client.set_requested_flag(True)
                self.gui.gui_update_button_status(client , "requested") 
       
        
    #this function is used if a stop command is received to clear the status form type A clients
    #TODO clear the last recieved status in the network
    def clear_status(self):
        for client in self.trigger_osc_clients:            
            self.set_client_gui_status(client, "clear")
     
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
        if ("cmd" in args[0])  and  len(args) >= 3:
            try:
                cmd_client_id = int(args[1])    
                print("Error: args[1] is not an integer")            
                if 1 >= cmd_client_id <= len(self.osc_clients):                
                    if("s." in args[0]):
                        self.commandline_send_cmd(args)
                    elif("r." in args[0]):
                        self.commandline_receive_cmd(args)
                    else:
                        self.gui.print_command("Error: Invalid cmd argument")
            except ValueError:            
                self.gui.print_command("CMD Error: Invalid ID")
                    
        elif len(args) > 0 <= 2:
            self.gui.print_command(f"command unknown: {args}")           
            

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
                      
                      
    #commands the server can send      
    def commandline_send_cmd(self, args):        
            cmd_clinet_id = int(args[1])
            client = self.osc_clients[cmd_clinet_id-1]                   
            if client:                
                command = str(args[2])                    
                msg = ""
                if command in self.send_cmd_list:
                                       
                    if "msg" in command:
                        msg = str(args[3]) # so we can add another argument for commands like "Hello World"
                        self.send_queue.put(client.get_command(cmd_clinet_id, command , msg))
                        
                    #send gloabal status update to all station clients
                    elif "status" in command:
                        self.send_status_command(client)
                        
                    #send global stop command to all station clients   
                    elif "stop" in command:
                        self.send_confirm_command(client)
                    #send single command to a client
                    else:
                        self.send_queue.put(client.get_command(client, command))     
                else:
                    self.gui.print_command(f"Send command not found")
                    return
                            
                self.gui.print_command(f"Send test: {command} to ID:{cmd_line_id} - {client.name} ")
            
                self.gui.print_command(f"Error: No client found for {args[1]}")
                
    #commands the server can receive   
    def commandline_receive_cmd(self, args):
        cmd_clinet_id = int(args[1])
        client = self.osc_clients[cmd_clinet_id-1]
        command = str(args[2])
        if client:
            if command in self.receive_cmd_list:
                command = str(args[2])                    
                msg = ""       
                if command in self.receive_cmd_list:
                    if command == "msg":
                        msg = str(args[3])
                        self.handle_command(client , command , msg) #sends commandline input to command handler
                        return
                    else:
                        self.handle_command(client , command , msg)
                else:
                        self.gui.print_command(f"Send command not found")
                        return
                            
                self.gui.print_command(f"Send test: {command} from {client.name}: {msg} ")
            else:                          
                self.gui.print_command(f"Error: No client found for {args[1]}")
        


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
        







   
