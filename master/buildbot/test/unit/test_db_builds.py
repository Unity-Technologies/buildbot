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
import mock
from datetime import timedelta, datetime
from freezegun import freeze_time

from twisted.trial import unittest
from twisted.internet import defer, task
from buildbot.db import builds
from buildbot.db.builds import BuildDoNotExist
from buildbot.status import build
from buildbot.test.fake.botmaster import FakeBotMaster
from buildbot.test.util import connector_component
from buildbot.test.fake import fakedb, fakemaster
from buildbot.util import epoch2datetime
from buildbot.status.results import SUCCESS


class TestBuildsConnectorComponent(
    connector_component.ConnectorComponentMixin,
    unittest.TestCase):
    SUBMITTED_AT_EPOCH = 298297875
    COMPLETE_AT_EPOCH = 329920275

    def setUp(self):
        d = self.setUpConnectorComponent(
            table_names=['builds', 'buildrequests', 'buildsets',
                         'sourcestamps', 'sourcestampsets', 'patches'])

        def finish_setup(_):
            self.db.builds = builds.BuildsConnectorComponent(self.db)

        d.addCallback(finish_setup)

        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()

    # common sample data

    background_data = [
        fakedb.SourceStampSet(id=27),
        fakedb.SourceStamp(id=27, sourcestampsetid=27, revision='abcd'),
        fakedb.Buildset(id=20, sourcestampsetid=27),
        fakedb.Buildset(id=30, sourcestampsetid=27),
        fakedb.BuildRequest(id=41, buildsetid=20, buildername='b1'),
        fakedb.BuildRequest(id=42, buildsetid=30, buildername='b1'),
    ]

    last_builds = [fakedb.BuildRequest(id=1, buildsetid=1, buildername="builder",
                                       complete=1, results=0,
                                       submitted_at=SUBMITTED_AT_EPOCH,
                                       complete_at=COMPLETE_AT_EPOCH),
                   fakedb.Buildset(id=1, sourcestampsetid=1),
                   fakedb.SourceStampSet(id=1),
                   fakedb.SourceStamp(id=1, revision='a', codebase='1',
                                      sourcestampsetid=1, branch='master', repository='z'),
                   fakedb.SourceStamp(id=2, revision='b', codebase='2', sourcestampsetid=1,
                                      branch='staging', repository='w'),
                   fakedb.Build(id=1, number=4, brid=1, start_time=SUBMITTED_AT_EPOCH,
                                finish_time=COMPLETE_AT_EPOCH, slavename='slave-01')]

    # tests

    def test_getBuild(self):
        d = self.insertTestData(self.background_data + [
            fakedb.Build(id=50, brid=42, number=5, start_time=1304262222),
        ])
        d.addCallback(lambda _:
                      self.db.builds.getBuild(50))

        def check(bdict):
            self.assertEqual(bdict, dict(bid=50, number=5, brid=42,
                                         start_time=epoch2datetime(1304262222), finish_time=None))

        d.addCallback(check)
        return d

    def test_getBuild_missing(self):
        d = defer.succeed(None)
        d.addCallback(lambda _:
                      self.db.builds.getBuild(50))

        def check(bdict):
            self.assertEqual(bdict, None)

        d.addCallback(check)
        return d

    def test_getBuildsForRequest(self):
        d = self.insertTestData(self.background_data + [
            fakedb.Build(id=50, brid=42, number=5, start_time=1304262222),
            fakedb.Build(id=51, brid=41, number=6, start_time=1304262223),
            fakedb.Build(id=52, brid=42, number=7, start_time=1304262224,
                         finish_time=1304262235),
        ])
        d.addCallback(lambda _:
                      self.db.builds.getBuildsForRequest(42))

        def check(bdicts):
            self.assertEqual(sorted(bdicts), sorted([
                dict(bid=50, number=5, brid=42,
                     start_time=epoch2datetime(1304262222), finish_time=None),
                dict(bid=52, number=7, brid=42,
                     start_time=epoch2datetime(1304262224),
                     finish_time=epoch2datetime(1304262235)),
            ]))

        d.addCallback(check)
        return d

    def test_addBuild(self):
        clock = task.Clock()
        clock.advance(1302222222)
        d = self.insertTestData(self.background_data)
        d.addCallback(lambda _:
                      self.db.builds.addBuild(brid=41, number=119, slavename="slave-01", _reactor=clock))

        def check(_):
            def thd(conn):
                r = conn.execute(self.db.model.builds.select())
                rows = [(row.brid, row.number, row.start_time,
                         row.finish_time) for row in r.fetchall()]
                self.assertEqual(rows,
                                 [(41, 119, 1302222222, None)])

            return self.db.pool.do(thd)

        d.addCallback(check)
        return d

    def test_finishBuilds(self):
        clock = task.Clock()
        clock.advance(1305555555)

        d = self.insertTestData(self.background_data + [
            fakedb.Build(id=50, brid=41, number=5, start_time=1304262222),
            fakedb.Build(id=51, brid=42, number=5, start_time=1304262222),
            fakedb.Build(id=52, brid=42, number=6, start_time=1304262222),
        ])
        d.addCallback(lambda _:
                      self.db.builds.finishBuilds([50, 51], _reactor=clock))

        def check(_):
            def thd(conn):
                r = conn.execute(self.db.model.builds.select())
                rows = [(row.id, row.brid, row.number, row.start_time,
                         row.finish_time) for row in r.fetchall()]
                self.assertEqual(sorted(rows), [
                    (50, 41, 5, 1304262222, 1305555555),
                    (51, 42, 5, 1304262222, 1305555555),
                    (52, 42, 6, 1304262222, None),
                ])

            return self.db.pool.do(thd)

        d.addCallback(check)
        return d

    def test_finishBuilds_big(self):
        clock = task.Clock()
        clock.advance(1305555555)

        d = self.insertTestData(self.background_data + [
            fakedb.Build(id=nn, brid=41, number=nn, start_time=1304262222)
            for nn in xrange(50, 200)
        ])
        d.addCallback(lambda _:
                      self.db.builds.finishBuilds(range(50, 200), _reactor=clock))

        def check(_):
            def thd(conn):
                r = conn.execute(self.db.model.builds.select())
                rows = [(row.id, row.brid, row.number, row.start_time,
                         row.finish_time) for row in r.fetchall()]
                self.assertEqual(sorted(rows), [
                    (nn, 41, nn, 1304262222, 1305555555)
                    for nn in xrange(50, 200)
                ])

            return self.db.pool.do(thd)

        d.addCallback(check)
        return d

    @defer.inlineCallbacks
    def test_getLastBuildsNumbersCodeBasesFound(self):
        yield self.insertTestData(self.last_builds)

        sourcestamps_filter = [{'b_codebase': '1', 'b_branch': 'master'},
                               {'b_codebase': '2', 'b_branch': 'staging'}]

        lastBuildNumber = yield self.db.builds.getLastBuildsNumbers(buildername="builder",
                                                                    sourcestamps=sourcestamps_filter, num_builds=1)

        self.assertEqual(lastBuildNumber, [4])

    @defer.inlineCallbacks
    def test_getLastBuildsNumbersCodeBasesNotFound(self):
        yield self.insertTestData(self.last_builds)

        sourcestamps_filter = [{'b_codebase': '1', 'b_branch': 'development'},
                               {'b_codebase': '2', 'b_branch': 'qa'}]

        lastBuildNumber = yield self.db.builds.getLastBuildsNumbers(buildername="builder",
                                                                    sourcestamps=sourcestamps_filter, num_builds=1)

        self.assertEqual(lastBuildNumber, [])

    @defer.inlineCallbacks
    def test_getLastBuildsNumbersOneFilter(self):
        yield self.insertTestData(self.last_builds)

        sourcestamps_filter = [{'b_codebase': '1', 'b_branch': 'master'}]

        lastBuildNumber = yield self.db.builds.getLastBuildsNumbers(buildername="builder",
                                                                    sourcestamps=sourcestamps_filter, num_builds=1)

        self.assertEqual(lastBuildNumber, [4])

    @defer.inlineCallbacks
    def test_getLastBuildsNumbersMultipleBuilds(self):
        builds = [fakedb.BuildRequest(id=2, buildsetid=2, buildername="builder",
                                      complete=1, results=0,
                                      submitted_at=self.SUBMITTED_AT_EPOCH,
                                      complete_at=self.COMPLETE_AT_EPOCH),
                  fakedb.Buildset(id=2, sourcestampsetid=2),
                  fakedb.SourceStampSet(id=2),
                  fakedb.SourceStamp(id=3, revision='a', codebase='1',
                                     sourcestampsetid=2, branch='master', repository='z'),
                  fakedb.SourceStamp(id=4, revision='b', codebase='4', sourcestampsetid=2,
                                     branch='development', repository='w'),
                  fakedb.Build(id=2, number=3, brid=2, start_time=self.SUBMITTED_AT_EPOCH,
                               finish_time=self.COMPLETE_AT_EPOCH)]
        yield self.insertTestData(self.last_builds + builds)

        sourcestamps_filter = [{'b_codebase': '1', 'b_branch': 'master'},
                               {'b_codebase': '2', 'b_branch': 'qa'}]

        lastBuildNumber = yield self.db.builds.getLastBuildsNumbers(buildername="builder",
                                                                    sourcestamps=sourcestamps_filter, num_builds=4)

        self.assertEqual(lastBuildNumber, [3])

    @defer.inlineCallbacks
    def test_getLastBuildsNumbersFilterBranchResults(self):
        builds = [fakedb.BuildRequest(id=2, buildsetid=2, buildername="builder",
                                      complete=1, results=4,
                                      submitted_at=self.SUBMITTED_AT_EPOCH,
                                      complete_at=self.COMPLETE_AT_EPOCH),
                  fakedb.Buildset(id=2, sourcestampsetid=2),
                  fakedb.SourceStampSet(id=2),
                  fakedb.SourceStamp(id=3, revision='a', codebase='1',
                                     sourcestampsetid=2, branch='master', repository='z'),
                  fakedb.SourceStamp(id=4, revision='b', codebase='4', sourcestampsetid=2,
                                     branch='development', repository='w'),
                  fakedb.Build(id=2, number=3, brid=2, start_time=self.SUBMITTED_AT_EPOCH,
                               finish_time=self.COMPLETE_AT_EPOCH)]
        yield self.insertTestData(self.last_builds + builds)

        sourcestamps_filter = [{'b_branch': 'master'}, {'b_branch': 'qa'}]

        lastBuildNumber = yield self.db.builds.getLastBuildsNumbers(buildername="builder",
                                                                    sourcestamps=sourcestamps_filter,
                                                                    results=[0],
                                                                    num_builds=4)

        self.assertEqual(lastBuildNumber, [4])

        lastBuildNumber = yield self.db.builds.getLastBuildsNumbers(buildername="builder",
                                                                    sourcestamps=sourcestamps_filter,
                                                                    results=[0, 4],
                                                                    num_builds=4)

        self.assertEqual(lastBuildNumber, [4, 3])

    @defer.inlineCallbacks
    def insertRecentBuilds(self):
        builds = [{'buildername': "builder",
                   'submitted_at': 1457706077,
                   'complete_at': 1457706089,
                   'revision': 'abzdewf',
                   'slavename': 'slave-02'},
                  {'buildername': "builder",
                   'submitted_at': 1457895804,
                   'complete_at': 1457895819,
                   'revision': 'zbzdewf',
                   'slavename': 'slave-01'},
                  {'buildername': "builder-01",
                   'submitted_at': 1457895804,
                   'complete_at': 1457895819,
                   'revision': 'zbzdewf',
                   'slavename': 'slave-01'},
                  {'buildername': "builder",
                   'submitted_at': self.SUBMITTED_AT_EPOCH,
                   'complete_at': self.COMPLETE_AT_EPOCH,
                   'revision': 'fwbzdeif',
                   'slavename': 'slave-01'}]

        recent_builds = []

        for idx, b in enumerate(builds):
            rowid = idx + 1
            recent_builds += [fakedb.BuildRequest(id=rowid, buildsetid=rowid, buildername=b['buildername'],
                                                  complete=1, results=SUCCESS,
                                                  submitted_at=b['submitted_at'],
                                                  complete_at=b['complete_at']),
                              fakedb.Buildset(id=rowid, sourcestampsetid=rowid),
                              fakedb.SourceStampSet(id=rowid),
                              fakedb.SourceStamp(id=rowid, revision=b['revision'], codebase='1',
                                                 sourcestampsetid=rowid, branch='master', repository='z'),
                              fakedb.Build(id=rowid, number=rowid, brid=rowid,
                                           start_time=b['submitted_at'],
                                           finish_time=b['complete_at'],
                                           slavename=b['slavename'])
                              ]
        yield self.insertTestData(recent_builds)

    @defer.inlineCallbacks
    def test_getLastBuildsNumbersOrderByCompleted(self):
        yield self.insertRecentBuilds()

        builds = yield self.db.builds.getLastBuildsNumbers(buildername="builder")
        self.assertEquals([2, 1, 4], builds)

    @defer.inlineCallbacks
    def test_getLastsBuildsNumbersBySlave(self):
        builds = [fakedb.BuildRequest(id=2, buildsetid=2, buildername="builder1",
                                      complete=1, results=0,
                                      submitted_at=self.SUBMITTED_AT_EPOCH,
                                      complete_at=self.COMPLETE_AT_EPOCH),
                  fakedb.Buildset(id=2, sourcestampsetid=2),
                  fakedb.SourceStampSet(id=2),
                  fakedb.SourceStamp(id=3, revision='a', codebase='1',
                                     sourcestampsetid=2, branch='master', repository='z'),
                  fakedb.SourceStamp(id=4, revision='b', codebase='4', sourcestampsetid=2,
                                     branch='development', repository='w'),
                  fakedb.Build(id=2, number=3, brid=2, start_time=self.SUBMITTED_AT_EPOCH,
                               finish_time=self.COMPLETE_AT_EPOCH, slavename='slave-01'),
                  fakedb.BuildRequest(id=3, buildsetid=2, buildername="builder2",
                                      complete=1, results=0,
                                      submitted_at=self.SUBMITTED_AT_EPOCH,
                                      complete_at=self.COMPLETE_AT_EPOCH),
                  fakedb.Build(id=3, number=5, brid=3, start_time=self.SUBMITTED_AT_EPOCH,
                               finish_time=self.COMPLETE_AT_EPOCH, slavename='slave-02')]
        yield self.insertTestData(self.last_builds + builds)

        lastBuildNumber = yield self.db.builds.getLastsBuildsNumbersBySlave(slavename='slave-01')
        self.assertEqual(lastBuildNumber, {'builder': [4], 'builder1': [3]})

        lastBuildNumber = yield self.db.builds.getLastsBuildsNumbersBySlave(slavename='slave-02')
        self.assertEqual(lastBuildNumber, {'builder2': [5]})

    @defer.inlineCallbacks
    def test_getLastsBuildsNumbersBySlaveFilterResults(self):
        builds = [fakedb.BuildRequest(id=2, buildsetid=2, buildername="builder1",
                                      complete=1, results=4,
                                      submitted_at=self.SUBMITTED_AT_EPOCH,
                                      complete_at=self.COMPLETE_AT_EPOCH),
                  fakedb.Buildset(id=2, sourcestampsetid=2),
                  fakedb.SourceStampSet(id=2),
                  fakedb.SourceStamp(id=3, revision='a', codebase='1',
                                     sourcestampsetid=2, branch='master', repository='z'),
                  fakedb.SourceStamp(id=4, revision='b', codebase='4', sourcestampsetid=2,
                                     branch='development', repository='w'),
                  fakedb.Build(id=2, number=3, brid=2, start_time=self.SUBMITTED_AT_EPOCH,
                               finish_time=self.COMPLETE_AT_EPOCH, slavename='slave-01'),
                  fakedb.BuildRequest(id=3, buildsetid=2, buildername="builder2",
                                      complete=1, results=7,
                                      submitted_at=self.SUBMITTED_AT_EPOCH,
                                      complete_at=self.COMPLETE_AT_EPOCH),
                  fakedb.Build(id=3, number=5, brid=3, start_time=self.SUBMITTED_AT_EPOCH,
                               finish_time=self.COMPLETE_AT_EPOCH, slavename='slave-02')]
        yield self.insertTestData(self.last_builds + builds)

        lastBuildNumber = yield self.db.builds.getLastsBuildsNumbersBySlave(slavename='slave-01', results=[0, 4])
        self.assertEqual(lastBuildNumber, {'builder': [4], 'builder1': [3]})

        lastBuildNumber = yield self.db.builds.getLastsBuildsNumbersBySlave(slavename='slave-02', results=[7])
        self.assertEqual(lastBuildNumber, {'builder2': [5]})

    @defer.inlineCallbacks
    def test_getLastsBuildsNumbersBySlaveOrderByCompleted(self):
        yield self.insertRecentBuilds()

        builds = yield self.db.builds.getLastsBuildsNumbersBySlave(slavename="slave-01")
        self.assertEquals(builds, {'builder-01': [3], 'builder': [2, 4]})


