#!/usr/bin/env python3

# Program to read Chinese dial indicator from serial port and display it
# in curses screen.
#
# When run, the program will scan for serial ports. If more than one
# is available, the ports will be listed out. If only one is available,
# it is assumed to be the one connected to the arduino outputing
# data from the dial indicator/digital calipers.

import argparse
import contextlib
import curses
import curses.ascii
import re
import select
import serial
from serial.tools import list_ports
import signal
import signalfd
import sys

INDICATOR_RE = re.compile(r'(?P<number>-?\d+\.\d+)\s+(?P<unit>\S+)')

def GetPort(list_only=False):
  """Find available serial ports"""
  count = 0
  port_list = list_ports.comports()
  if not port_list:
    print('No ports found')
    sys.exit(0)
    
  # If list_only or more than one port available, print and exit.
  if list_only or len(port_list) > 1:
    for port, desc, hwid in port_list:
      print(f'port={port}, desc={desc}, hwid={hwid}')
    sys.exit(0)
    
  # Only one port available
  return port_list[0][0]


# Base characters are used to change the style of the font
# displayed on the screen.
# U+2022 • (Bullet)
# U+26AB ⚫ (Medium Black Circle Emoji)
# U+2B24 ⬤ (Large Black Cirlce)
# U+23FA ⏺ (Black Circle for Record Emoji)
# U+25CF ● (Black Circle)
BASE_CHARACTERS = (' ', '#', '•', '⬤', '⏺', '●', '⬩', '♦')

# For each "font", the space and hyphen need to be the same width
# in order to keep the displayed aligned the same for both positive
# and negative values.

CHAR_SET1 = {
  # Numbers are 8 Rows x 6 Cols
  '0': [' ###  ', 
        '#   # ',
        '#   # ', 
        '#   # ', 
        '#   # ',
        '#   # ', 
        ' ###  ', 
        '      '],
  '1': [' ##   ',
        '# #   ',
        '  #   ',
        '  #   ',
        '  #   ',
        '  #   ',
        '##### ',
        '      '],
  '2': [' ###  ',
        '#   # ',
        '    # ',
        ' ###  ',
        '#     ',
        '#     ',
        '##### ',
        '      '],
  '3': [' ###  ',
        '#   # ',
        '    # ',
        ' ###  ',
        '    # ',
        '#   # ',
        ' ###  ',
        '      '],
  '4': ['#   # ',
        '#   # ',
        '#   # ',
        '##### ',
        '    # ',
        '    # ',
        '    # ',
        '      '],
  '5': ['####  ',
        '#     ',
        '#     ',
        ' ###  ',
        '    # ',
        '    # ',
        '####  ',
        '      '],
  '6': [' ###  ',
        '#     ',
        '#     ',
        '####  ',
        '#   # ',
        '#   # ',
        ' ###  ',
        '      '],
  '7': ['##### ',
        '#   # ',
        '    # ',
        '   #  ',
        '  #   ',
        ' #    ',
        ' #    ',
        '      '],
  '8': [' ###  ',
        '#   # ',
        '#   # ',
        ' ###  ',
        '#   # ',
        '#   # ',
        ' ###  ',
        '      '],
  '9': [' ###  ',
        '#   # ',
        '#   # ',
        ' #### ',
        '    # ',
        '    # ',
        ' ###  ',
        '      '],
  # Non-uniform sizes
  'i': ['  ',
        '# ',
        '  ',
        '# ',
        '# ',
        '# ',
        '# ',
        '  '],
  'n': ['      ',
        '      ',
        '      ',
        ' ###  ',
        '#   # ',
        '#   # ',
        '#   # ',
        '      '],
  'm': ['        ',
        '        ',
        '        ',
        ' ## ##  ',
        '#  #  # ',
        '#  #  # ',
        '#  #  # ',
        '        '],
  '-': ['    ',
        '    ',
        '    ',
        '### ',
        '    ',
        '    ',
        '    ',
        '    '],
  ' ': ['    ',
        '    ',
        '    ',
        '    ',
        '    ',
        '    ',
        '    ',
        '    '],
  '.': ['  ',
        '  ',
        '  ',
        '  ',
        '  ',
        '  ',
        '# ',
        '  '],
  '?': [' ###  ',
        '#   # ',
        '    # ',
        '   #  ',
        '  #   ',
        '      ',
        '  #   ',
        '      '],
 }

