
        
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
    

    

               
