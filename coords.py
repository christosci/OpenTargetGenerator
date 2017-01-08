# This file is part of the ATC-pie project, modified for use
# in the OpenTargetGenerator project.

# Original work: Copyright (C) 2015  Michael Filhol <mickybadia@gmail.com>
# Modified work: Copyright (C) 2016  Christos K. <christoskok@gmail.com>

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

import re
from math import radians, degrees, cos, sin, acos, asin, atan2, sqrt

# ---------- Constants ----------

m2NM = 1 / 1852  # 1 NM is defined as 1852 m
m2SM = 1 / 1609.344  # statute mile
m2ft = 3.2808399

Earth_radius_km = 6378.1
Earth_radius_NM = m2NM * 1000 * Earth_radius_km

# -------------------------------


def moved(lat, lon, radial, distance):
    """Get the final position of a crow's flight starting with a given heading."""
    lat1 = radians(lat)
    lon1 = radians(lon)
    a = radians(radial)
    d = distance / Earth_radius_NM
    lat2 = asin(sin(lat1) * cos(d) + cos(lat1) * sin(d) * cos(a))
    lon2 = lon1 + atan2(sin(a) * sin(d) * cos(lat1), cos(d) - sin(lat1) * sin(lat2))
    lat_res = (degrees(lat2) + 90) % 180 - 90
    lon_res = (degrees(lon2) + 180) % 360 - 180
    return lat_res, lon_res


def heading_to(lat1, lon1, lat2, lon2):
    """Get the heading between two coordinates.

    Follows the shortest path (on great circle, i.e. as the crow flies)
    """
    lat1 = radians(lat1)
    lat2 = radians(lat2)
    dlon = radians(lon2 - lon1)
    theta = atan2(sin(dlon) * cos(lat2), cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlon))
    return degrees(theta) % 360


def distance_to(lat1, lon1, lat2, lon2):
    """Get the distance betweeen two coordinates."""
    lat1 = radians(lat1)
    lat2 = radians(lat2)
    dlon = radians(lon2 - lon1)
    try:
        return acos(sin(lat1) * sin(lat2) + cos(lat1) * cos(lat2) * cos(dlon)) * Earth_radius_NM
    except ValueError:  # Caught as every time was only acos of value just over 1, probably from non-critical approximations
        return 0  # acos(1)


# ======= WGS84 geodesy =======

# translated from simgear C++ sources

WGS84_equrad = 6378137
WGS84_squash = .9966471893352525192801545

ra2 = 1 / (WGS84_equrad * WGS84_equrad)
e2 = abs(1 - WGS84_squash * WGS84_squash)
e4 = e2 * e2


def WGS84_geodetic_to_cartesian_metres(lon, lat, ftAMSL):
    """Earth centred cartesian coordinates from geodetic coordinates on the WGS84 ellipsoid.

    Translated from Simgear sources: simgear/math/SGGeodesy.cxx
    """
    l = radians(lon)
    phi = radians(lat)
    h = ftAMSL / m2ft
    sphi = sin(phi)
    n = WGS84_equrad / sqrt(1 - e2 * sphi * sphi)
    cphi = cos(phi)
    slambda = sin(l)
    clambda = cos(l)
    x = (h + n) * cphi * clambda
    y = (h + n) * cphi * slambda
    z = (h + n - e2 * n) * sphi
    return x, y, z