CHAR_SET2 = {
  # Numbers are 8 Rows x 8 Cols
  '0': [' #####  ', 
        '##   ## ',
        '##   ## ', 
        '##   ## ', 
        '##   ## ',
        '##   ## ', 
        ' #####  ', 
        '        '],
  '1': [' ####   ',
        '#  ##   ',
        '   ##   ',
        '   ##   ',
        '   ##   ',
        '   ##   ',
        '####### ',
        '        '],
  '2': [' #####  ',
        '##   ## ',
        '     ## ',
        ' #####  ',
        '##      ',
        '##      ',
        '####### ',
        '        '],
  '3': [' #####  ',
        '##   ## ',
        '     ## ',
        ' #####  ',
        '     ## ',
        '##   ## ',
        ' #####  ',
        '        '],
  '4': ['##   ## ',
        '##   ## ',
        '##   ## ',
        '####### ',
        '     ## ',
        '     ## ',
        '     ## ',
        '        '],
  '5': ['######  ',
        '##      ',
        '##      ',
        ' #####  ',
        '     ## ',
        '     ## ',
        '######  ',
        '        '],
  '6': [' #####  ',
        '##      ',
        '##      ',
        '######  ',
        '##   ## ',
        '##   ## ',
        ' #####  ',
        '        '],
  '7': ['####### ',
        '##   ## ',
        '     ## ',
        '    ##  ',
        '   ##   ',
        '  ##    ',
        '  ##    ',
        '        '],
  '8': [' #####  ',
        '##   ## ',
        '##   ## ',
        ' #####  ',
        '##   ## ',
        '##   ## ',
        ' #####  ',
        '        '],
  '9': [' #####  ',
        '##   ## ',
        '##   ## ',
        ' ###### ',
        '     ## ',
        '     ## ',
        ' #####  ',
        '        '],
  # Non-uniform sizes
  'i': ['  ',
        '# ',
        '  ',
        '# ',
        '# ',
        '# ',
        '# ',
        '  '],
  'n': ['      ',
        '      ',
        '      ',
        ' ###  ',
        '#   # ',
        '#   # ',
        '#   # ',
        '      '],
  'm': ['        ',
        '        ',
        '        ',
        ' ## ##  ',
        '#  #  # ',
        '#  #  # ',
        '#  #  # ',
        '        '],
  '-': ['     ',
        '     ',
        '     ',
        '#### ',
        '     ',
        '     ',
        '     ',
        '     '],
  ' ': ['     ',
        '     ',
        '     ',
        '     ',
        '     ',
        '     ',
        '     ',
        '     '],
  '.': ['  ',
        '  ',
        '  ',
        '  ',
        '  ',
        '  ',
        '# ',
        '  '],
  '?': [' #####  ',
        '##   ## ',
        '     ## ',
        '    ##  ',
        '   ##   ',
        '        ',
        '   ##   ',
        '        '],
 }

