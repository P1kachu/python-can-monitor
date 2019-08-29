# Python3 CAN bus monitor

This script allows you to read live data from a CAN bus and display it in an easy-to-read table.

This is a fork from https://github.com/alexandreblin/python-can-monitor (thanks to him!)

The only differences are that it uses python3, and that it can communicates
with CAN device over network interfaces (like `vcan0` for tests for example)

## newcanmonitor.py

This is a dev version of the same canmonitor, but with some message coloring
when bytes change. I use it internally to spot more easily changing bytes when
I try things in the car. The code is quite ugly, this is just a dirty hack that
has not been tested that much. Don't expect much of it, and use the standard
`canmonitor.py` if you want something more stable.

## Usage
Install the dependencies (preferably in a virtualenv)

    pip install -r requirements.txt

Launch the script

    ./canmonitor.py <network interface>

Press Q at any time to exit the script.

Sending a special frame (right now, `777#0707070707070707`) will reset the screen
Adding arbitration ids to BLACKLIST or WHITELIST can allow you to select what
you want and don't want to see when there are too many messages.

## Example

    ./canmonitor.py vcan0

![Screenshot](http://i.imgur.com/1nqCQKz.png)


