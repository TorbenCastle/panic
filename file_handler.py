import os
from configparser import ConfigParser
from osc_client import Osc_client



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
