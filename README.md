# Python3 CAN bus monitor

This script allows you to read live data from a CAN bus and display it in an easy-to-read table.

This is a fork from https://github.com/alexandreblin/python-can-monitor (thanks to him!)

The only differences are that it uses python3, and that it can communicates
with CAN device over network interfaces (like `vcan0` for tests for example)

## Usage
Install the dependencies (preferably in a virtualenv)

    pip install -r requirements.txt

Launch the script

    ./canmonitor.py <network interface>

Press Q at any time to exit the script.

## Example

    ./canmonitor.py vcan0

![Screenshot](http://i.imgur.com/1nqCQKz.png)

