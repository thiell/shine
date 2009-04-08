# FSClientLiveCommand.py -- Base commands class: live client-side filesystem
# Copyright (C) 2009 CEA
#
# This file is part of shine
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
# $Id$

"""
Base class for live client filesystem commands (mount, umount)
"""

from RemoteCommand import RemoteCommand

# Options support classes
from Support.Nodes import Nodes
from Support.FS import FS
from Support.Verbose import Verbose


class FSClientLiveCommand(RemoteCommand):
    """
    shine <cmd> [-f <fsname>] [-n <nodes>] [-dqv]
    """
    
    def __init__(self):
        RemoteCommand.__init__(self)

        self.fs_support = FS(self, optional=True)
        self.nodes_support = Nodes(self)
        self.verbose_support = Verbose(self)
