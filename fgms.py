# This file is part of the ATC-pie project, modified for use
# in the OpenTargetGenerator project.

# Original work: Copyright (C) 2015  Michael Filhol <mickybadia@gmail.com>
# Modified work: Copyright (C) 2017  Christos K. <christoskok@gmail.com>

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

import threading
from time import sleep
from datetime import datetime, timezone
from struct import pack, unpack
from math import radians, pi, cos, sin, acos

from coords import WGS84_geodetic_to_cartesian_metres


# ---------- Constants ----------

encoding = 'utf-8'
maximum_packet_size = 2048
dodgy_character_substitute = '_'

timestamp_ignore_maxdiff = 10  # s (as specified in FGMS packets)
FGMS_handshake_interval = 0.5  # seconds

# -------------------------------


class PacketData:
    """
    Data packer/unpacker for FGFS stuff.

    Includes funny FGFS behaviour like little endian ints and big endian doubles,
    "buggy strings" (encoded with int sequences), etc.
    """

    def __init__(self, data=None):
        self.data = self.some(data, bytes(0))

    def some(self, value, fallback):
        if value is not None:
            return value
        return fallback

    def allData(self):
        return self.data
    def __len__(self):
        return len(self.data)

    def pad(self, block_multiple):
        pad = block_multiple - (len(self) % block_multiple)
        self.append_bytes(bytes(pad % block_multiple))

    def pack_bool(self, b):
        self.pack_int(int(b))
    def pack_int(self, i):
        self.data += pack('!i', i)
    def pack_float(self, f):
        self.data += pack('!f', f)
    def pack_double(self, d):
        self.data += pack('!d', d)
    def pack_string(self, size, string):  # For padded null-terminated string
        self.data += pack('%ds' % size, bytes(string, encoding)[:size-1])
    def append_bytes(self, raw_data):
        self.data += raw_data
    def append_packed(self, data):
        self.data += data.allData()
    def append_hexbytes(self, data):  # Data is a string of hex-represented bytes
        self.data += bytes.fromhex(data)
    def pack_FGFS_buggy_string(self, string):
        strbuf = PacketData()
        for c in string:
            strbuf.pack_int(ord(c))
        strbuf.pad(16)
        self.pack_int(len(string))
        self.append_packed(strbuf)

    def unpack_bytes(self, nbytes):
        popped = self.data[:nbytes]
        self.data = self.data[nbytes:]
        if len(popped) < nbytes:
            print('WARNING: Truncated packet detected. Expected %d bytes; only %d could be read.' % (nbytes, len(popped)))
            return bytes(nbytes)
        return popped
    def unpack_int(self):
        return unpack('!i', self.unpack_bytes(4))[0]
    def unpack_float(self):
        return unpack('!f', self.unpack_bytes(4))[0]
    def unpack_double(self):
        return unpack('!d', self.unpack_bytes(8))[0]
    def unpack_string(self, size):
        return self.unpack_bytes(size).split(b'\x00', 1)[0].decode()
    def unpack_bool(self):
        return self.unpack_int()
    def unpack_FGFS_buggy_string(self):
        nchars = self.unpack_int()
        intbytes = PacketData(self.unpack_bytes((((4 * nchars - 1) // 16) + 1) * 16))
        chrlst = []
        for i in range(nchars):
            try: chrlst.append(chr(intbytes.unpack_int()))
            except ValueError: chrlst.append(dodgy_character_substitute)
        return ''.join(chrlst)

# ----------------

#    ENCODING

# ----------------


def make_position_message(callsign, data):
    packet = PacketData()

    # Header first (32 bytes)
    packet.append_bytes(b'FGFS')  # Magic
    packet.append_hexbytes('00 01 00 01')  # Protocol version 1.1
    packet.append_hexbytes('00 00 00 07')  # Type: position message
    packet.pack_int(32 + len(data))  # Length of data
    packet.append_hexbytes('00 00 00 00')  # Ignored
    packet.append_hexbytes('00 00 00 00')  # Ignored
    packet.pack_string(8, callsign)  # Callsign
    # Append the data
    packet.append_packed(data)
    return packet


def position_data(aircraft_model, lon, lat, pos_amsl, hdg, velx, pitch=0, roll=0):
    """pos_coords: EarthCoords.

    pos_amsl should be geometric alt in feet.
    """
    buf = PacketData()
    buf.pack_string(96, aircraft_model)  # Aircraft model
    buf.pack_double(read_stopwatch())  # Time
    buf.pack_double(0)  # Lag
    posX, posY, posZ = WGS84_geodetic_to_cartesian_metres(lon, lat, pos_amsl)
    buf.pack_double(posX)  # PosX
    buf.pack_double(posY)  # PosY
    buf.pack_double(posZ)  # PosZ
    oriX, oriY, oriZ = FG_orientation_XYZ(lon, lat, hdg, pitch, roll)
    buf.pack_float(oriX)  # OriX
    buf.pack_float(oriY)  # OriY
    buf.pack_float(oriZ)  # OriZ
    buf.pack_float(velx)  # VelX
    buf.pack_float(0)  # VelY
    buf.pack_float(0)  # VelZ
    buf.pack_float(0)  # AV1
    buf.pack_float(0)  # AV2
    buf.pack_float(0)  # AV3
    buf.pack_float(0)  # LA1
    buf.pack_float(0)  # LA2
    buf.pack_float(0)  # LA3
    buf.pack_float(0)  # AA1
    buf.pack_float(0)  # AA2
    buf.pack_float(0)  # AA3
    buf.append_hexbytes('00 00 00 00')  # 4-byte padding
    return buf


class FGMShandshaker(threading.Thread): 
    def __init__(self, socket, srv_address, aircraft):
        threading.Thread.__init__(self)
        self.socket = socket
        self.server_address = srv_address
        self.aircraft = aircraft
        self.current_chat_msg = ''
        self.handshaker_run = True

    def currentChatMessage(self):
        return self.current_chat_msg

    def setChatMessage(self, msg):
        self.current_chat_msg = msg

    def run(self):
        while self.handshaker_run:
            lon, lat, alt = self.aircraft.get_pos()
            data = position_data(self.aircraft.ac_type, lon, lat, alt, self.aircraft.heading, self.aircraft.get_vel_x())
            data.pack_int(FGMS_prop_XPDR_code)
            data.pack_int(self.aircraft.sq)
            data.pack_int(FGMS_prop_XPDR_alt)
            data.pack_int(alt)
            packet = make_position_message(self.aircraft.callsign, data)
            # print('Sending packet with size %d=0x%x bytes. Optional data is: %s' % (len(packet), len(packet), packet.data[228:])) # DEBUG
            try:
                self.socket.sendto(packet.allData(), self.server_address)
            except OSError as error:
                print('Could not send FGMS packet to server. System says: %s' % error)
            sleep(FGMS_handshake_interval)

    def set_status(self, status):
        self.handshaker_run = status

FGMS_properties = {
  100: ('surface-positions/left-aileron-pos-norm',  PacketData.unpack_float),
  101: ('surface-positions/right-aileron-pos-norm', PacketData.unpack_float),
  102: ('surface-positions/elevator-pos-norm',      PacketData.unpack_float),
  103: ('surface-positions/rudder-pos-norm',        PacketData.unpack_float),
  104: ('surface-positions/flap-pos-norm',          PacketData.unpack_float),
  105: ('surface-positions/speedbrake-pos-norm',    PacketData.unpack_float),
  106: ('gear/tailhook/position-norm',              PacketData.unpack_float),
  107: ('gear/launchbar/position-norm',             PacketData.unpack_float),
  108: ('gear/launchbar/state',                     PacketData.unpack_FGFS_buggy_string),
  109: ('gear/launchbar/holdback-position-norm',    PacketData.unpack_float),
  110: ('canopy/position-norm',                     PacketData.unpack_float),
  111: ('surface-positions/wing-pos-norm',          PacketData.unpack_float),
  112: ('surface-positions/wing-fold-pos-norm',     PacketData.unpack_float),

  200: ('gear/gear[0]/compression-norm',           PacketData.unpack_float),
  201: ('gear/gear[0]/position-norm',              PacketData.unpack_float),
  210: ('gear/gear[1]/compression-norm',           PacketData.unpack_float),
  211: ('gear/gear[1]/position-norm',              PacketData.unpack_float),
  220: ('gear/gear[2]/compression-norm',           PacketData.unpack_float),
  221: ('gear/gear[2]/position-norm',              PacketData.unpack_float),
  230: ('gear/gear[3]/compression-norm',           PacketData.unpack_float),
  231: ('gear/gear[3]/position-norm',              PacketData.unpack_float),
  240: ('gear/gear[4]/compression-norm',           PacketData.unpack_float),
  241: ('gear/gear[4]/position-norm',              PacketData.unpack_float),

  300: ('engines/engine[0]/n1',  PacketData.unpack_float),
  301: ('engines/engine[0]/n2',  PacketData.unpack_float),
  302: ('engines/engine[0]/rpm', PacketData.unpack_float),
  310: ('engines/engine[1]/n1',  PacketData.unpack_float),
  311: ('engines/engine[1]/n2',  PacketData.unpack_float),
  312: ('engines/engine[1]/rpm', PacketData.unpack_float),
  320: ('engines/engine[2]/n1',  PacketData.unpack_float),
  321: ('engines/engine[2]/n2',  PacketData.unpack_float),
  322: ('engines/engine[2]/rpm', PacketData.unpack_float),
  330: ('engines/engine[3]/n1',  PacketData.unpack_float),
  331: ('engines/engine[3]/n2',  PacketData.unpack_float),
  332: ('engines/engine[3]/rpm', PacketData.unpack_float),
  340: ('engines/engine[4]/n1',  PacketData.unpack_float),
  341: ('engines/engine[4]/n2',  PacketData.unpack_float),
  342: ('engines/engine[4]/rpm', PacketData.unpack_float),
  350: ('engines/engine[5]/n1',  PacketData.unpack_float),
  351: ('engines/engine[5]/n2',  PacketData.unpack_float),
  352: ('engines/engine[5]/rpm', PacketData.unpack_float),
  360: ('engines/engine[6]/n1',  PacketData.unpack_float),
  361: ('engines/engine[6]/n2',  PacketData.unpack_float),
  362: ('engines/engine[6]/rpm', PacketData.unpack_float),
  370: ('engines/engine[7]/n1',  PacketData.unpack_float),
  371: ('engines/engine[7]/n2',  PacketData.unpack_float),
  372: ('engines/engine[7]/rpm', PacketData.unpack_float),
  380: ('engines/engine[8]/n1',  PacketData.unpack_float),
  381: ('engines/engine[8]/n2',  PacketData.unpack_float),
  382: ('engines/engine[8]/rpm', PacketData.unpack_float),
  390: ('engines/engine[9]/n1',  PacketData.unpack_float),
  391: ('engines/engine[9]/n2',  PacketData.unpack_float),
  392: ('engines/engine[9]/rpm', PacketData.unpack_float),

  800: ('rotors/main/rpm', PacketData.unpack_float),
  801: ('rotors/tail/rpm', PacketData.unpack_float),
  810: ('rotors/main/blade[0]/position-deg',  PacketData.unpack_float),
  811: ('rotors/main/blade[1]/position-deg',  PacketData.unpack_float),
  812: ('rotors/main/blade[2]/position-deg',  PacketData.unpack_float),
  813: ('rotors/main/blade[3]/position-deg',  PacketData.unpack_float),
  820: ('rotors/main/blade[0]/flap-deg',  PacketData.unpack_float),
  821: ('rotors/main/blade[1]/flap-deg',  PacketData.unpack_float),
  822: ('rotors/main/blade[2]/flap-deg',  PacketData.unpack_float),
  823: ('rotors/main/blade[3]/flap-deg',  PacketData.unpack_float),
  830: ('rotors/tail/blade[0]/position-deg',  PacketData.unpack_float),
  831: ('rotors/tail/blade[1]/position-deg',  PacketData.unpack_float),

  900: ('sim/hitches/aerotow/tow/length',                       PacketData.unpack_float),
  901: ('sim/hitches/aerotow/tow/elastic-constant',             PacketData.unpack_float),
  902: ('sim/hitches/aerotow/tow/weight-per-m-kg-m',            PacketData.unpack_float),
  903: ('sim/hitches/aerotow/tow/dist',                         PacketData.unpack_float),
  904: ('sim/hitches/aerotow/tow/connected-to-property-node',   PacketData.unpack_bool),
  905: ('sim/hitches/aerotow/tow/connected-to-ai-or-mp-callsign',   PacketData.unpack_FGFS_buggy_string),
  906: ('sim/hitches/aerotow/tow/brake-force',                  PacketData.unpack_float),
  907: ('sim/hitches/aerotow/tow/end-force-x',                  PacketData.unpack_float),
  908: ('sim/hitches/aerotow/tow/end-force-y',                  PacketData.unpack_float),
  909: ('sim/hitches/aerotow/tow/end-force-z',                  PacketData.unpack_float),
  930: ('sim/hitches/aerotow/is-slave',                         PacketData.unpack_bool),
  931: ('sim/hitches/aerotow/speed-in-tow-direction',           PacketData.unpack_float),
  932: ('sim/hitches/aerotow/open',                             PacketData.unpack_bool),
  933: ('sim/hitches/aerotow/local-pos-x',                      PacketData.unpack_float),
  934: ('sim/hitches/aerotow/local-pos-y',                      PacketData.unpack_float),
  935: ('sim/hitches/aerotow/local-pos-z',                      PacketData.unpack_float),

  1001: ('controls/flight/slats',  PacketData.unpack_float),
  1002: ('controls/flight/speedbrake',  PacketData.unpack_float),
  1003: ('controls/flight/spoilers',  PacketData.unpack_float),
  1004: ('controls/gear/gear-down',  PacketData.unpack_float),
  1005: ('controls/lighting/nav-lights',  PacketData.unpack_float),
  1006: ('controls/armament/station[0]/jettison-all',  PacketData.unpack_bool),

  1100: ('sim/model/variant', PacketData.unpack_int),
  1101: ('sim/model/livery/file', PacketData.unpack_FGFS_buggy_string),

  1200: ('environment/wildfire/data', PacketData.unpack_FGFS_buggy_string),
  1201: ('environment/contrail', PacketData.unpack_int),

  1300: ('tanker', PacketData.unpack_int),

  1400: ('scenery/events', PacketData.unpack_FGFS_buggy_string),

  1500: ('instrumentation/transponder/transmitted-id', PacketData.unpack_int),
  1501: ('instrumentation/transponder/altitude', PacketData.unpack_int),
  1502: ('instrumentation/transponder/ident', PacketData.unpack_bool),
  1503: ('instrumentation/transponder/inputs/mode', PacketData.unpack_int),

  10001: ('sim/multiplay/transmission-freq-hz',  PacketData.unpack_FGFS_buggy_string),
  10002: ('sim/multiplay/chat',  PacketData.unpack_FGFS_buggy_string),

  10100: ('sim/multiplay/generic/string[0]', PacketData.unpack_FGFS_buggy_string),
  10101: ('sim/multiplay/generic/string[1]', PacketData.unpack_FGFS_buggy_string),
  10102: ('sim/multiplay/generic/string[2]', PacketData.unpack_FGFS_buggy_string),
  10103: ('sim/multiplay/generic/string[3]', PacketData.unpack_FGFS_buggy_string),
  10104: ('sim/multiplay/generic/string[4]', PacketData.unpack_FGFS_buggy_string),
  10105: ('sim/multiplay/generic/string[5]', PacketData.unpack_FGFS_buggy_string),
  10106: ('sim/multiplay/generic/string[6]', PacketData.unpack_FGFS_buggy_string),
  10107: ('sim/multiplay/generic/string[7]', PacketData.unpack_FGFS_buggy_string),
  10108: ('sim/multiplay/generic/string[8]', PacketData.unpack_FGFS_buggy_string),
  10109: ('sim/multiplay/generic/string[9]', PacketData.unpack_FGFS_buggy_string),
  10110: ('sim/multiplay/generic/string[10]', PacketData.unpack_FGFS_buggy_string),
  10111: ('sim/multiplay/generic/string[11]', PacketData.unpack_FGFS_buggy_string),
  10112: ('sim/multiplay/generic/string[12]', PacketData.unpack_FGFS_buggy_string),
  10113: ('sim/multiplay/generic/string[13]', PacketData.unpack_FGFS_buggy_string),
  10114: ('sim/multiplay/generic/string[14]', PacketData.unpack_FGFS_buggy_string),
  10115: ('sim/multiplay/generic/string[15]', PacketData.unpack_FGFS_buggy_string),
  10116: ('sim/multiplay/generic/string[16]', PacketData.unpack_FGFS_buggy_string),
  10117: ('sim/multiplay/generic/string[17]', PacketData.unpack_FGFS_buggy_string),
  10118: ('sim/multiplay/generic/string[18]', PacketData.unpack_FGFS_buggy_string),
  10119: ('sim/multiplay/generic/string[19]', PacketData.unpack_FGFS_buggy_string),

  10200: ('sim/multiplay/generic/float[0]', PacketData.unpack_float),
  10201: ('sim/multiplay/generic/float[1]', PacketData.unpack_float),
  10202: ('sim/multiplay/generic/float[2]', PacketData.unpack_float),
  10203: ('sim/multiplay/generic/float[3]', PacketData.unpack_float),
  10204: ('sim/multiplay/generic/float[4]', PacketData.unpack_float),
  10205: ('sim/multiplay/generic/float[5]', PacketData.unpack_float),
  10206: ('sim/multiplay/generic/float[6]', PacketData.unpack_float),
  10207: ('sim/multiplay/generic/float[7]', PacketData.unpack_float),
  10208: ('sim/multiplay/generic/float[8]', PacketData.unpack_float),
  10209: ('sim/multiplay/generic/float[9]', PacketData.unpack_float),
  10210: ('sim/multiplay/generic/float[10]', PacketData.unpack_float),
  10211: ('sim/multiplay/generic/float[11]', PacketData.unpack_float),
  10212: ('sim/multiplay/generic/float[12]', PacketData.unpack_float),
  10213: ('sim/multiplay/generic/float[13]', PacketData.unpack_float),
  10214: ('sim/multiplay/generic/float[14]', PacketData.unpack_float),
  10215: ('sim/multiplay/generic/float[15]', PacketData.unpack_float),
  10216: ('sim/multiplay/generic/float[16]', PacketData.unpack_float),
  10217: ('sim/multiplay/generic/float[17]', PacketData.unpack_float),
  10218: ('sim/multiplay/generic/float[18]', PacketData.unpack_float),
  10219: ('sim/multiplay/generic/float[19]', PacketData.unpack_float),

  10300: ('sim/multiplay/generic/int[0]', PacketData.unpack_int),
  10301: ('sim/multiplay/generic/int[1]', PacketData.unpack_int),
  10302: ('sim/multiplay/generic/int[2]', PacketData.unpack_int),
  10303: ('sim/multiplay/generic/int[3]', PacketData.unpack_int),
  10304: ('sim/multiplay/generic/int[4]', PacketData.unpack_int),
  10305: ('sim/multiplay/generic/int[5]', PacketData.unpack_int),
  10306: ('sim/multiplay/generic/int[6]', PacketData.unpack_int),
  10307: ('sim/multiplay/generic/int[7]', PacketData.unpack_int),
  10308: ('sim/multiplay/generic/int[8]', PacketData.unpack_int),
  10309: ('sim/multiplay/generic/int[9]', PacketData.unpack_int),
  10310: ('sim/multiplay/generic/int[10]', PacketData.unpack_int),
  10311: ('sim/multiplay/generic/int[11]', PacketData.unpack_int),
  10312: ('sim/multiplay/generic/int[12]', PacketData.unpack_int),
  10313: ('sim/multiplay/generic/int[13]', PacketData.unpack_int),
  10314: ('sim/multiplay/generic/int[14]', PacketData.unpack_int),
  10315: ('sim/multiplay/generic/int[15]', PacketData.unpack_int),
  10316: ('sim/multiplay/generic/int[16]', PacketData.unpack_int),
  10317: ('sim/multiplay/generic/int[17]', PacketData.unpack_int),
  10318: ('sim/multiplay/generic/int[18]', PacketData.unpack_int),
  10319: ('sim/multiplay/generic/int[19]', PacketData.unpack_int)
}

def FGMS_prop_code_by_name(name):
    return next(code for code, data in FGMS_properties.items() if data[0] == name)


FGMS_prop_comm_frq = FGMS_prop_code_by_name('sim/multiplay/transmission-freq-hz')  # STRING
FGMS_prop_chat_msg = FGMS_prop_code_by_name('sim/multiplay/chat')  # STRING
FGMS_prop_XPDR_code = FGMS_prop_code_by_name('instrumentation/transponder/transmitted-id')  # INT
FGMS_prop_XPDR_alt = FGMS_prop_code_by_name('instrumentation/transponder/altitude')  # INT
FGMS_prop_XPDR_ident = FGMS_prop_code_by_name('instrumentation/transponder/ident')  # BOOL
FGMS_prop_XPDR_mode = FGMS_prop_code_by_name('instrumentation/transponder/inputs/mode')  # INT

# ======= FGFS orientation conversions =======

epsilon = 1e-8

def wxyz_quat_mult(q1, q2):
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2
    w = w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2
    x = w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2
    y = w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2
    z = w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2
    return w, x, y, z




def earth2quat(lon, lat):
    zd2 = radians(lon) / 2
    yd2 = -pi / 4 - radians(lat) / 2
    Szd2 = sin(zd2)
    Syd2 = sin(yd2)
    Czd2 = cos(zd2)
    Cyd2 = cos(yd2)
    w = Czd2 * Cyd2
    x = -Szd2 * Syd2
    y = Czd2 * Syd2
    z = Szd2 * Cyd2
    return w, x, y, z


def euler2quat(z, y, x):
    zd2 = z / 2
    yd2 = y / 2
    xd2 = x / 2
    Szd2 = sin(zd2)
    Syd2 = sin(yd2)
    Sxd2 = sin(xd2)
    Czd2 = cos(zd2)
    Cyd2 = cos(yd2)
    Cxd2 = cos(xd2)
    Cxd2Czd2 = Cxd2 * Czd2
    Cxd2Szd2 = Cxd2 * Szd2
    Sxd2Szd2 = Sxd2 * Szd2
    Sxd2Czd2 = Sxd2 * Czd2
    w = Cxd2Czd2 * Cyd2 + Sxd2Szd2 * Syd2
    x = Sxd2Czd2 * Cyd2 - Cxd2Szd2 * Syd2
    y = Cxd2Czd2 * Syd2 + Sxd2Szd2 * Cyd2
    z = Cxd2Szd2 * Cyd2 - Sxd2Czd2 * Syd2
    return w, x, y, z




def FG_orientation_XYZ(lon, lat, hdg, pitch, roll):
    local_rot = euler2quat(radians(hdg), radians(pitch), radians(roll))
    qw, qx, qy, qz = wxyz_quat_mult(earth2quat(lon, lat), local_rot)
    acw = acos(qw)
    sa = sin(acw)
    if abs(sa) < epsilon:
        return 1, 0, 0  # no rotation
    else:
        angle = 2 * acw
        k = angle / sa
        return k*qx, k*qy, k*qz


# ======= Time stuff =======


def now():
    return datetime.now(timezone.utc)

last_stopwatch_reset = now()

def read_stopwatch():
    '''
    returns a timedelta
    '''
    return (now() - last_stopwatch_reset).total_seconds()