CHAR_SET3 = {
  # Numbers are 10 Rows x 8 Cols
  '0': [' #####  ', 
        '####### ',
        '##   ## ',
        '##   ## ', 
        '##   ## ', 
        '##   ## ',
        '##   ## ', 
        '####### ',
        ' #####  ', 
        '        '],
  '1': [' ####   ',
        '#####   ',
        '## ##   ',
        '   ##   ',
        '   ##   ',
        '   ##   ',
        '   ##   ',
        '####### ',
        '####### ',
        '        '],
  '2': [' #####  ',
        '####### ',
        '##   ## ',
        '     ## ',
        ' #####  ',
        '##      ',
        '##      ',
        '####### ',
        '####### ',
        '        '],
  '3': [' #####  ',
        '####### ',
        '##   ## ',
        '     ## ',
        ' #####  ',
        '     ## ',
        '##   ## ',
        '####### ',
        ' #####  ',
        '        '],
  '4': ['##   ## ',
        '##   ## ',
        '##   ## ',
        '##   ## ',
        '####### ',
        '####### ',
        '     ## ',
        '     ## ',
        '     ## ',
        '        '],
  '5': ['######  ',
        '######  ',
        '##      ',
        '##      ',
        ' #####  ',
        '     ## ',
        '     ## ',
        '######  ',
        '#####   ',
        '        '],
  '6': [' #####  ',
        '######  ',
        '##      ',
        '##      ',
        '######  ',
        '##   ## ',
        '##   ## ',
        ' #####  ',
        '  ###   ',
        '        '],
  '7': ['####### ',
        '####### ',
        '##   ## ',
        '     ## ',
        '    ##  ',
        '   ##   ',
        '  ##    ',
        '  ##    ',
        '  ##    ',
        '        '],
  '8': [' #####  ',
        '####### ',
        '##   ## ',
        '##   ## ',
        ' #####  ',
        '##   ## ',
        '##   ## ',
        '####### ',
        ' #####  ',
        '        '],
  '9': [' #####  ',
        '####### ',
        '##   ## ',
        '##   ## ',
        ' ###### ',
        '     ## ',
        '     ## ',
        ' #####  ',
        ' ####   ',
        '        '],
  # Non-uniform sizes
  'i': ['  ',
        '## ',
        '## ',
        '   ',
        '## ',
        '## ',
        '## ',
        '## ',
        '## ',
        '   '],
  'n': ['        ',
        '        ',
        '        ',
        '        ',
        ' #####  ',
        '##   ## ',
        '##   ## ',
        '##   ## ',
        '##   ## ',
        '        '],
  'm': ['          ',
        '          ',
        '          ',
        '          ',
        ' ### ###  ',
        '##  #  ## ',
        '##  #  ## ',
        '##  #  ## ',
        '##  #  ## ',
        '          '],
  '-': ['     ',
        '     ',
        '     ',
        '     ',
        '#### ',
        '     ',
        '     ',
        '     ',
        '     ',
        '     '],
  ' ': ['     ',
        '     ',
        '     ',
        '     ',
        '     ',
        '     ',
        '     ',
        '     ',
        '     ',
        '     '],
  '.': ['   ',
        '   ',
        '   ',
        '   ',
        '   ',
        '   ',
        '   ',
        '## ',
        '## ',
        '   '],
  '?': [' #####  ',
        '####### ',
        '##   ## ',
        '     ## ',
        '    ##  ',
        '   ##   ',
        '   ##   ',
        '        ',
        '   ##   ',
        '        '],
 }

