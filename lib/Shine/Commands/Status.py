# Status.py -- Check remote filesystem servers and targets status
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
Shine `status' command classes.

The status command aims to return the real state of a Lustre filesystem
and its components, depending of the requested "view". Status views let
the Lustre administrator to either stand back and get a global status
of the filesystem, or if needed, to enquire about filesystem components
detailed states.
"""

# Configuration
from Shine.Configuration.Configuration import Configuration
from Shine.Configuration.Globals import Globals 
from Shine.Configuration.Exceptions import *

# Command base class
from Base.FSLiveCommand import FSLiveCommand
# Additional options
from Base.Support.View import View

# Error handling
from Exceptions import CommandBadParameterError

# -R handler
from RemoteCallEventHandler import RemoteCallEventHandler

# Command helper
from Shine.FSUtils import open_lustrefs

# Command output formatting
from Shine.Utilities.AsciiTable import *

# Lustre events and errors
import Shine.Lustre.EventHandler
from Shine.Lustre.Disk import *
from Shine.Lustre.FileSystem import *
from Shine.Lustre.Target import *

from ClusterShell.NodeSet import NodeSet

import os
import socket


(KILO, MEGA, GIGA, TERA) = (1024, 1048576, 1073741824, 1099511627776)

class GlobalStatusEventHandler(Shine.Lustre.EventHandler.EventHandler):

    def __init__(self, verbose=False):
        self.verbose = verbose
        self.failures = 0
        self.success = 0

    def ev_statustarget_start(self, node, target):
        pass

    def ev_statustarget_done(self, node, target):
        self.success += 1
        #print "ev_status_done %s" % target

    def ev_statustarget_failed(self, node, target, rc, message):
        self.failures += 1
        print "%s: Failed to status %s %s (%s)" % (node, target.type.upper(), \
                target.get_id(), target.dev)
        print ">> %s" % message

    def ev_statusclient_start(self, node, client):
        pass

    def ev_statusclient_done(self, node, client):
        pass

    def ev_statusclient_failed(self, node, client, rc, message):
        print "%s: Failed to status of FS %s" % (node, client.fs.fs_name)
        print ">> %s" % message

    def complete(self):
        if self.failures == 0:
            print "Status successful."
            return 0
        else:
            if self.failures == 1:
                print "Status failed (%d error)" % self.failures
            else:
                print "Status failed (%d errors)" % self.failures
            return 1


class Status(FSLiveCommand):
    """
    shine status [-f <fsname>] [-t <target>] [-i <index(es)>] [-n <nodes>] [-qv]
    """

    def __init__(self):
        FSLiveCommand.__init__(self)
        self.view_support = View(self)

    def get_name(self):
        return "status"

    def get_desc(self):
        return "Check for file system target status."

    def execute(self):

        if self.local_flag or self.remote_call:
            self.opt_n = socket.gethostname()

        target = self.target_support.get_target()
        for fsname in self.fs_support.iter_fsname():

            if self.remote_call:
                handler = RemoteCallEventHandler()
            else:
                handler = GlobalStatusEventHandler()

            fs_conf, fs = open_lustrefs(fsname, target,
                    nodes=self.nodes_support.get_nodeset(),
                    indexes=self.indexes_support.get_rangeset(),
                    event_handler=handler)

            fs.set_debug(self.debug_support.has_debug())

            status_flags = STATUS_ANY
            view = self.view_support.get_view()

            # default view
            if view is None:
                view = "fs"
            else:
                view = view.lower()

            # disable client checks when not requested
            if view.startswith("disk") or view.startswith("target"):
                status_flags &= ~STATUS_CLIENTS
            # disable servers checks when not requested
            if view.startswith("client"):
                status_flags &= ~(STATUS_SERVERS|STATUS_HASERVERS)

            fs.status(status_flags)

            if self.local_flag or self.remote_call:
                return

            if view == "fs":
                self.status_view_fs(fs)
            elif view.startswith("target"):
                self.status_view_targets(fs)
            elif view.startswith("disk"):
                self.status_view_disks(fs)
            else:
                raise CommandBadParameterError(self.view_support.get_view(),
                        "fs, targets, disks")
            

    def status_view_targets(self, fs):
        """
        View: lustre targets
        """
        print "FILESYSTEM TARGETS (%s)" % fs.fs_name

        # override dict to allow target sorting by index
        class target_dict(dict):
            def __lt__(self, other):
                return self["index"] < other["index"]

        ldic = []
        for type, (all_targets, enabled_targets) in fs.targets_by_type():
            for target in enabled_targets:

                if target.state == DOWN:
                    status = "offline"
                elif target.state == LOADED:
                    status = "INCOHERENT"
                elif target.state == MOUNT_RECOVERY:
                    status = "recovering %s" % target.status_info
                elif target.state == MOUNT_COMPLETE:
                    status = "online"
                else:
                    status = "UNKNOWN"

                ldic.append(target_dict([["target", target.get_id()],
                    ["type", target.type.upper()],
                    ["nodes", NodeSet.fromlist(target.servers)],
                    ["device", target.dev],
                    ["index", target.index],
                    ["status", status]]))

        ldic.sort()
        layout = AsciiTableLayout()
        layout.set_show_header(True)
        layout.set_column("target", 0, AsciiTableLayout.LEFT, "target id",
                AsciiTableLayout.CENTER)
        layout.set_column("type", 1, AsciiTableLayout.LEFT, "type",
                AsciiTableLayout.CENTER)
        layout.set_column("index", 2, AsciiTableLayout.RIGHT, "idx",
                AsciiTableLayout.CENTER)
        layout.set_column("nodes", 3, AsciiTableLayout.LEFT, "nodes",
                AsciiTableLayout.CENTER)
        layout.set_column("device", 4, AsciiTableLayout.LEFT, "device",
                AsciiTableLayout.CENTER)
        layout.set_column("status", 5, AsciiTableLayout.LEFT, "status",
                AsciiTableLayout.CENTER)

        AsciiTable().print_from_list_of_dict(ldic, layout)


    def status_view_fs(self, fs):
        """
        View: lustre FS summary
        """
        ldic = []

        # targets
        for type, (a_targets, e_targets) in fs.targets_by_type():
            nodes = NodeSet()
            t_offline = []
            t_incoherent = []
            t_recovering = []
            t_online = []
            t_unknown = []
            for target in a_targets:
                nodes.add(target.servers[0])

                # check target status
                if target.state == DOWN:
                    t_offline.append(target)
                elif target.state == LOADED:
                    t_incoherent.append(target)
                elif target.state == MOUNT_RECOVERY:
                    t_recovering.append(target)
                elif target.state == MOUNT_COMPLETE:
                    t_online.append(target)
                else:
                    t_unknown.append(target)

            status = []
            if len(t_offline) > 0:
                status.append("offline (%d)" % len(t_offline))
            if len(t_incoherent) > 0:
                status.append("INCOHERENT (%d)" % len(t_incoherent))
            if len(t_recovering) > 0:
                status.append("recovering (%d) for %s" % (len(t_recovering),
                    t_recovering[0].status_info))
            if len(t_online) > 0:
                status.append("online (%d)" % len(t_online))
            if len(t_unknown) > 0:
                status.append("not checked (%d)" % len(t_unknown))

            if len(t_unknown) < len(a_targets):
                ldic.append(dict([["type", "%s" % type.upper()],
                    ["count", len(a_targets)], ["nodes", nodes],
                    ["status", ', '.join(status)]]))

        # clients
        (c_ign, c_down, c_loaded, c_mounted) = fs.get_client_statecounters()
        status = []
        if c_ign > 0:
            status.append("not checked (%d)" % c_ign)
        if c_down > 0:
            status.append("not mounted (%d)" % c_down)
        if c_loaded > 0:
            status.append("INCOHERENT (%d)" % c_loaded)
        if c_mounted > 0:
            status.append("mounted (%d)" % c_mounted)

        ldic.append(dict([["type", "CLI"], ["count", len(fs.clients)],
            ["nodes", "%s" % fs.get_client_servers()], ["status", ', '.join(status)]]))

        layout = AsciiTableLayout()
        layout.set_show_header(True)
        layout.set_column("type", 0, AsciiTableLayout.CENTER, "type", AsciiTableLayout.CENTER)
        layout.set_column("count", 1, AsciiTableLayout.RIGHT, "#", AsciiTableLayout.CENTER)
        layout.set_column("nodes", 2, AsciiTableLayout.LEFT, "nodes", AsciiTableLayout.CENTER)
        layout.set_column("status", 3, AsciiTableLayout.LEFT, "status", AsciiTableLayout.CENTER)

        print "FILESYSTEM COMPONENTS STATUS (%s)" % fs.fs_name
        AsciiTable().print_from_list_of_dict(ldic, layout)


    def status_view_disks(self, fs):
        """
        View: lustre disks
        """

        print "FILESYSTEM DISKS (%s)" % fs.fs_name

        # override dict to allow target sorting by index
        class target_dict(dict):
            def __lt__(self, other):
                return self["index"] < other["index"] 
        ldic = []
        jdev_col_enabled = False
        tag_col_enabled = False
        for type, (all_targets, enabled_targets) in fs.targets_by_type():
            for target in enabled_targets:

                if target.state == DOWN:
                    status = "offline"
                elif target.state == LOADED:
                    status = "INCOHERENT"
                elif target.state == MOUNT_RECOVERY:
                    status = "recovering %s" % target.status_info
                elif target.state == MOUNT_COMPLETE:
                    status = "online"
                else:
                    status = "UNKNOWN"

                if target.dev_size >= TERA:
                    dev_size = "%.1fT" % (target.dev_size/TERA)
                elif target.dev_size >= GIGA:
                    dev_size = "%.1fG" % (target.dev_size/GIGA)
                elif target.dev_size >= MEGA:
                    dev_size = "%.1fM" % (target.dev_size/MEGA)
                elif target.dev_size >= KILO:
                    dev_size = "%.1fK" % (target.dev_size/KILO)
                else:
                    dev_size = "%d" % target.dev_size

                if target.jdev:
                    jdev_col_enabled = True
                    jdev = target.jdev
                else:
                    jdev = ""

                if target.tag:
                    tag_col_enabled = True
                    tag = target.tag
                else:
                    tag = ""

                flags = []
                if target.has_need_index_flag():
                    flags.append("need_index")
                if target.has_first_time_flag():
                    flags.append("first_time")
                if target.has_update_flag():
                    flags.append("update")
                if target.has_rewrite_ldd_flag():
                    flags.append("rewrite_ldd")
                if target.has_writeconf_flag():
                    flags.append("writeconf")
                if target.has_upgrade14_flag():
                    flags.append("upgrade14")
                if target.has_param_flag():
                    flags.append("conf_param")

                ldic.append(target_dict([\
                    ["nodes", NodeSet.fromlist(target.servers)],
                    ["dev", target.dev],
                    ["size", dev_size],
                    ["jdev", jdev],
                    ["type", target.type.upper()],
                    ["index", target.index],
                    ["tag", tag],
                    ["label", target.label],
                    ["flags", ' '.join(flags)],
                    ["fsname", target.fs.fs_name],
                    ["status", status]]))

        ldic.sort()
        layout = AsciiTableLayout()
        layout.set_show_header(True)
        i = 0
        layout.set_column("nodes", i, AsciiTableLayout.LEFT, "node(s)",
                AsciiTableLayout.CENTER)
        i += 1
        layout.set_column("dev", i, AsciiTableLayout.LEFT, "device",
                AsciiTableLayout.CENTER)
        i += 1
        layout.set_column("size", i, AsciiTableLayout.RIGHT, "dev size",
                AsciiTableLayout.CENTER)
        if jdev_col_enabled:
            i += 1
            layout.set_column("jdev", i, AsciiTableLayout.RIGHT, "journal device",
                    AsciiTableLayout.CENTER)
        i += 1
        layout.set_column("type", i, AsciiTableLayout.LEFT, "type",
                AsciiTableLayout.CENTER)
        i += 1
        layout.set_column("index", i, AsciiTableLayout.RIGHT, "index",
                AsciiTableLayout.CENTER)
        if tag_col_enabled:
            i += 1
            layout.set_column("tag", i, AsciiTableLayout.LEFT, "tag",
                    AsciiTableLayout.CENTER)
        i += 1
        layout.set_column("label", i, AsciiTableLayout.LEFT, "label",
                AsciiTableLayout.CENTER)
        i += 1
        layout.set_column("flags", i, AsciiTableLayout.LEFT, "ldd flags",
                AsciiTableLayout.CENTER)
        i += 1
        layout.set_column("fsname", i, AsciiTableLayout.LEFT, "fsname",
                AsciiTableLayout.CENTER)
        i += 1
        layout.set_column("status", i, AsciiTableLayout.LEFT, "status",
                AsciiTableLayout.CENTER)

        AsciiTable().print_from_list_of_dict(ldic, layout)

