#!/usr/bin/env python3

# This file is part of the OpenTargetGenerator project,
# a target generator program for FlightGear.

# Copyright (C) 2017 Christos K. <christoskok@gmail.com>

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301  USA

"""OpenTargetGenerator.py.
This program allows a user to generate and control multiple instances of
virtual aircraft, within FlightGear Flight Simulator's multiplayer server
system.
For usage instructions, refer to README.md
Long term TODO:
    * Add the option to issue instructions directly through multiplayer
      chat instead of the terminal. This will allow the user to select
      aircraft by clicking on OpenRadar's datablocks, without having to type
      the callsign.
    * Pack more FGFS properties in each mp message so that the aircraft
      models will be made visible on multiplayer.
    * Use floats instead of ints for headings and related calculations for
      more accuracy.
    * Allow for custon climb/descent rates for each aircraft.
    * Allow for ground-based scenarios, where aircraft can be instructed
      to taxi, takeoff and land from and to pre-specified locations.
"""

import sys
import os
import xml.etree.ElementTree as ET
from fgmsHandler import FgmsHandler
from aircraft import Aircraft
import constants as c


class OpenTargetGenerator:
    def __init__(self):
        print('OpenTargetGenerator v' + c.version + '\n')
        self.aircraft_list = []
        self.prompts()
        self.super_commands()


    def prompts(self):
        while True:
            try:
                c.filename = input('Enter scenario filename: ')
                self.get_data()
            except Exception as e:
                print('Unexpected error parsing scenario file: %s' % (e))
            else:
                break

        c.server_address = input('Enter server adddress (or press return to use default FGMEMBERS server): ')
        if not c.server_address:
            c.server_address = c.default_address

        c.server_port = input('Enter server port (or press return to use default FGMEMBERS port): ')
        if not c.server_port:
            c.server_port = c.default_port
        else:
            c.server_port = int(c.server_port)

        self.initialize_aircraft()


    def get_data(self):
        c.scenario = ET.parse(os.path.join(c.scenario_path, c.filename)).getroot()
        c.data['magvar'] = round(float(c.scenario.get('magvar')))
        c.data['navaids'] = c.scenario.find('navaids').findall('wp')
        c.data['runways'] = c.scenario.find('runways').findall('rwy')
        c.data['aircraft'] = c.scenario.find('aircraft').findall('ac')


    def initialize_aircraft(self):
        for ac_data in c.data['aircraft']:
            aircraft_obj = Aircraft(ac_data)
            self.aircraft_list.append(aircraft_obj)
            aircraft_obj.handler = FgmsHandler(aircraft_obj)


    def delete_all_aircraft(self):
        for ac in self.aircraft_list:
            ac.disconnect_aircraft()
            del ac
        self.aircraft_list.clear()


    def super_commands(self):
        while True:
            # prompt for callsign or global command
            super_command = input('>> ').upper().strip() 

            if self.check_global_commands(super_command): continue

            aircraft_found = False
        
            for ac in self.aircraft_list:
                if ac.callsign.find(super_command) != -1:
                    # Ensure only a single callsign match has been found
                    if aircraft_found:
                        aircraft_found = False
                        break
                    else:
                        selected_aircraft = ac
                        aircraft_found = True

            if aircraft_found: self.aircraft_commands(selected_aircraft)
            else: print('Aircraft not found')


    def aircraft_commands(self, selected_aircraft):
        command = input('\t' + selected_aircraft.callsign + ': ').lower().lstrip()

        if command == 'p': selected_aircraft.paused = True
        elif command == 'u': selected_aircraft.paused = False

        try:
            # Break down the command into two parts
            instruction = command[0]
            value = command[1:]

            # Heading
            if instruction == 'h':
                selected_aircraft.set_target_heading(int(value))
            # Altitude
            elif instruction == 'm' or instruction == 'd' or instruction == 'c':
                selected_aircraft.set_target_alt(int(value) * 100)
            # Speed
            elif instruction == 's':
                selected_aircraft.target_spd = int(value) + c.iasvar
            # Approach
            elif instruction == 'a' or instruction == 'i':
                for rwy in c.data['runways']:
                    if rwy.get('id') == value.upper():
                        selected_aircraft.set_target_rwy(rwy)
                        break
            # Direct next waypoint
            elif instruction == '>' and value == '>':
                selected_aircraft.target_wpt_index += 1
                selected_aircraft.set_target_wpt()
                print('Proceeding direct to ' +
                      selected_aircraft.route[selected_aircraft.target_wpt_index])
            # New route
            elif instruction == '>':
                selected_aircraft.set_route(value.upper())
            # Beacon code (squawk)
            elif instruction == 'b':
                selected_aircraft.sq = int(value)
            # Disconnect aircraft
            elif instruction == 'x':
                selected_aircraft.disconnect_aircraft()
        except:
            print('Invalid instruction!')


    def check_global_commands(self, command):
        """Check for commands that affect all aircraft objects globally.

        Returns:
            bool -- [Return true if super_commands() loop must continue]
        """
        if command == 'EXIT':
            for ac in self.aircraft_list:
                self.delete_all_aircraft()
            sys.exit()
        elif command == 'P':
            for ac in self.aircraft_list:
                ac.paused = True
            return True
        elif command == 'U':
            for ac in self.aircraft_list:
                ac.paused = False
            return True
        elif command == 'RELOAD':
            self.delete_all_aircraft()
            self.get_data()
            self.initialize_aircraft()
            print('Scenario has been reloaded')
            return True


if __name__== '__main__':
    OpenTargetGenerator()