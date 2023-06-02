# Optitrack Bridge

## Getting started
This repository contains all the files needed to communicate with the optitrack system and to send the data to a websocket server. <br>
The code in this repository is a modified version of the NatNet SDK for Python (you can find more informations in the <b>Third party libraries</b>). <br><br>
The schema of the Optitrack Bridge is: <br>
![Alt Text](readme-files/schema.png)

## Installation
To install this repository you can clone it and then install the requirements with the command:
To install this repository you just need to clone it. <br>
After that you need to install the requirements with the command:
```
pip install -r requirements.txt
```
Before running the <code>main.py</code> file it's important that you verify that:
- You are in the same network of the Optitrack system which you want to stream informations from
- On the Optitrack system the streaming of data is turned on
- You have set up the parameters in the <code>modules/settings.py</code> file (such as the client address, the server addres, ...)
- The websocket server is up and running

If you are running the program with a manager (e.g. <code>supervisord</code>) is suggested to set the variable <code>LOGGING_ON_STDOUT</code> in the file <code>settings.py</code> to <code>False</code> while is recomended to put it to <code>True</code> if you are running it in a command windows. <br>
The logging on the stdout (controller with the variable <code>LOGGING_ON_STDOUT</code>) is set to a logging level of **DEBUG** while the logging on the file is set to a logging level of **INFO**. <br>

## Modify the code
In this case the code has been adapted to send only few specific data. 
- If you wish to send different type of data (e.g. skeleton, cameras info, ...) you should modify the function <code>__unpack_mocap_data(...)</code> of the class <code>NatNetClient</code> (and in particular the sub-function <code>makeDataReadyForWebsocket(data)</code>) which is in the file <code>NatNetClient.py</code>.
- The bridge apply a filter on the input data and send only the informations relative to specific rigid bodies to the websocket server. <br>
If you wish to remove this filter or you wish to modify the filtered rigidbody please modify the <code>filter.py</code> file.

## Third party libraries
The only third party library that is used in the code (other than the modules in <code>requirements.txt</code>) is [NatNet SDK for Python v.4.0.0](https://optitrack.com/support/downloads/developer-tools.html).

## Authors
This repository is part of the project *"Mixed Reality Environment For Harvesting Study"* done by Alessandro Dalbesio.<br>
The project has been done in the CREATE LAB (EPFL).<br>
Professor: Josie Hughes<br>
Supervisor: Ilic Stefan<br>

## License
This project is under [MIT] license