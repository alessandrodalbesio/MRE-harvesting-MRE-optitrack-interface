# Optitrack Interface

## Getting started
This repository contains all the files needed to communicate with the optitrack system and to send the data to a websocket server. <br>
The code in this repository is a modified version of the NatNet SDK for Python (you can find more informations in the <b>Third party libraries</b>).

## Installation
After cloning this repository before running the <code>main.py</code> file it's important that you verify that:
- You are in the same network of the Optitrack system which you want to stream informations from
- On the Optitrack system the streaming of data is turned on
- You have set up the parameters in the <code>modules/Settings.py</code> file (such as the client address, the server addres, ...) (p.s. if these parameters are not set the program won't start)
- You're websocket server is up and running (otherwise it will shut down immediately)

If you are running the program with a manager (e.g. <code>supervisord</code>) is suggested to set the variable <code>LOGGING_ON_STDOUT</code> in the file <code>Settings.py</code> while is recomended to put it to true if you are running it in a command windows. <br>
The logging on the stdout (controller with the variable <code>LOGGING_ON_STDOUT</code>) is set to a logging level of DEBUG while the logging on the file is set to a logging level of INFO.

## Adapt the code for you work
In this case the code has been adapted to send only specific data (frame_number, timestamp and labeled_marked_data). <br>
If you wish to send different data (e.g. skeleton or rigidbodies) you should modify the function <code>NatNetClient.__unpack_mocap_data(...)</code> (and in particular the sub-function <code>makeDataReadyForWebsocket(data)</code>) which is in the file <code>NatNetClient.py</code>.

## Third party libraries
The only third party library that is used in the code (other than the modules in <code>requirements.txt</code>) is [NatNet SDK for Python v.4.0.0](https://optitrack.com/support/downloads/developer-tools.html). <br>
The original Python files can be found in the folder <code>NatNet SDK (Python)</code>

## Authors
This repository is part of the project *"Mixed Reality Environment For Harvesting Study"* done by Alessandro Dalbesio.<br>
The project has been done in the CREATE LAB (EPFL).<br>
Professor: Josie Hughes<br>
Supervisor: Ilic Stefan<br>

## License
This project is under [MIT] license