# OpenTargetGenerator
This program allows the user to generate and control multiple instances of virtual aircraft, within FlightGear Flight Simulator's multiplayer server system.

This software's intended purpose is to provide a tool that enables ATC enthusiasts to practice vectoring, sequencing or any other type of air traffic control technique within a controlled environment.

While previous implementations of the same concept have been created in the past, OpenTargetGenerator is unique in that it connects aircraft targets directly to multiplayer, allowing you to use any ATC client.

## IMPORTANT!
Do not use OpenTargetGenerator on official mpservers! These targets can waste a lot of bandwidth and resources, especially when the server is trying to serve other connections as well.

You can set up and use your own FGMS server, or alternatively, use the FGMEMBERS server which can be selected by default. However I reserve the right to ban your IP address from the FGMEMBERS server if you have connected an excessive amount of targets.

## Dependencies
* Python 3
* An ATC client to view the targets, preferably OpenRadar or ATC-pie

## Usage
All scenario files should be placed in OpenTargetGenerator/scenarios directory.

This program is completely headless. All input must be done through a terminal.
Once the program is started, it will prompt you for the scenario filename. Be sure to include the .xml extension. Then enter the server address and port.

When ">>" appears, enter the full callsign or part of the callsign of the aircraft you want to select. Then press return.
If the aircraft has been selected successfuly, an indented prompt will appear with the selected callsign followed by a colon. At this point, you can tell the aircraft what you want it to do.

Usually, Your input needs to include two parts: 1) the instruction; 2) the value of the instruction. For example, "h100" tells the aircraft to fly heading 100, where "h" is the instruction and "100" is the value.

The following instructions are possible and must be followed by a value:

    h        = heading
    m, d, c  = altitude
    s        = speed
    a, i     = cleared for approach
    >        = set new route
    b        = beacon code (squawk)

For some instructions, you have the option to use different letters.

Here are a few examples for each:

    h120        = Fly heading 120
    m60         = Maintain 6000 ft (note that the altitude is given in hundreds)
    d60         = Same as above
    i18r        = Cleared for approach to runway 18R
    >SUGOL SPY  = Proceed direct SUGOL and then direct SPY (you can add an unlimited number of waypoints)
    b3610       = Squawk 3610

The following instructions do not require a value:

    p  = pause the target
    u  = unpause the target
    >> = proceed direct the next waypoint in the route
    x  = delete the aircraft
    
When no aircraft is selected, you also have the option to use the following special commands:

    exit = deletes all aircraft and exits the program
    p    = pauses all aircraft
    u    = unpauses all aircraft
    
## Special Notes
* The turn rate is 2 degrees per second, which is quite close to the turn rate of an airliner at around >200 knots.
* The climb/descend rate is 1800 FPM
* The glidepath is configured for a 300 ft/NM descent, which equates to about a 3-degree glidepath.
* All aircraft will automatically reduce speed incrementally when cleared for approach and once within 5 miles of the runway touchdown zone.
