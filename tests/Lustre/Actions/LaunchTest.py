# test suite for launch() method in Shine.Lustre.Actions.*
# Copyright (C) 2013 CEA
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

import types
import unittest
import Utils

from Shine.Lustre.EventHandler import EventHandler
from Shine.Lustre.Server import Server
from Shine.Lustre.FileSystem import FileSystem
from Shine.Lustre.Component import MOUNTED, OFFLINE, TARGET_ERROR

class ActionsTest(unittest.TestCase):

    class ActionEH(EventHandler):
        def __init__(self):
            EventHandler.__init__(self)
            self.evlist = dict()
        def event_callback(self, compname, action, status, **kwargs):
            self.evlist['%s_%s_%s' % (compname, action, status)] = kwargs
        def clear(self):
            self.evlist.clear()
        def result(self, compname, action, status):
            evname = '%s_%s_%s' % (compname, action, status)
            return self.evlist[evname]['result']

    def assert_events(self, compname, action, status_list):
        self.assertEqual(len(self.eh.evlist), len(status_list))
        for status in status_list:
            evname = '%s_%s_%s' % (compname, action, status)
            evlist = ', '.join(self.eh.evlist)
            self.assertTrue(evname in self.eh.evlist,
                            "'%s' not in event list: %s" % (evname, evlist))

    def format(self):
        self.tgt.format().launch()
        self.fs._run_actions()
        self.eh.clear()

    def setUp(self):
        self.eh = self.ActionEH()
        self.fs = FileSystem('action', event_handler=self.eh)
        srv1 = Server("localhost", ["localhost@tcp"])
        self.disk = Utils.make_disk()
        self.tgt = self.fs.new_target(srv1, 'mgt', 0, self.disk.name)

    def tearDown(self):
        self.tgt.lustre_check()
        if self.tgt.is_started():
            self.tgt.stop().launch()
            self.fs._run_actions()

    #
    # Format
    #

    @Utils.rootonly
    def test_format_ok(self):
        """Format a simple MGT"""
        act = self.tgt.format()
        act.launch()
        self.fs._run_actions()

        # Callback checks
        self.assert_events('mgt', 'format', ['start', 'done'])
        result = self.eh.result('mgt', 'format', 'done')
        self.assertEqual(result.retcode, 0)

        # Status checks
        self.assertEqual(self.tgt.state, OFFLINE)

    @Utils.rootonly
    def test_format_if_started(self):
        """Format when target is started failed"""
        def check_set_online(self):
            self.__class__.lustre_check(self)
            self.state = MOUNTED
        self.tgt.lustre_check = types.MethodType(check_set_online, self.tgt)

        act = self.tgt.format()
        act.launch()
        self.fs._run_actions()

        # Callback checks
        self.assert_events('mgt', 'format', ['start', 'failed'])
        result = self.eh.result('mgt', 'format', 'failed')
        self.assertEqual(result.retcode, None)
        # Status checks
        self.assertEqual(self.tgt.state, TARGET_ERROR)

    @Utils.rootonly
    def test_format_with_error(self):
        """Format with bad options is an error"""
        act = self.tgt.format(addopts="--BAD-OPTIONS")
        act.launch()
        self.fs._run_actions()

        # Callback checks
        self.assert_events('mgt', 'format', ['start', 'failed'])
        result = self.eh.result('mgt', 'format', 'failed')
        self.assertEqual(result.retcode, 22)

        # Status checks
        self.assertEqual(self.tgt.state, OFFLINE)

    # XXX: Add tests with Journal

    #
    # Fsck
    #
    @Utils.rootonly
    def test_fsck_ok(self):
        """Fsck on a freshly formatted target is ok"""
        self.format()
        act = self.tgt.fsck()
        act.launch()
        self.fs._run_actions()

        # Callback checks
        self.assert_events('mgt', 'fsck', ['start', 'progress', 'done'])
        result = self.eh.result('mgt', 'fsck', 'done')
        self.assertEqual(result.retcode, 0)
        # Status checks
        self.assertEqual(self.tgt.state, OFFLINE)

    @Utils.rootonly
    def test_fsck_repairs(self):
        """Fsck repairs a corruption"""
        self.format()
        # Corrupt FS
        self.disk.seek(1024)
        self.disk.write('\0' * 1024)
        self.disk.flush()
        act = self.tgt.fsck()
        act.launch()
        self.fs._run_actions()

        # Callback checks
        self.assert_events('mgt', 'fsck', ['start', 'progress', 'done'])
        result = self.eh.result('mgt', 'fsck', 'done')
        self.assertEqual(result.message, "Errors corrected")
        self.assertEqual(result.retcode, 1)

        # Status checks
        self.assertEqual(self.tgt.state, OFFLINE)

    @Utils.rootonly
    def test_fsck_no_repair(self):
        """Fsck detects but does not repair a corruption with -n"""
        self.format()
        # Corrupt FS
        self.disk.seek(1024)
        self.disk.write('\0' * 1024)
        self.disk.flush()
        act = self.tgt.fsck(addopts='-n')
        act.launch()
        self.fs._run_actions()

        # Callback checks
        self.assert_events('mgt', 'fsck', ['start', 'progress', 'done'])
        result = self.eh.result('mgt', 'fsck', 'done')
        self.assertEqual(result.message, "Errors found but NOT corrected")
        self.assertEqual(result.retcode, 4)

        # Status checks
        self.assertEqual(self.tgt.state, OFFLINE)

    @Utils.rootonly
    def test_fsck_with_error(self):
        """Fsck on an unformated device fails"""
        act = self.tgt.fsck()
        act.launch()
        self.fs._run_actions()

        # Callback checks
        self.assert_events('mgt', 'fsck', ['start', 'failed'])
        result = self.eh.result('mgt', 'fsck', 'failed')
        self.assertEqual(result.retcode, 8)

        # Status checks
        self.assertEqual(self.tgt.state, TARGET_ERROR)

    #
    # Execute
    #
    def test_execute_ok(self):
        """Execute of a simple command is ok"""
        act = self.tgt.execute(addopts='/bin/echo %device', mountdata='never')
        act.launch()
        self.fs._run_actions()

        # Callback checks
        self.assert_events('mgt', 'execute', ['start', 'done'])
        result = self.eh.result('mgt', 'execute', 'done')
        self.assertEqual(result.retcode, 0)
        # Status checks
        self.assertEqual(self.tgt.state, OFFLINE)

    def test_execute_error(self):
        """Execute a bad command fails"""
        act = self.tgt.execute(addopts='/bin/false', mountdata='never')
        act.launch()
        self.fs._run_actions()

        # Callback checks
        self.assert_events('mgt', 'execute', ['start', 'failed'])
        result = self.eh.result('mgt', 'execute', 'failed')
        self.assertEqual(result.retcode, 1)
        # Status checks
        self.assertEqual(self.tgt.state, OFFLINE)

    @Utils.rootonly
    def test_execute_check_mountdata(self):
        """Execute a command with mountdata check"""
        self.format()
        act = self.tgt.execute(addopts="ls %device", mountdata='always')
        act.launch()
        self.fs._run_actions()

        # Callback checks
        self.assert_events('mgt', 'execute', ['start', 'done'])
        result = self.eh.result('mgt', 'execute', 'done')
        self.assertEqual(result.retcode, 0)
        # Status checks
        self.assertEqual(self.tgt.state, OFFLINE)

    #
    # Status
    #
    @Utils.rootonly
    def test_status_ok(self):
        """Status on a simple target"""
        self.format()
        act = self.tgt.status()
        act.launch()
        self.fs._run_actions()

        # Callback checks
        self.assert_events('mgt', 'status', ['start', 'done'])
        result = self.eh.result('mgt', 'status', 'done')
        self.assertEqual(result, None)
        # Status checks
        self.assertEqual(self.tgt.state, OFFLINE)

    def test_status_error(self):
        """Status on a not-formated target fails"""
        act = self.tgt.status()
        act.launch()
        self.fs._run_actions()

        # Callback checks
        self.assert_events('mgt', 'status', ['start', 'failed'])
        result = self.eh.result('mgt', 'status', 'failed')
        self.assertEqual(result.retcode, None)
        # Status checks
        self.assertEqual(self.tgt.state, TARGET_ERROR)

    #
    # Start Target
    #
    @Utils.rootonly
    def test_start_ok(self):
        """Start a simple target"""
        self.format()
        act = self.tgt.start()
        act.launch()
        self.fs._run_actions()

        # Callback checks
        self.assert_events('mgt', 'start', ['start', 'done'])
        result = self.eh.result('mgt', 'start', 'done')
        self.assertEqual(result.retcode, 0)
        # Status checks
        self.assertEqual(self.tgt.state, MOUNTED)

    @Utils.rootonly
    def test_start_already_done(self):
        """Start an already mounted target returns ok"""
        self.format()
        def is_started(self):
            self.state = MOUNTED
            return True
        self.tgt.is_started = types.MethodType(is_started, self.tgt)
        act = self.tgt.start()
        act.launch()
        self.fs._run_actions()

        # Callback checks
        self.assert_events('mgt', 'start', ['start', 'done'])
        result = self.eh.result('mgt', 'start', 'done')
        self.assertEqual(result.message, "MGS is already started")
        self.assertEqual(result.retcode, None)
        # Status checks
        self.assertEqual(self.tgt.state, MOUNTED)

    @Utils.rootonly
    def test_start_error(self):
        """Start an non-formated target fails"""
        act = self.tgt.start()
        act.launch()
        self.fs._run_actions()

        # Callback checks
        self.assert_events('mgt', 'start', ['start', 'failed'])
        result = self.eh.result('mgt', 'start', 'failed')
        self.assertEqual(result.retcode, None)
        # Status checks
        self.assertEqual(self.tgt.state, TARGET_ERROR)

    #
    # Stop Target
    #
    @Utils.rootonly
    def test_stop_ok(self):
        """Start a simple target"""
        self.format()
        # Start the target, to be able to unmount it after
        act = self.tgt.start()
        act.launch()
        self.fs._run_actions()
        self.eh.clear()

        act = self.tgt.stop()
        act.launch()
        self.fs._run_actions()

        # Callback checks
        self.assert_events('mgt', 'stop', ['start', 'done'])
        result = self.eh.result('mgt', 'stop', 'done')
        self.assertEqual(result.retcode, 0)
        # Status checks
        self.assertEqual(self.tgt.state, OFFLINE)

    @Utils.rootonly
    def test_stop_already_done(self):
        """Stop an already stopped target fails"""
        self.format()
        act = self.tgt.stop()
        act.launch()
        self.fs._run_actions()

        # Callback checks
        self.assert_events('mgt', 'stop', ['start', 'done'])
        result = self.eh.result('mgt', 'stop', 'done')
        self.assertEqual(result.message, "MGS is already stopped")
        self.assertEqual(result.retcode, None)
        # Status checks
        self.assertEqual(self.tgt.state, OFFLINE)

    @Utils.rootonly
    def test_stop_error(self):
        """Stop target failure is an error"""
        self.format()
        # Start the target, to be able to unmount it after
        self.tgt.start().launch()
        self.fs._run_actions()
        self.eh.clear()

        act = self.tgt.stop()
        def _prepare_cmd(_self):
            return [ "/bin/false" ]
        act._prepare_cmd = types.MethodType(_prepare_cmd, act)
        act.launch()
        self.fs._run_actions()

        # Callback checks
        self.assert_events('mgt', 'stop', ['start', 'failed'])
        result = self.eh.result('mgt', 'stop', 'failed')
        self.assertEqual(result.retcode, 1)
        # Status checks
        self.assertEqual(self.tgt.state, MOUNTED)

