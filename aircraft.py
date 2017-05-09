"""
aircraft.py.

This module calculates and sends positional data for each aircraft to fgms.py for
mp data packing every 0.5 seconds.
"""

from coords import moved, heading_to, distance_to
import constants as c


# ---------- Constants ----------

update_interval = 0.5  # seconds
updates_per_min = 60 / update_interval
updates_per_hr = 3600 / update_interval

# climb/descent rate per update interval
climb_descent_rate = int(1800 / updates_per_min)

# shallow intercept to be used for small corrections when intercepting the final approach course.
shallow_intercept_angle = 5  # degrees

# used to turn the aircraft to the next waypoint and to delete the aircraft when within close proximity to the rwy.
magic_distance = 0.4  # NM

# distance from the rwy at which the aircraft can begin reducing to approach speed.
free_speed_distance = 5  # NM

# knots per NM that the aircraft will decrease speed by to ensure a difference of 40 knots over the rwy.
# in other words, the speed will be 40 knots less over the rwy than at free_speed_distance.
free_speed_increment = 40 / free_speed_distance

# -------------------------------


class Aircraft:
    def __init__(self, ac):
        self.handler = None  # Stores the aircraft's handler object
        # Status variables
        self.paused = True
        self.callsign = ac.get('callsign')
        self.sq = int(ac.get('sq'))
        self.lat = float(ac.get('lat'))
        self.lon = float(ac.get('lon'))
        self.alt = int(ac.get('alt'))
        self.spd = int(ac.get('spd'))
        self.ac_type = ac.get('type')
        self.route = ac.get('route').split()  # list of waypoints

        # Target variables
        self.target_alt = self.alt
        self.target_spd = self.spd + c.iasvar
        self.status = 'route'  # route, approach, heading
        self.on_profile = True
        self.initial_appr_spd = 180  # default value
        self.target_wpt_index = 0  # index of target waypoint in self.route

        # Dependent variables
        # Assigned last because of dependency to pre-existing variables
        self.set_target_wpt()  # Get coordinates of first waypoint...
        self.heading = self.bearing_to_target_wpt()  # ...so we can get a bearing
        self.target_heading = self.heading

    # ----------------

    #    ACCESSORS

    # ----------------

    def get_pos(self):
        """Update position if needed and return it."""
        self.control_aircraft()
        return self.lon, self.lat, self.alt

    def get_vel_x(self):
        """Approximation for mp protocol's VelX value based on speed.

        Doing this so OpenRadar will display a vector/predicted track line.
        """
        return self.spd / 6

    # ----------------

    #    SETTERS

    # ----------------

    def set_route(self, route):
        """Set a new route."""
        self.status = 'route'
        self.target_wpt_index = 0
        self.route = route.split()
        self.set_target_wpt()

    def set_target_heading(self, target_heading):
        """Set the target heading plus magnetic variation."""
        self.status = 'heading'
        self.target_heading = (target_heading - c.data['magvar']) % 360

    def set_target_alt(self, target_alt):
        """Set the target altitude."""
        self.on_profile = False
        self.target_alt = target_alt

    def set_target_rwy(self, rwy):
        """Set the target runway."""
        self.status = 'approach'
        self.target_rwy_lat = float(rwy.get('lat'))
        self.target_rwy_lon = float(rwy.get('lon'))
        self.target_rwy_crs = int(rwy.get('crs')) - c.data['magvar']
        self.target_rwy_elev = int(rwy.get('elev'))

    def set_target_wpt(self):
        """Obtain coordinates of target waypoint."""
        try:
            for wp in c.data['navaids']:
                if wp.get('name') == self.route[self.target_wpt_index]:
                    self.target_wpt_lat = float(wp.get('lat'))
                    self.target_wpt_lon = float(wp.get('lon'))
                    self.target_wpt_alt = int(wp.get('alt', 0))
                    break
        except:
            self.set_target_heading(self.heading + c.data['magvar'])

    def disconnect_aircraft(self):
        """Disconnect the aircraft."""
        self.handler.stop()
        del self.handler

    # ----------------

    #    ALGORITHMS

    # ----------------

    def control_aircraft(self):
        """Check status and call the appropriate method."""
        if not self.paused:
            if self.status == 'route':
                self.fly_route()
            elif self.status == 'heading':
                self.adjust_heading()
            elif self.status == 'approach':
                self.check_ils_feather()
            self.adjust_alt()
            self.adjust_speed()
            self.move_position()

    def check_heading(self):
        """Ensure that the heading does not become negative or greater than 360."""
        self.heading %= 360

    # ---------------------------------------------------------------------------------------------------------

    def turn_one_degree(self, target_hdg):
        """Turn aircraft by one degree towards the shortest direction needed to reach target heading."""
        if self.heading != target_hdg:
            turn_right = (self.heading - target_hdg + 360) % 360 > 180  # True = right turn; False = left turn
            self.heading = self.heading + 1 if turn_right else self.heading - 1
        self.check_heading()

    # ---------------------------------------------------------------------------------------------------------

    def move_position(self):
        """Move position based on distance per update interval."""
        distance = self.spd / updates_per_hr
        self.lat, self.lon = moved(self.lat, self.lon, self.heading, distance)

    # ---------------------------------------------------------------------------------------------------------

    def adjust_heading(self):
        """Adjust the current heading."""
        if self.heading != self.target_heading:
            self.turn_one_degree(self.target_heading)

    # ---------------------------------------------------------------------------------------------------------

    def adjust_alt(self):
        """Adjust the current altitude by climb_descent_rate."""
        if self.alt != self.target_alt:
            if abs(self.alt - self.target_alt) >= climb_descent_rate:
                self.alt = self.alt - climb_descent_rate if self.alt > self.target_alt else self.alt + climb_descent_rate
            else:
                self.alt = self.target_alt

    # ---------------------------------------------------------------------------------------------------------

    def adjust_speed(self):
        """Adjust the current speed by one knot."""
        if self.spd != self.target_spd:
            self.spd = self.spd - 1 if self.spd > self.target_spd else self.spd + 1

    # ---------------------------------------------------------------------------------------------------------

    def check_ils_feather(self):
        """Check if the aircraft needs to turn for the approach.

        Begin turning if the aircraft is within a 2-degree "feather" within 12 NM from the rwy TDZ, or
        within 1-degree "feather" outside of 12 NM.
        """
        # Get current bearing to runway TDZ
        current_bearing = round(heading_to(self.lat, self.lon, self.target_rwy_lat, self.target_rwy_lon))
        dme = distance_to(self.lat, self.lon, self.target_rwy_lat, self.target_rwy_lon)

        if abs(current_bearing - self.target_rwy_crs) <= 2 and dme < 12:
            self.turn_to_centerline(current_bearing)
        elif abs(current_bearing - self.target_rwy_crs) <= 1 and dme >= 12:
            self.turn_to_centerline(current_bearing)
        else:
            self.turn_one_degree(self.target_heading)

        self.descend_to_rwy()

    # ---------------------------------------------------------------------------------------------------------

    def turn_to_centerline(self, brg):
        """Turn the aircraft to the centerline for approach."""
        if brg == self.target_rwy_crs:
            self.turn_one_degree(brg)
        elif brg > self.target_rwy_crs:
            self.turn_one_degree(brg + shallow_intercept_angle)
        elif brg < self.target_rwy_crs:
            self.turn_one_degree(brg - shallow_intercept_angle)

    # ---------------------------------------------------------------------------------------------------------

    def descend_to_rwy(self):
        """Descend the aircraft to the runway, following a 3-deg glidepath angle."""
        dme = distance_to(self.lat, self.lon, self.target_rwy_lat, self.target_rwy_lon)  # distance to rwy
        glidepath_alt = int(300 * dme + self.target_rwy_elev)  # 300 ft / NM =~ 3 deg glidepath

        # Check if calculated glidepath is below current alt.
        if self.alt > glidepath_alt:
            self.alt = glidepath_alt
            self.target_alt = glidepath_alt

        # Get initial approach spd
        if round(dme) == free_speed_distance + 1:
            self.initial_appr_spd = self.spd

        # Calculate number of knots, based on dme.
        # Then subtract it from the initial approach spd.
        if dme < free_speed_distance and dme > magic_distance:
            self.spd = self.initial_appr_spd - (-dme + free_speed_distance) * free_speed_increment
        # Delete aircraft once within magic_distance from the TDZ.
        elif dme <= magic_distance:
            self.delete_aircraft()

    # ---------------------------------------------------------------------------------------------------------

    def fly_route(self):
        """Guide aircraft along the route."""
        dme = distance_to(self.lat, self.lon, self.target_wpt_lat, self.target_wpt_lon)
        current_bearing = self.bearing_to_target_wpt()

        # Check if target waypoint has a pre-specified crossing altitude
        if self.target_wpt_alt != 0:
            tod = abs(self.alt - self.target_wpt_alt) / 1000 * 3  # top of descent
            if dme <= tod and self.on_profile:
                self.target_alt = self.target_wpt_alt

        # Turn towards the waypoint
        if dme > magic_distance:
            if abs(self.heading - current_bearing) >= 1:
                self.turn_one_degree(current_bearing)
        else:
            self.target_wpt_index += 1  # next waypoint
            self.set_target_wpt()

    # ---------------------------------------------------------------------------------------------------------

    def bearing_to_target_wpt(self):
        """Calculate bearing from present position to target waypoint."""
        bearing = heading_to(self.lat, self.lon, self.target_wpt_lat, self.target_wpt_lon)
        return round(bearing)
