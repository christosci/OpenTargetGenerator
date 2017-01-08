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

    * Add a pre-specified amount of knots to the speed to account for
      differences between indicated airspeed and groundspeed.

    * Allow for ground-based scenarios, where aircraft can be instructed
      to taxi, takeoff and land from and to pre-specified locations.
"""

import sys
import xml.etree.ElementTree as ET
from fgmsHandler import FgmsHandler
from aircraft import Aircraft

# -------------------------------------------------------------------------------------------------------

version = "1.0"
default_address = "172.93.103.204"  # FGMEMBERS address
default_port = 16605  # FGMEMBERS port

# -------------------------------------------------------------------------------------------------------

print("OpenTargetGenerator v" + version + "\n")

# 1. Prompt user to enter scenario file
while True:
    try:
        filename = input("Enter scenario filename: ")
        scenario = ET.parse('scenarios/' + filename).getroot()
    except:
        print("File not found!")
    else:
        break

# -------------------------------------------------------------------------------------------------------

# 2. Promt user to enter server info
server_address = input("Enter server adddress (or press return to use default FGMEMBERS server): ")
if not server_address:
    server_address = default_address

server_port = input("Enter server port (or press return to use default FGMEMBERS port): ")
if not server_port:
    server_port = default_port
else:
    server_port = int(server_port)

# -------------------------------------------------------------------------------------------------------

# 3. Store the required attributes
magvar = scenario.get("magvar")
navaids = scenario.find("navaids").findall("wp")
runways = scenario.find("runways").findall("rwy")
aircraft = scenario.find("aircraft").findall("ac")
aircraft_list = []  # List to store aircraft objects

# -------------------------------------------------------------------------------------------------------

# 4. Loop through each aircraft
for ac in aircraft:
    aircraft_obj = Aircraft(ac, navaids, magvar)
    aircraft_list.append(aircraft_obj)
    aircraft_obj.handler = FgmsHandler(server_address, server_port, aircraft_obj)

# -------------------------------------------------------------------------------------------------------

# 5. Infinite loop of prompts, until "exit" is entered
while True:
    transmission = input(">> ").upper().lstrip().rstrip()

    # a. Check for inputs independent of aircraft
    if transmission == "EXIT":
        for ac in aircraft_list:
            ac.delete_aircraft()
        sys.exit()
    elif transmission == "P":
        for ac in aircraft_list:
            ac.paused = True
        continue
    elif transmission == "U":
        for ac in aircraft_list:
            ac.paused = False
        continue

    aircraft_found = False

    # b. Check if entered callsign matches any aircraft in aircraft_list
    for ac in aircraft_list:
        if ac.callsign.find(transmission) != -1:
            if aircraft_found:
                aircraft_found = False
                break
            else:
                selected_aircraft = ac
                aircraft_found = True

    # c. Prompt the user for an instruction and modify the appropriate variables.
    if aircraft_found:
        transmission = input("\t" + selected_aircraft.callsign + ": ").lower().lstrip()

        if transmission == "p":
            selected_aircraft.paused = True
        elif transmission == "u":
            selected_aircraft.paused = False

        try:
            # Break down the transmission into two parts
            instruction = transmission[0]
            value = transmission[1:]

            # Heading
            if instruction == "h":
                selected_aircraft.set_target_heading(int(value))
            # Altitude
            elif instruction == "m" or instruction == "d" or instruction == "c":
                selected_aircraft.set_target_alt(int(value) * 100)
            # Speed
            elif instruction == "s":
                selected_aircraft.target_spd = int(value)
            # Approach
            elif instruction == "a" or instruction == "i":
                for rwy in runways:
                    if rwy.get("id") == value.upper():
                        selected_aircraft.set_target_rwy(rwy)
                        break
            # Direct next waypoint
            elif instruction == ">" and value == ">":
                selected_aircraft.target_wpt_index += 1
                selected_aircraft.set_target_wpt()
                print("Proceeding direct to " +
                      selected_aircraft.route[selected_aircraft.target_wpt_index])
            # New route
            elif instruction == ">":
                selected_aircraft.set_route(value.upper())
            # Beacon code (squawk)
            elif instruction == "b":
                selected_aircraft.sq = int(value)
            # Delete aircraft
            elif instruction == "x":
                selected_aircraft.delete_aircraft()
        except:
            print("Invalid instruction!")
    else:
        print("Not found")