CHAR_SET4 = {
  # Numbers are 11 Rows x 10 Cols
  '0': [' #######  ', 
        '######### ',
        '##     ## ',
        '##     ## ', 
        '##     ## ', 
        '##     ## ', 
        '##     ## ',
        '##     ## ', 
        '######### ',
        ' #######  ', 
        '          '],
  '1': [' #####    ',
        '######    ',
        '## ###    ',
        '   ###    ',
        '   ###    ',
        '   ###    ',
        '   ###    ',
        '   ###    ',
        '######### ',
        '######### ',
        '          '],
  '2': [' #######  ',
        '######### ',
        '##     ## ',
        '       ## ',
        '  ######  ',
        ' ######   ',
        '##        ',
        '##        ',
        '######### ',
        '######### ',
        '          '],
  '3': [' #######  ',
        '######### ',
        '##     ## ',
        '       ## ',
        ' #######  ',
        ' #######  ',
        '       ## ',
        '##     ## ',
        '######### ',
        ' #######  ',
        '          '],
  '4': ['##     ## ',
        '##     ## ',
        '##     ## ',
        '##     ## ',
        '######### ',
        '######### ',
        '       ## ',
        '       ## ',
        '       ## ',
        '       ## ',
        '          '],
  '5': ['########  ',
        '########  ',
        '##        ',
        '##        ',
        ' ######   ',
        '  ######  ',
        '       ## ',
        '       ## ',
        '########  ',
        '#######   ',
        '          '],
  '6': [' #######  ',
        '########  ',
        '##        ',
        '##        ',
        '#######   ',
        '########  ',
        '##     ## ',
        '##     ## ',
        ' #######  ',
        '  #####   ',
        '          '],
  '7': ['######### ',
        '######### ',
        '##     ## ',
        '       ## ',
        '      ##  ',
        '     ##   ',
        '    ##    ',
        '    ##    ',
        '    ##    ',
        '    ##    ',
        '          '],
  '8': [' #######  ',
        '######### ',
        '##     ## ',
        '##     ## ',
        ' #######  ',
        ' #######  ',
        '##     ## ',
        '##     ## ',
        '######### ',
        ' #######  ',
        '          '],
  '9': [' #######  ',
        '######### ',
        '##     ## ',
        '##     ## ',
        ' ######## ',
        '  ####### ',
        '       ## ',
        '       ## ',
        ' #######  ',
        ' ####     ',
        '          '],
  # Non-uniform sizes
  'i': ['  ',
        '## ',
        '## ',
        '   ',
        '## ',
        '## ',
        '## ',
        '## ',
        '## ',
        '## ',
        '   '],
  'n': ['        ',
        '        ',
        '        ',
        '        ',
        '        ',
        ' #####  ',
        '##   ## ',
        '##   ## ',
        '##   ## ',
        '##   ## ',
        '        '],
  'm': ['          ',
        '          ',
        '          ',
        '          ',
        '          ',
        ' ### ###  ',
        '##  #  ## ',
        '##  #  ## ',
        '##  #  ## ',
        '##  #  ## ',
        '          '],
  '-': ['     ',
        '     ',
        '     ',
        '     ',
        '     ',
        '#### ',
        '     ',
        '     ',
        '     ',
        '     ',
        '     '],
  ' ': ['     ',
        '     ',
        '     ',
        '     ',
        '     ',
        '     ',
        '     ',
        '     ',
        '     ',
        '     ',
        '     '],
  '.': ['   ',
        '   ',
        '   ',
        '   ',
        '   ',
        '   ',
        '   ',
        '   ',
        '## ',
        '## ',
        '   '],
  '?': [' #####  ',
        '####### ',
        '##   ## ',
        '     ## ',
        '    ##  ',
        '   ##   ',
        '   ##   ',
        '   ##   ',
        '        ',
        '   ##   ',
        '        '],
 }

# List of fonts
CHAR_SETS = (CHAR_SET1, CHAR_SET2, CHAR_SET3, CHAR_SET4)


