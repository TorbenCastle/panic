import datetime
import os
from configparser import ConfigParser
from osc_client import Osc_client
import datetime
from datetime import datetime

import threading


class File_handler:
    def __init__(self, name):
        self.name = name    
        # Define the folder paths for config and log files
        self.config_folder = "data/config"
        self.log_folder = "data/log"     
        self.info_folder = "data/info"
        self.gui = None
        self.fog_log_bool = False
        self.config = ConfigParser()      
        self.lock = threading.Lock()
        
    def get_fog_log_bool(self):
        return self.fog_log_bool
    
    
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
                if file_name.endswith("log.ini"):
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
       

        for i, osc_object in enumerate(osc_objects, start=1):
            section_name = f"Client_{i}"
            self.config[section_name] = {
                'name': osc_object.name,
                'client_id': str(osc_object.client_id),
                'ip': osc_object.ip,
                'port': str(osc_object.port),
                'client_type': osc_object.client_type
            }
            self.gui.print_command_log(f"Writing config for {osc_object.name} {osc_object.client_type} {osc_object.client_id}")
        config_file_path = os.path.join(self.config_folder, 'config.ini')    
        with open(config_file_path, 'w') as configfile:
            self.config.write(configfile)
            configfile.flush()    
    
    def write_log(self, log_entry , file):
        with self.lock:
        
            try:
                if not os.path.exists(self.log_folder):
                    os.makedirs(self.log_folder)
                log_file_path = os.path.join(self.log_folder, file) 
                with open(log_file_path, 'a') as log_file:
                    # Append the log entry to a new line in the log file
                    log_file.write(f"{log_entry}\n")
                    log_file.close()

            except Exception as e:
                self.gui.print_command_log(f"Error writing to log file: {e}")
     
            

    def get_last_fog_number(self):
        file_path = "data/log/log_fog.ini"
        self.config.read(file_path)
        print("getting last fog number")
        for section_name in self.config.sections():
            fog_number = int(section_name.split()[1])
           
        
        return fog_number




    # write fogmachine data to ini
    def write_fog_log(self, fog_time_values):
        with self.lock:
            try:
                fog_number = self.get_last_fog_number() +1                
                if fog_number is None or 0:
                    fog_number = 1

                # Create a new section with the incremented fog number
                section_name = f'FOG {fog_number}'
                self.config.add_section(section_name)

                for i, (timestamp, value) in enumerate(fog_time_values, start=1):
                    self.config.set(section_name, f'time_value_{i}', f'{timestamp}')
                    self.config.set(section_name, f'fog_value_{i}', f'{value}')
                    
                log_file_path = os.path.join(self.log_folder, 'log_fog.ini')
                with open(log_file_path, 'w') as fog_log_file:
                    self.config.write(fog_log_file)
                    fog_log_file.close()
                    print("FOG LOG DONE")

            except Exception as e:
                print(f"Error writing to log file: {e}")
                


      # read fog log to graph       
    
    def process_fog_log(self):
        result = []
        file_path = "data/log/log_fog.ini"
        self.config.read(file_path)

        for section_name in self.config.sections():
            values_list = []  # Reset values_list for each section
            print(f"Processing section: {section_name}")
            for key, value in self.config.items(section_name):
                # Check if the key is in the format 'time_value_' or 'fog_value_'
                if key.startswith('time_value_'):
                    time_str = value.strip()
                    date_object = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                elif key.startswith('fog_value_'):
                    # Ensure 'fog_value_' key has a corresponding value
                    if value:
                        fader_value = float(value.strip())
                        # Append the pair to the values_list
                        values_list.append((date_object, fader_value))
                    else:
                        print(f"Warning: No value found for key {key} in section {section_name}")
        
            print(f"Values for section {section_name}: {values_list}")
            result.append((section_name, values_list))

        return result
    
