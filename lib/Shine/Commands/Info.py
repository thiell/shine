# Info.py -- Info of file system
# Copyright (C) 2007 CEA
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

from Shine.Configuration.Configuration import Configuration
from Shine.Configuration.Globals import Globals 
from Shine.Configuration.Exceptions import *
from Base.Command import Command
from Shine.Lustre.FileSystem import FileSystem

import getopt
import sys

# ----------------------------------------------------------------------
# * shine status
# ----------------------------------------------------------------------
class Info(Command):
    def get_name(self):
        return "info"

    def get_params_desc(self):
        return "-f <fsname>"

    def get_desc(self):
        return "General file system information."

    def execute(self, args):
        try:
            fs_name = None
            options, arguments = getopt.getopt(args, "f:")
            for opt, arg in options:
                if opt == '-f':
                    fs_name = arg
            if not fs_name:
                print "Error: at this time, you must specify -f <fsname>"
                sys.exit(1)

            conf = Configuration(fs_name=fs_name)
            fs = FileSystem(conf)
            fs.info()

        except getopt.GetoptError:
            raise
        except ConfigException, e:
            print e
        except IOError, e:
            print e