class IndicatorDisplay:
  """Class to manage curses display screen for indicator numbers"""
  
  COLOR_POSITIVE = 0x2E  # Green
  COLOR_NEGATIVE = 0xC4  # Red
  
  COLOR_PAIR_GRN_ON_GRN = 1
  COLOR_PAIR_RED_ON_RED = 2
  COLOR_PAIR_GRN_ON_BLK = 3
  COLOR_PAIR_RED_ON_BLK = 4
  

  def __init__(self):
    self.stdscr = curses.initscr()
    self.stdscr.keypad(1)
    self.stdscr.timeout(0)  # Non-blocking
    curses.noecho()
    curses.start_color()
    # curses.use_default_colors() # Allows -1 to be used in color pairs
    curses.curs_set(0)
    curses.init_color(curses.COLOR_BLACK, 0, 0, 0)
    # curses.init_pair(pair_number, gf, bg)
    curses.init_pair(self.COLOR_PAIR_GRN_ON_GRN, self.COLOR_POSITIVE,
                     self.COLOR_POSITIVE)
    curses.init_pair(self.COLOR_PAIR_RED_ON_RED, self.COLOR_NEGATIVE,
                     self.COLOR_NEGATIVE)
    curses.init_pair(self.COLOR_PAIR_GRN_ON_BLK, self.COLOR_POSITIVE,
                     curses.COLOR_BLACK)
    curses.init_pair(self.COLOR_PAIR_RED_ON_BLK, self.COLOR_NEGATIVE,
                     curses.COLOR_BLACK)
    # Set initial colors
    self.pair_positive = self.COLOR_PAIR_GRN_ON_BLK
    self.pair_negative = self.COLOR_PAIR_RED_ON_BLK
    self.color_pair = self.pair_positive
    # Starting character set
    self.char_set = CHAR_SETS[0]
    # Starting style
    self.base_char = BASE_CHARACTERS[4]
    self.number = 0
    self.unit = 'mm'  # Or 'in'

  def __enter__(self):
    return self

  def __exit__(self, exc_type, exc_value, exc_traceback):
    # Return True on graceful exit
    curses.endwin()
    if not exc_type:
      return True

  def _foot_note(self):
    rows, cols = self.stdscr.getmaxyx()
    try:
      self.stdscr.addstr(rows-2, 0, '<ESC> or <EOT> to exit')
      self.stdscr.addstr(rows-1, 0, 'F1 - Change font, F2 - Change style')
      self.stdscr.clrtobot()  # Clear to the end of window
    except curses.error:
      pass # Can have error on resize
  
  def _display_char(self, ch):
    row, start_col = self.stdscr.getyx()
    start_row = row
    display = self.char_set.get(ch, self.char_set['?'])
    for line in display:
      try:
        self.stdscr.move(row, start_col)
        for d in line:
          if d != ' ':
            self.stdscr.addch(self.base_char, curses.color_pair(self.color_pair))
          else:
            self.stdscr.addch(d)
          self.stdscr.clrtoeol()
      except curses.error:
        pass  # Catch error on resize
      row += 1

    # Move cursor to starting row and new column
    _, end_col = self.stdscr.getyx()
    self.stdscr.move(start_row, end_col)
    return  
    
    self.stdscr.addch(ch)
  
  def update_page(self):
    # Convert number to string
    d = 2 if self.unit == 'mm' else 4
    n = self.number
    sign = '-' if n < 0 else ' '
    if sign == '-':
      self.color_pair = self.pair_negative
    else:
      self.color_pair = self.pair_positive
    num_str = f'{sign}{abs(n):0.{d}f} {self.unit}'
    # Display the string character by character
    self.stdscr.move(0, 0)
    for ch in num_str:
      self._display_char(ch)
    # Clear the space under the number displayed (in case resized)
    try:
      self.stdscr.move(len(self.char_set['0']), 0)
      self.stdscr.clrtobot()
    except curses.error:
      pass  # Ignore going out of bounds on resize
    self._foot_note()
    self.stdscr.refresh()

  def display_number(self, number: str):
    """Parse number, store in object and refresh the page"""
    m = INDICATOR_RE.match(number)
    if not m:
      self.number = '9.999'
      self.unit = 'xx'
    else:
      self.number = float(m.group('number'))
      self.unit = 'mm' if m.group('unit') == 'mm' else 'in'
    self.update_page()
  
  def handle_f1(self):
    """Change font"""
    i = CHAR_SETS.index(self.char_set)
    i = (i + 1) % len(CHAR_SETS)
    self.char_set = CHAR_SETS[i]
    self.update_page()

  def handle_f2(self):
    """Change font style"""
    i = BASE_CHARACTERS.index(self.base_char)
    i = (i + 1) % len(BASE_CHARACTERS)
    self.base_char = BASE_CHARACTERS[i]
    if self.base_char == ' ':
      self.pair_positive = self.COLOR_PAIR_GRN_ON_GRN
      self.pair_negative = self.COLOR_PAIR_RED_ON_RED
    else:
      self.pair_positive = self.COLOR_PAIR_GRN_ON_BLK
      self.pair_negative = self.COLOR_PAIR_RED_ON_BLK
    self.update_page()

  def get_input(self):
    """Get's called when select loop determines there is something to read"""
    try:
      wch = self.stdscr.get_wch()  # Non-Blocking
    except curses.error:
      return None
    if not wch:
      return None
    if isinstance(wch, str) and curses.ascii.isctrl(wch):
      if ord(wch) in (curses.ascii.ESC, curses.ascii.EOT):
        return True  # Should end
    if wch == curses.KEY_RESIZE:
      self.update_page()
    elif wch == curses.KEY_F1:
      self.handle_f1()
    elif wch == curses.KEY_F2:
      self.handle_f2()
    # All other input ignored
    return None

  
