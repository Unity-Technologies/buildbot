# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

import datetime
import os
from twisted.trial import unittest
from twisted.internet import defer
from buildbot.db import buildrequests, builds
from buildbot.status import builder, master
from buildbot.test.fake import fakemaster, fakedb
from buildbot.test.util import connector_component
from buildbot.util import UTC, epoch2datetime

class TestBuildStepStatus(connector_component.ConnectorComponentMixin,
                          unittest.TestCase):

    # that buildstep.BuildStepStatus is never instantiated here should tell you
    # that these classes are not well isolated!
    CLAIMED_AT = datetime.datetime(1978, 6, 15, 12, 31, 15, tzinfo=UTC)
    CLAIMED_AT_EPOCH = 266761875
    SUBMITTED_AT = datetime.datetime(1979, 6, 15, 12, 31, 15, tzinfo=UTC)
    SUBMITTED_AT_EPOCH = 298297875
    COMPLETE_AT = datetime.datetime(1980, 6, 15, 12, 31, 15, tzinfo=UTC)
    COMPLETE_AT_EPOCH = 329920275
    BSID = 567
    BSID2 = 5670
    MASTER_ID = "set in setUp"
    OTHER_MASTER_ID = "set in setUp"

    MASTER_NAME = "testmaster"
    MASTER_INCARN = "pid123-boot456789"

    def setUp(self):
        self.MASTER_ID = fakedb.FakeBuildRequestsComponent.MASTER_ID
        self.OTHER_MASTER_ID = self.MASTER_ID + 1111
        d = self.setUpConnectorComponent(table_names=['buildrequests', 'builds' ])

        def finish_setup(_):
            self.db.buildrequests = \
                    buildrequests.BuildRequestsConnectorComponent(self.db)
            self.db.builds = builds.BuildsConnectorComponent(self.db)
            self.db.master.getObjectId = lambda : defer.succeed(self.MASTER_ID)
        d.addCallback(finish_setup)

        return d

    def setupBuilder(self, buildername, category=None, description=None):
        self.master = fakemaster.make_master()
        self.master.basedir = '/basedir'

        b = builder.BuilderStatus(buildername, self.master, category, description)
        b.project = "Project"
        b.master = self.master
        # Ackwardly, Status sets this member variable.
        b.basedir = os.path.abspath(self.mktemp())
        os.mkdir(b.basedir)
        # Otherwise, builder.nextBuildNumber is not defined.
        b.determineNextBuildNumber()
        return b

    def setupStatus(self, b):
        s = master.Status(self.master)
        b.status = s
        return s

    def testBuildStepNumbers(self):
        b = self.setupBuilder('builder_1')
        bs = b.newBuild()
        self.assertEquals(0, bs.getNumber())
        bss1 = bs.addStepWithName('step_1', None)
        self.assertEquals('step_1', bss1.getName())
        bss2 = bs.addStepWithName('step_2', None)
        self.assertEquals(0, bss1.asDict()['step_number'])
        self.assertEquals('step_2', bss2.getName())
        self.assertEquals(1, bss2.asDict()['step_number'])
        self.assertEquals([bss1, bss2], bs.getSteps())

    def testLogDict(self):
        b = self.setupBuilder('builder_1')
        self.setupStatus(b)
        bs = b.newBuild()
        bss1 = bs.addStepWithName('step_1', None)
        bss1.stepStarted()
        bss1.addLog('log_1')
        self.assertEquals(
            bss1.asDict()['logs'],
            [['log_1', ('http://localhost:8080/projects/Project/builders/builder_1/'
                        'builds/0/steps/step_1/logs/log_1')]]
            )

    def testaddHtmlLog_with_no_content_type(self):
        b = self.setupBuilder('builder_1')
        self.setupStatus(b)
        bs = b.newBuild()
        bss1 = bs.addStepWithName('step_1', None)
        bss1.stepStarted()
        bss1.addHTMLLog('htmllog_1', "html")

        self.assertEquals(
            bss1.asDict()['logs'],
            [['htmllog_1', ('http://localhost:8080/projects/Project/builders/builder_1/'
                        'builds/0/steps/step_1/logs/htmllog_1')]]
            )
        self.assertEqual(len(bss1.logs), 1)
        self.assertEqual(bss1.logs[0].content_type, None)

    def testaddHtmlLog_with_content_type(self):
        b = self.setupBuilder('builder_1')
        self.setupStatus(b)
        bs = b.newBuild()
        bss1 = bs.addStepWithName('step_1', None)
        bss1.stepStarted()
        content_type = "test_content_type"
        bss1.addHTMLLog('htmllog_1', "html", content_type)

        self.assertEqual(len(bss1.logs), 1)
        self.assertEqual(bss1.logs[0].content_type, content_type)

    def testaddHtmlLog_with_content_type_multiple_logs(self):
        b = self.setupBuilder('builder_1')
        self.setupStatus(b)
        bs = b.newBuild()
        bss1 = bs.addStepWithName('step_1', None)
        bss1.stepStarted()
        content_type1 = "test_content_type"
        content_type2 = "json"
        bss1.addHTMLLog('htmllog_1', "html", content_type1)
        bss1.addHTMLLog('htmllog_2', "html 2")
        bss1.addHTMLLog('htmllog_3', "html 2", content_type2)

        self.assertEqual(len(bss1.logs), 3)
        self.assertEqual(bss1.logs[0].content_type, content_type1)
        self.assertEqual(bss1.logs[1].content_type, None)
        self.assertEqual(bss1.logs[2].content_type, content_type2)


    def test_addURLs(self):
        b = self.setupBuilder('builder_1')
        self.setupStatus(b)
        bs = b.newBuild()
        bss1 = bs.addStepWithName('step_1', None)
        bss1.stepStarted()

        urlList = dict()
        urlList["URL"] = "http://www.url"
        urlList["URL2"] = "http://www.url2"

        bss1.addURL("URL", "http://www.url")
        bss1.addURL("URL2", "http://www.url2")
        self.assertEquals(bss1.getURLs(), urlList)

    def test_prepare_trigger_links_for_nontrigger(self):
        from buildbot.steps.shell import ShellCommand
        builder = self.setupBuilder('builder_1')
        self.setupStatus(builder)
        build = builder.newBuild()

        shell_step_status = build.addStepWithName('step_1', ShellCommand)
        shell_step_status.prepare_trigger_links()
        self.assertEqual(len(shell_step_status.urls), 0)

    @defer.inlineCallbacks
    def test_prepare_trigger_link_for_trigger(self):
        from buildbot.steps.trigger import Trigger
        builder = self.setupBuilder('builder_1')
        self.setupStatus(builder)
        build = builder.newBuild()

        trigger_step_status = build.addStepWithName('step_2', Trigger)
        build.builder.master.db = self.db
        build.brids = [1]
        build.builder.master.status.getURLForBuild = lambda x,y: {'path':x, 'text': y}

        breqs = [
            fakedb.BuildRequest(id=1, buildsetid=1, complete=1, results=0,  buildername="bldr1", priority=50, submitted_at=1518616728, startbrid=None),
            fakedb.BuildRequest(id=2, buildsetid=1, complete=1, results=0,  buildername="sub-bldr1", priority=50, submitted_at=1518616728, startbrid=1),
        ]
        builds = [
            fakedb.Build(id=20, brid=1, number=5, start_time=1518616728, finish_time=1518617000),
            fakedb.Build(id=21, brid=2, number=6, start_time=1518616728, finish_time=1518617000),
        ]
        self.insertTestData(breqs + builds)

        yield trigger_step_status.prepare_trigger_links()
        self.assertEqual(len(trigger_step_status.urls), 1)

