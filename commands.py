# this is a dictionary to handle commands
class Commands:
    def __init__(self, name):
        self.name = name
        self.send = {}
        self.receive = {}
        
        server_all_cmd_dict = {
                1: ("status"),
                2: ("stop"),
                3: ("ping"),
                4: ("confirm"),
                5: ("response"),
                6: ("trigger"),
                7: ("debug"),
                8: ("special")
        }

        server_send_dict = {
                1: ("status"),
                2: ("stop"),
                3: ("ping"),
                4: ("confirm"),                
                5: ("trigger"),
                6: ("debug"),
                7: ("special")
        }

     
        

        self.all_commands = server_all_cmd_dict
        self.all_send_commands = server_send_dict    
        