class IndicatorReader:
  def __init__(self, port, baudrate):
    self.port = port
    self.baudrate = baudrate

  def select_loop(self):
    try:
      recv_prefix = 'Loop: '
      # Open serial port in non-blocking mode
      with serial.Serial(self.port, self.baudrate, timeout=0) as monitor, \
           IndicatorDisplay() as id:
        print('Connected to: ', end='')
        print(monitor)
        # Set up select loop here

        indicator_fd = monitor.fileno()
        stdin_fd = sys.stdin.fileno()
        resize_fd = signalfd.signalfd(
          -1, [signal.SIGWINCH], signalfd.SFD_CLOEXEC | signalfd.SFD_NONBLOCK)

        inputs = [indicator_fd, stdin_fd, resize_fd]

        line = ''
        while True:
          rlist, wlist, xlist = select.select(inputs, [], [])
          if indicator_fd in rlist:
            chars = monitor.read_until()
            if chars:
              line += chars.decode('utf8')
            if line.endswith('\n'):
              #print(f"{recv_prefix}{line}", end='')
              id.display_number(line)
              line = ''
          else:
            if id.get_input():
              break
    except IOError as error:
      print('Problem opening monitor: ', error)
      sys.exit(-1)

      
class CombinedFormatter(argparse.RawTextHelpFormatter,
                        argparse.ArgumentDefaultsHelpFormatter):
  pass
    

def main():
  parser = argparse.ArgumentParser(
    description='''
DialIndicator Reader/Display:

  This program opens a serial port connection to an Arduino running
  a version of the DialIndicator program that decodes dial indicator
  or digital caliper data. This program then reads the data sent
  by the Arduino via serial port and displays it on the screen in
  the form of a curses window.

  When first run, the program will scan all serial ports:
    o If no ports are available, the program will indicate as such.
    o If only one is available, it is assumed to be one with the Arduino.
    o If more than one port is available, the list of ports will be displayed,
      the program will end and the user must re-run specifying the port
      using the port (-p or --port) flag.

  Once the program is run and a connection is made to the Arduino,
  Ctrl-D or <ESC> will exit the program, F1 will change the font, and
  F2 will change the font style. ''',
    formatter_class=CombinedFormatter)

  # List Ports
  parser.add_argument('-l', '--list_ports',
                      action='store_true',
                      help='List available ports and exit')

  # Port
  parser.add_argument('-p', '--port',
                      type=str,
                      help='Serial port to monitor')

  # baudrate
  parser.add_argument('-b', '--baudrate',
                      type=int, default=115200,
                      help='Baudrate of serial communication')

  args = parser.parse_args()

  if args.list_ports or not args.port:
    args.port = GetPort(args.list_ports)

  reader = IndicatorReader(args.port, args.baudrate)
  reader.select_loop()

  
if __name__ == '__main__':
  main()
