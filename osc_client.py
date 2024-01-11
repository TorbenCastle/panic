import time
from pythonosc import udp_client
from configparser import ConfigParser



        
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
        
        self.ping_request_flag = False  # Initialize the requested flag to false 
        self.timer_start = None  # Initialize the timer start time to None
        self.response_time = None  # Initialize the response time to None
        self.timeout_threshold = 5  # Set the timeout threshold to 5 seconds
        self.online = False # Initialize the online status to False
        self.message_commands = ["msg" , "var1" , "var2"]


    def send_msg(self, cmd, *args):
        receiver = udp_client.SimpleUDPClient(self.ip, self.port)
       
        if self.client_type == "gma3":
            if len(args) == 0:
                self.gui.print_command_log("Error: Invalid number of arguments for 'msg' command")
                return
           
        msg = " ".join(map(str, args))
        msg = msg.strip()
        message = f'setUserVar "message_in" "{str(msg)}"'
        
                
        self.gui.print_command(f"Sending {message} command to grandma3")
        receiver.send_message("/cmd", [message])
        time.sleep(0.1)
        receiver.send_message("/cmd", ["Call plugin 6"])  


    #send command function
    def send_data(self,value, cmd , msg = None):
        # if its a message command, build the message
        if(cmd in self.message_commands):
            self.send_msg_to_client(msg)
            return
        if(cmd == "status"):id_value = value
        else:
            id_value = self.client_id   
        
        #set up the udp client before sending the command
        receiver = udp_client.SimpleUDPClient(self.ip, self.port)
        #the address ("/cmd") can be filtered by the osc client)
        #gma3 is recieving a command with only one argument
        if self.client_type == "gma3":
            receiver.send_message("/cmd", [cmd])
            self.gui.print_command_log(f"Sending /cmd,{cmd}")
        else:       
            receiver.send_message("/cmd", [id_value , cmd])
           
            self.gui.print_command_log(f"Sending /cmd,{id_value},{cmd}")
        
    def get_command(self, cmd , val ):
            
        #if the client is a gma3, the command is different, status command can send to different sequences
        if self.client_type == "gma3":
            return(self.get_C_command(val, str(cmd)))
        
        #the status command is adding the trigger if, to start different sequences
        elif cmd == "status":
                cmd = (f"status {str(val)}")
        else:
            val = self.client_id
        
        return (str(val) , str(cmd))
        
    

    #commands send to grandma3
    def get_C_command(self, val, cmd):
                    

        command_mappings = {
            "status": f"Go+ Sequence {6000 + val}" if self.mode == "normal" else "On Sequence 6008",
            "stop": "Go+ Sequence 6009",
            "ping": "Go+ Sequence 6011",
            "debug": "Go+ Sequence 6006",
            "special": "Go+ Sequence 6007",
            "released": "Off Sequence 6008",
            "confirm": "Go+ Sequence 6010",             
        }

        gma3_cmd = command_mappings.get(cmd, None)

        if gma3_cmd is None:
            self.gui.print_command("Command not found for grandma3")
            return False

        return (self.client_id , gma3_cmd)


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

    def set_ping_request_flag(self, value):
            self.ping_request_flag = value
            if value:                
                self.start_timer()
            else:                
                self.stop_timer()
                
    def get_ping_request_flag(self):
        return self.ping_request_flag

    def check_ping_timeout(self):
        if self.timer_start is not None:
            elapsed_time = time.time() - self.timer_start
            if elapsed_time > self.timeout_threshold:
                self.stop_timer()
                self.ping_request_flag = False
                self.gui.print_command_log(f"Timeout: Client {self.name} ID:{self.client_id} is not available.")  
                self.online = False                
                self.gui.gui_update_button_status(self , "offline")
                
    def get_online_status(self):
        return self.online  
    
    def set_online_status(self, val):
        self.online = val
        
 

    def start_timer(self):
        self.timer_start = time.time()

    def stop_timer(self):
        if self.timer_start is not None:
            self.timer_start = None

    def get_response_time(self):
        self.response_time = int((time.time() - self.timer_start)*1000)
        self.online = True        
        return self.response_time
    

    

               
