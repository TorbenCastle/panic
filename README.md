
# OSC Server and GUI

This project is an OSC (Open Sound Control) server and GUI implemented in Python. It allows communication between various clients and provides a graphical user interface for managing OSC commands and monitoring the status of connected clients.

## Features

- OSC server handling messages from multiple clients.
- Graphical user interface (GUI) for interacting with clients.
- Command handling for various OSC commands.
- Logging functionality to keep track of important events.

The idea is to have a single OSC server to handle multible clients for lighting control, or other things

## Prerequisites

Make sure you have the following installed before running the application:

- Python 3.11
- Powersupply
- Network connection
- A computer


## Main functionality

The panic_handler.py opens a threading server that listens to incoming OSC messages.
At the moment, the server is configured to listen to incoming messages on port 9090.
It is sending to grandMA3 sequence 6001 thru 6012
The server is opening a thread for each incoming message, so multiple messages can be handled at the same time.
With the command handler, the server is handling the incoming messages and is sending messages to other clients.
The command handler is also updating the GUI with the status of the clients.


## Configuration
You can configure OSC clients by editing the data/config/config.ini file.
Each client is specified with a name, IP address, port, and station type (trigger, station, gma3).
The client_id is generated automatically when the programm starts.

All stations that can trigger, should be in the beginning of the config file,
followed by the stations that can be triggered.

the station_type can be one of the following:

	trigger: a station that can trigger other stations
	station: a station that can be triggered by other stations
	gma3: a station that can be triggered by other stations, but uses  GMA3 commands

Example:

[Client_1]
name = Client1
client_id = 1
ip = 192.168.1.2
port = 9001
station_type = trigger



## Logging

Logs are stored in the data/log/log.ini file.



## Usage

    The GUI provides commands for sending and receiving messages.
    Use the command line in the GUI for various operations (e.g., help, clients, test).
	Its will be possible to send commands to the server from the GUI in the future.
	Only a few commands are implemented at the moment.

	If a trigger client send its status to the server,
	the server will send a status message to all stations that can be triggered with the ID of the trigger.
	
	The station clients will start an own function to show the status of the trigger.
	The first station that confirm the status, will send a confirmation back to the server.
	Then the server clear the global status of all triggers on all other stations.

	The server can also confirm the status of a trigger.
	The server will ping one of all clients every 60 seconds, to check if the client is still connected.

	Red indicating the status of the trigger in the GUI.
	White indicating the online and trigger status of the client in the GUI.
	Grey indicating the offline status of the client in the GUI.
	Light blue if a ping is send to the client.
		
	By clicking on the client in the GUI, you can send a ping to the client.

## Known issues and further development

	T
	The GUI is not fully tested yet.
	The GUI commandline is not fully functional yet.
	The OSC server is not fully tested , functional , documented and configurable yet.
	
	

	When the server starting thread for every message, i havent set up a filter right.
	And the creating of the threaded server is in the class of the command_handler, it should be in the main function,
	but i havent figured out how to do that yet, there are too many crossed object requirements atm.

	At the moment the command handling, is passing object ids to other fuctions,
	this might be changed to passing the object itself.

	The global clear status function is not finnalized yet.
	better error handling and logging is needed.

	Moms spagetthi code, needs to be cleaned up and documented.