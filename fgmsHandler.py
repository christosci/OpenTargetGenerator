
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

from socket import socket, AF_INET, SOCK_DGRAM, SOL_SOCKET, SO_REUSEADDR
from fgms import FGMShandshaker

FGMS_handshake_interval = 0.5  # seconds


class FgmsHandler:
    """Creates sockets and starts the fgms connection for each aircraft."""

    def __init__(self, aircraft):
        """__init__ function."""
        self.aircraft = aircraft
        self.start()

    def start(self):
        """Start FGMShandshaker."""
        try:
            self.socket = socket(AF_INET, SOCK_DGRAM)
            self.socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        except OSError as error:
            self.socket = None
            print('Connection error: %s' % error)
        else:
            self.FGMS_handshaker = FGMShandshaker(self.socket, self.aircraft)
            self.fgms_handshake()

    def stop(self):
        """Stop FGMShandshaker."""
        if self.is_running():
            self.socket = None
            self.FGMS_handshaker.set_status(False)

    def is_running(self):
        """Check if socket is open."""
        return self.socket is not None

    def fgms_handshake(self):
        """Start FGMShandshaker thread."""
        self.FGMS_handshaker.start()
