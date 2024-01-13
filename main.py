
import commands
from pythonosc.dispatcher import Dispatcher
import tkinter as tk
from osc_client import Osc_client
from osc_server import Osc_server
from gui import GuiHandler
from file_handler import File_handler
from osc_client import Osc_client
try:
    import RPi.GPIO as GPIO
    on_raspberry_pi = True

except ImportError:
    on_raspberry_pi = False
    
    

def main():
    try:
        relay_pin = 18      
        if on_raspberry_pi:
            # Code specific to Raspberry Pi with GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(relay_pin, GPIO.OUT)
            GPIO.output(relay_pin, GPIO.LOW)
        
        server_commands = commands.Commands("server_commands")
        text_handler = File_handler("text_handler")
        
        osc_objects =  text_handler.read_file("config")    
        osc_clients = [Osc_client(obj.name, obj.client_id, obj.ip, obj.port, obj.client_type) for obj in osc_objects]
        
        
        # Start the OSC server and Tkinter GUI
        root = tk.Tk()
        gui = GuiHandler(root, osc_clients , "#DDDDDD", "#FFFFFF", "#000000", text_handler ,  server_commands)
        
        osc_dispatcher = Dispatcher()   
        osc_server = Osc_server(osc_dispatcher, "0.0.0.0", 9090, osc_clients , gui , server_commands , text_handler)
        
        # Pass a reference to osc_server to text_handler
        gui.set_osc_server(osc_server)
        for client in osc_clients:
            client.set_gui(gui)
            
        text_handler.set_gui(gui)
        # Get the current local time and write it to the log file
                
        osc_server.start_server()        
        osc_server.start_handle()       
        gui.start_gui()
        
        
       
       #if running on an raspberry, it will trigger the relay on pin 18

    except Exception as e:
        if on_raspberry_pi:GPIO.cleanup() 
        # Handle exceptions here
        print(f"Error: {e}")
         
if __name__ == "__main__":
    
    main()
    
