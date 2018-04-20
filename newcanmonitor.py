#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import curses
import datetime
import sys
import threading
import traceback

import can

should_redraw = threading.Event()
stop_bus = threading.Event()

can_messages = {}
can_messages_lock = threading.Lock()

thread_exception = None

DELTA_TIME_TRIGGER = 0.01
RESET_COLOR_COUNTER_VALUE = 50

# This whole script is hacky
# Please protect your eyes with something less violent,
# like... acid idk, if you are willing to read it anyway
# MESSAGES TUPLE FORMAT (ANCHOR_TUPLE_FORMAT)
FRAME_ID_NEW_MESSAGE = 0 # This frame ID sent a new message, so save it
FRAME_ID_OLD_MESSAGE = 1 # Save the previous message also, to compare
FRAME_ID_LAST_CHANGE = 2 # Time at which the last modification occured
FRAME_ID_MESSAGE_CHANGED = 3 # Did a new message appear after last refresh ?
FRAME_ID_COLOR_COUNTER = 4 # How many iteration should we color the message for


def read_bus(bus_device):
    """Read data from `bus_device` until the next newline character."""
    message = bus.recv(0.2)
    while True:
        if message:
            break
        message = bus.recv(0.2)

    try:
        string = "{}:ID={}:LEN={}".format("RX", message.arbitration_id, message.dlc)
        for x in range(message.dlc):
            string += ":{:02x}".format(message.data[x])

    except Exception as e:
        print(e)
    return string


def bus_run_loop(bus_device):
    """Background thread for serial reading."""
    try:
        while not stop_bus.is_set():
            line = read_bus(bus_device)

            # Sample frame from Arduino: FRAME:ID=246:LEN=8:8E:62:1C:F6:1E:63:63:20
            # Split it into an array (e.g. ['FRAME', 'ID=246', 'LEN=8', '8E', '62', '1C', 'F6', '1E', '63', '63', '20'])
            frame = line.split(':')

            try:
                frame_id = int(frame[1][3:])  # get the ID from the 'ID=246' string
                frame_length = int(frame[2][4:])  # get the length from the 'LEN=8' string

                data = [int(byte, 16) for byte in frame[3:]]  # convert the hex strings array to an integer array
                data = [byte for byte in data if byte >= 0 and byte <= 255]  # sanity check


                if len(data) != frame_length:
                    # Wrong frame length or invalid data
                    continue

                # Add the frame to the can_messages dict and tell the main thread to refresh its content
                # See ANCHOR_TUPLE_FORMAT for information
                with can_messages_lock:
                    try:
                        can_messages[frame_id] = (data,
                                can_messages[frame_id][FRAME_ID_NEW_MESSAGE], # New message becomes old message
                                (datetime.datetime.now() - can_messages[frame_id][FRAME_ID_LAST_CHANGE]).total_seconds(),
                                True,
                                can_messages[frame_id][FRAME_ID_COLOR_COUNTER])
                    except Exception as e:
                        can_messages[frame_id] = (data, [0], DELTA_TIME_TRIGGER, True, 0)
                    should_redraw.set()
            except Exception as e:
                # Invalid frame
                continue
    except:
        if not stop_bus.is_set():
            # Only log exception if we were not going to stop the thread
            # When quitting, the main thread calls close() on the serial device
            # and read() may throw an exception. We don't want to display it as
            # we're stopping the script anyway
            global thread_exception
            thread_exception = sys.exc_info()


def init_window(stdscr):
    """Init a window filling the entire screen with a border around it."""
    stdscr.clear()
    stdscr.refresh()

    max_y, max_x = stdscr.getmaxyx()
    root_window = stdscr.derwin(max_y, max_x, 0, 0)

    root_window.box()

    return root_window


