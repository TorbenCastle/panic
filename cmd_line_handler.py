class CommandLineHandler:
    def __init__(self, osc_clients,gui,osc_server):
        self.osc_clients = osc_clients
        self.gui = gui
        self.osc_server = osc_server
        self.client_attribute = {"name", "client_id", "ip", "port", "client_type"}
        
        
        # Define a dictionary to map command keywords to functions
        self.command_functions = {
            "send": self.handle_send_command,
            "get": self.handle_get_command,
            "help": self.handle_help_command,
            "clients": self.handle_clients_command
            # Add more commands as needed
        }
        self.send_functions={
			"cmd": self.commandline_send_commands,
			"get": self.commandline_receive_commands
		}

    def gui_command(self, command):
        print(f"gui_command = {command}")
        if len(command) == 0:
            return

        args = command.split(" ")
        command_keyword = args[0]

        # Check if the command keyword is in the dictionary
        if command_keyword in self.command_functions:
            # Call the corresponding function
            self.command_functions[command_keyword](args[1:])
        else:
            self.gui.print_command_log("Error: Invalid command")
            
    # Check if the correct number of arguments is provided
    def handle_send_command(self, args):
        client = self.get_client(args[0])
        if len(args) >= 2:
            if client in self.osc_clients:
                self.commandline_send_cmd(client, args[1], "")
            else:
                self.gui.print_command_log("Error: Client not found")
        else:
            self.gui.print_command_log("Error: Invalid number of arguments for 'send' command")

    def handle_get_command(self, args):
        
        if len(args) >= 2:
            client = self.get_client(args[0])
            if client in self.osc_clients:
                self.commandline_receive_cmd(client, args[1], "")
            else:
                self.gui.print_command_log("Error: Client not found")
        else:
            self.gui.print_command_log("Error: Invalid number of arguments for 'get' command")

    def handle_help_command(self, args):
        # Implement the logic for the "help" command
        if len(args) == 0:
            self.gui.print_command("--------------------------------------")            
            self.gui.print_command("Send command ID")                   
            self.gui.print_command(f"\"clients\" return all clients")                   
            self.gui.print_command(f"\"send ID command\" send a test command to an id")
            self.gui.print_command(f"\"get name command\" receive a test command from a client with name")

        elif args[0] == "cmd":
            self.gui.print_command("--------------------------------------")
            

    def handle_clients_command(self, args):
        # Implement the logic for the "clients" command
        if len(args) == 0:
            self.gui.print_command("--------------------------------------")
            self.gui.print_command(f"All registered clients:")
            for client in self.osc_clients:
                self.gui.print_command(f"Name: {client.get_name()} ID: {client.get_id()} IP: {client.get_ip()}:{client.get_port()} Type: {client.get_type()}")
              

        elif len(args) == 2:
            attribute = args[0]
            value = args[1]
            if attribute in self.client_attribute:
                matching_clients = self.get_clients_by_identifier({attribute})
                if matching_clients:
                    for client in matching_clients:
                        if attribute == "name":
                            self.gui.print_command(f"Found: {client.get_name()} ID: {client.get_id()}")
                        else:
                            self.gui.print_command(f"Found: {client.get_name()} with {attribute}")
                else:
                    self.gui.print_command(f"No clients found with {attribute}")
            else:
                self.gui.print_command("--------------------------------------")
                self.gui.print_command("Type \"clients\" \"name , client_id , ip , port or client_type\"")
                self.gui.print_command("to get a list all clients with type station or other value")
        else:
            self.gui.print_command_log("Error: Invalid number of arguments for 'clients' command")