class TestGetLastBuildsOwnedBy(
    connector_component.ConnectorComponentMixin,
    unittest.TestCase
):

    def setUp(self):
        d = self.setUpConnectorComponent(
            table_names=['builds', 'build_user', 'buildrequests', 'buildsets', 'sourcestamps', 'sourcestampsets', 'patches', 'buildset_properties']
        )
        self.master = fakemaster.make_master(wantDb=True, testcase='Tests for getTopBuildUrl method')

        def finish_setup(_):
            self.db.builds = builds.BuildsConnectorComponent(self.db)

        d.addCallback(finish_setup)

        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()

    @staticmethod
    def _collect_ids(builds, attribute):
        return sorted([item[attribute] for item in builds])

    @defer.inlineCallbacks
    def test_results_are_correctly_limited_by_builds_completed_time(self):
        today_time = 1519115900
        day_count = 7
        user_id = 1
        expired_time = today_time - (day_count * 24 * 60 * 60) # 7 days = 24hours * 60minuts * 60seconds
        example_data = [
            fakedb.Buildset(id=2, sourcestampsetid=2, reason='[ first_user ]'),
            fakedb.BuildRequest(id=3, buildsetid=2, buildername="builder2", complete=1, results=7),
        ] + [
            # Should be included in result
            fakedb.Build(id=1, number=3, brid=3, slavename='slave-02', finish_time=1519115855),
            fakedb.BuildUser(buildid=1, userid=user_id, finish_time=1519115855),
            fakedb.Build(id=2, number=4, brid=3, slavename='slave-02', finish_time=1519115865),
            fakedb.BuildUser(buildid=2, userid=user_id, finish_time=1519115865),
            fakedb.Build(id=3, number=5, brid=3, slavename='slave-02', finish_time=1519115875),
            fakedb.BuildUser(buildid=3, userid=user_id, finish_time=1519115875),
            fakedb.Build(id=4, number=6, brid=3, slavename='slave-02', finish_time=1519115885),
            fakedb.BuildUser(buildid=4, userid=user_id, finish_time=1519115885),
            fakedb.Build(id=5, number=7, brid=3, slavename='slave-02', finish_time=1519115895),
            fakedb.BuildUser(buildid=5, userid=user_id, finish_time=1519115895),
        ] + [
            # Shouldn't be included in result
            fakedb.Build(id=6, number=8, brid=3, slavename='slave-02', finish_time=expired_time - 30),
            fakedb.BuildUser(buildid=6, userid=user_id, finish_time=expired_time - 30),
            fakedb.Build(id=7, number=9, brid=3, slavename='slave-02', finish_time=expired_time - 40),
            fakedb.BuildUser(buildid=7, userid=user_id, finish_time=expired_time - 40),
            fakedb.Build(id=8, number=10, brid=3, slavename='slave-02', finish_time=expired_time - 50),
            fakedb.BuildUser(buildid=8, userid=user_id, finish_time=expired_time - 50),
            fakedb.Build(id=9, number=11, brid=3, slavename='slave-02', finish_time=expired_time - 60),
            fakedb.BuildUser(buildid=9, userid=user_id, finish_time=expired_time - 60),
            fakedb.Build(id=10, number=12, brid=3, slavename='slave-02', finish_time=expired_time - 70),
            fakedb.BuildUser(buildid=10, userid=user_id, finish_time=expired_time - 70),
            fakedb.Build(id=11, number=13, brid=3, slavename='slave-02', finish_time=expired_time - 80),
            fakedb.BuildUser(buildid=11, userid=user_id, finish_time=expired_time - 80),
            fakedb.Build(id=12, number=14, brid=3, slavename='slave-02', finish_time=expired_time - 90),
            fakedb.BuildUser(buildid=12, userid=user_id, finish_time=expired_time - 90),
            fakedb.Build(id=13, number=15, brid=3, slavename='slave-02', finish_time=expired_time - 100),
            fakedb.BuildUser(buildid=13, userid=user_id, finish_time=expired_time - 100),
        ]
        yield self.insertTestData(example_data)

        with freeze_time("2018-02-20 8:38:00"):
            first_user_builds = yield self.db.builds.getLastBuildsOwnedBy(
                user_id,
                FakeBotMaster(self.master),
                day_count,
            )
        self.assertEqual(len(first_user_builds), 5)
        self.assertEqual(self._collect_ids(first_user_builds, 'builds_id'), [1, 2, 3, 4, 5])

    @defer.inlineCallbacks
    def test_results_are_correctly_filtered_for_user(self):
        day_count = 7
        first_user_builds_count = 15
        second_user_builds_count = 30
        first_user_id = 1
        second_user_id = 2
        second_user_max_build_id = first_user_builds_count + second_user_builds_count

        example_data = [
            fakedb.Buildset(id=2, sourcestampsetid=2, reason='[ first_user ]'),
            fakedb.Buildset(id=3, sourcestampsetid=2, reason='[ second_user ]'),

            fakedb.BuildRequest(id=3, buildsetid=2, buildername="builder2", complete=1, results=7),
            fakedb.BuildRequest(id=4, buildsetid=3, buildername="buillder3", complete=1, results=7),
        ] + [
            fakedb.Build(id=i, number=i+2, brid=3, slavename='slave-02', finish_time=(1519115855 - 50 * i))
            for i in xrange(first_user_builds_count)
        ] + [
            fakedb.Build(id=i, number=i + 2, brid=4, slavename='slave-02', finish_time=(1519115855 - 50 * i))
            for i in xrange(first_user_builds_count, second_user_max_build_id)
        ] + [
            fakedb.BuildUser(buildid=i, userid=first_user_id, finish_time=(1519115855 - 50 * i))
            for i in xrange(first_user_builds_count)
        ] + [
            fakedb.BuildUser(buildid=i, userid=second_user_id, finish_time=(1519115855 - 50 * i))
            for i in xrange(first_user_builds_count, second_user_max_build_id)
        ]

        yield self.insertTestData(example_data)

        with freeze_time("2018-02-20 8:38:00"):
            second_user_builds = yield self.db.builds.getLastBuildsOwnedBy(
                second_user_id,
                FakeBotMaster(self.master),
                day_count,
            )
        self.assertEqual(len(second_user_builds), second_user_builds_count)
        self.assertEqual(
            self._collect_ids(second_user_builds, 'builds_id'),
            range(first_user_builds_count, second_user_max_build_id)
        )