def main(stdscr, bus_thread):
    """Main function displaying the UI."""
    # Don't print typed character
    curses.noecho()
    curses.cbreak()

    # Set getch() to non-blocking
    stdscr.nodelay(True)

    win = init_window(stdscr)
    curses.start_color()
    curses.init_pair(1, 3, 4) # Marine Blue
    curses.init_pair(2, 5, 6) # Turquoise Blue
    curses.init_pair(3, 7, 8) # Gray

    while True:
        # should_redraw is set by the serial thread when new data is available
        if should_redraw.is_set():
            max_y, max_x = win.getmaxyx()

            column_width = 70
            id_column_start = 2
            id_padding = 14
            bytes_column_start = 15 + id_padding
            text_column_start = 45 + id_padding

            # Compute row/column counts according to the window size and borders
            row_start = 3
            lines_per_column = max_y - (1 + row_start)
            num_columns = int((max_x - 2) / column_width)

            # Setting up column headers
            for i in range(0, num_columns):
                win.addstr(1, id_column_start + i * column_width, 'ID')
                win.addstr(1, bytes_column_start + i * column_width, 'Bytes')
                win.addstr(1, text_column_start + i * column_width, 'Text')

            win.addstr(3, id_column_start, "Press 'q' to quit")

            row = row_start + 2  # The first column starts a bit lower to make space for the 'press q to quit message'
            current_column = 0

            # Make sure we don't read the can_messages dict while it's being written to in the serial thread
            with can_messages_lock:
                for frame_id in sorted(can_messages.keys()):
                    msg = can_messages[frame_id][FRAME_ID_NEW_MESSAGE]

                    # convert the bytes array to an hex string (separated by spaces)
                    msg_bytes = ' '.join('%02X' % byte for byte in msg)

                    # try to make an ASCII representation of the bytes
                    # nonprintable characters are replaced by '?'
                    # and spaces are replaced by '.'
                    msg_str = ''
                    for byte in msg:
                        char = chr(byte)
                        if char == '\0':
                            msg_str = msg_str + '.'
                        elif ord(char) < 32 or ord(char) > 126:
                            msg_str = msg_str + '?'
                        else:
                            msg_str = msg_str + char

                    # print frame ID in decimal and hex
                    #win.addstr(row, id_column_start + current_column * column_width, '%s' % str(frame_id).ljust(8))
                    color = None
                    #COLOR_ONE = curses.color_pair(1)
                    #COLOR_TWO = curses.color_pair(2)
                    #COLOR_THREE = curses.color_pair(3)
                    COLOR_ONE = curses.A_STANDOUT
                    COLOR_TWO = curses.A_STANDOUT
                    COLOR_THREE = curses.A_STANDOUT
                    update_color_counter = False

                    try:
                        if can_messages[frame_id][FRAME_ID_COLOR_COUNTER] > 0:
                            color = COLOR_THREE
                    except Exception as e:
                        #win.addstr(42, text_column_start + current_column * column_width, "0:{0}".format(e))
                        pass

                    try:
                        if (can_messages[frame_id][FRAME_ID_MESSAGE_CHANGED]
                            and can_messages[frame_id][FRAME_ID_LAST_CHANGE] >= DELTA_TIME_TRIGGER):
                            if len(can_messages[frame_id][FRAME_ID_OLD_MESSAGE]) != len(can_messages[frame_id][FRAME_ID_NEW_MESSAGE]):
                                color = COLOR_ONE
                                update_color_counter = True
                            else:
                                for i, b in enumerate(can_messages[frame_id][FRAME_ID_NEW_MESSAGE]):
                                    if b != can_messages[frame_id][FRAME_ID_OLD_MESSAGE][i]:
                                        color = COLOR_TWO
                                        update_color_counter = True
                                        break
                    except Exception as e:
                        #win.addstr(43, text_column_start + current_column * column_width, "1:{0}".format(e))
                        pass

                    try:
                        # new messages arrived
                        new_timestamp = datetime.datetime.now() if color else datetime.datetime.now() + datetime.timedelta(seconds=can_messages[frame_id][FRAME_ID_LAST_CHANGE])
                    except Exception as e:
                        # message was not updated between now and last refresh
                        pass

                    can_messages[frame_id] = (can_messages[frame_id][FRAME_ID_NEW_MESSAGE],
                            can_messages[frame_id][FRAME_ID_OLD_MESSAGE],
                            new_timestamp,
                            False,
                            RESET_COLOR_COUNTER_VALUE if update_color_counter else can_messages[frame_id][FRAME_ID_COLOR_COUNTER] - 1)

                    win.addstr(row, id_column_start + id_padding + current_column * column_width, '{:08x}'.format(frame_id))

                    # print frame bytes
                    if color:
                        win.addstr(row, bytes_column_start + current_column * column_width, msg_bytes.ljust(23), color)
                    else:
                        win.addstr(row, bytes_column_start + current_column * column_width, msg_bytes.ljust(23))

                    # print frame text
                    win.addstr(row, text_column_start + current_column * column_width, msg_str.ljust(8))
                    #win.addstr(row, text_column_start + 10 + current_column * column_width, "--- {0} - {1}{2}".format(can_messages[frame_id][FRAME_ID_LAST_CHANGE], can_messages[frame_id][FRAME_ID_COLOR_COUNTER], " " * 30))

                    row = row + 1

                    if row >= lines_per_column + row_start:
                        # column full, switch to the next one
                        row = row_start
                        current_column = current_column + 1

                        if current_column >= num_columns:
                            break

            win.refresh()

            should_redraw.clear()

        c = stdscr.getch()
        if c == ord('q') or not bus_thread.is_alive():
            break
        elif c == curses.KEY_RESIZE:
            win = init_window(stdscr)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Process CAN data from a socket-can device.')
    parser.add_argument('interface', default='can0')

    args = parser.parse_args()

    bus_device = None
    bus_thread = None

    try:
        bus = can.interface.Bus(channel=args.interface, bustype='socketcan_native')

        # Start the bus reading background thread
        bus_thread = threading.Thread(target=bus_run_loop, args=(bus,))
        bus_thread.start()

        # Make sure to draw the UI the first time even if there is no data
        should_redraw.set()

        # Start the main loop
        curses.wrapper(main, bus_thread)

    finally:
        # Cleanly stop bus thread before exiting
        if bus_thread:
            stop_bus.set()

            bus_thread.join()

            # If the thread returned an exception, print it
            if thread_exception:
                traceback.print_exception(*thread_exception)
                sys.stderr.flush()