class TestGetBuildIDForRequest(
    connector_component.ConnectorComponentMixin,
    unittest.TestCase,
):

    def setUp(self):
        d = self.setUpConnectorComponent(table_names=['builds', 'buildrequests'])
        self.master = fakemaster.make_master(wantDb=True, testcase='Tests for getBuildIDForRequest method')

        def finish_setup(_):
            self.db.builds = builds.BuildsConnectorComponent(self.db)

        d.addCallback(finish_setup)

        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()

    @defer.inlineCallbacks
    def testGetBuildIDForRequestsIfBuildExists(self):
        example_data = [
            fakedb.BuildRequest(id=1, buildsetid=1, buildername="builder2", complete=1, results=7),
            fakedb.BuildRequest(id=2, buildsetid=1, buildername="builder3", complete=1, results=7),
            fakedb.Build(id=1, number=3, brid=1, slavename='slave-02', finish_time=1519115855),
            fakedb.Build(id=2, number=4, brid=1, slavename='slave-01', finish_time=1519115850),
            fakedb.Build(id=3, number=3, brid=2, slavename='slave-01', finish_time=1519115850),
        ]
        yield self.insertTestData(example_data)

        bid1 = yield self.db.builds.getBuildIDForRequest(1, 3)
        bid2 = yield self.db.builds.getBuildIDForRequest(1, 4)
        bid3 = yield self.db.builds.getBuildIDForRequest(2, 3)

        self.assertEqual(bid1, 1)
        self.assertEqual(bid2, 2)
        self.assertEqual(bid3, 3)

    @defer.inlineCallbacks
    def testGetBuildIDForRequestIfBuildNotExists(self):
        example_data = [
            fakedb.BuildRequest(id=1, buildsetid=1, buildername="builder2", complete=1, results=7),
        ]
        yield self.insertTestData(example_data)

        with self.assertRaises(BuildDoNotExist):
            yield self.db.builds.getBuildIDForRequest(1, 1)


    @defer.inlineCallbacks
    def testGetBuildIDForRequestIfBuildRequestNotExists(self):
        #Empty database

        with self.assertRaises(BuildDoNotExist):
            yield self.db.builds.getBuildIDForRequest(1, 1)
