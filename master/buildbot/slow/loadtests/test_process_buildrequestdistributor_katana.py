from twisted.trial import unittest
from twisted.internet import defer
from buildbot.db.buildrequests import Queue
from buildbot.status.results import RESUME, BEGINNING
from buildbot.process.buildrequest import Priority
from buildbot.test.util.katanabuildrequestdistributor import KatanaBuildRequestDistributorTestSetup

class TestKatanaBuildRequestDistributorUnderLoad(unittest.TestCase,
                                                 KatanaBuildRequestDistributorTestSetup):

    @defer.inlineCallbacks
    def setUp(self):
        yield self.setUpComponents()
        self.setUpKatanaBuildRequestDistributor()

    @defer.inlineCallbacks
    def tearDown(self):
        yield self.tearDownComponents()
        self.stopKatanaBuildRequestDistributor()

    def createBuildersWithLoad(self, priority, slavenames, startSlavenames,
                               builders_xrange, breqs_xrange, selected_slave=None):
        for id in builders_xrange:
            buildername = 'bldr%d' % (self.lastbuilderid+id)
            if buildername not in self.botmaster.builders.keys():
                self.setupBuilderInMaster(name=buildername, slavenames=slavenames, startSlavenames=startSlavenames)
            self.insertBuildrequests(buildername, priority, breqs_xrange, selected_slave=selected_slave)
            self.insertBuildrequests(buildername, priority, breqs_xrange, results=RESUME, selected_slave=selected_slave)

        self.lastbuilderid += len(builders_xrange)

    @defer.inlineCallbacks
    def generateBuildLoadCalculateNextPriorityBuilder(self):
        self.initialized()

        self.createBuildersWithLoad(priority=Priority.Default, slavenames={'slave-01': True},
                                    startSlavenames={'slave-02': True},
                                    builders_xrange=xrange(1, 6),
                                    breqs_xrange=xrange(1, 350))

        # breqs has selected slave x slave-03
        self.createBuildersWithLoad(priority=Priority.VeryHigh,
                                    slavenames={'slave-03': False, 'slave-04': True},
                                    startSlavenames={'slave-05': False},
                                    builders_xrange=xrange(1, 6),
                                    breqs_xrange=xrange(1, 700),
                                    selected_slave='slave-03')

        # breqs dont have available slave
        self.createBuildersWithLoad(priority=Priority.Emergency,
                                    slavenames={'slave-05': False},
                                    startSlavenames={'slave-06': False},
                                    builders_xrange=xrange(1, 6),
                                    breqs_xrange=xrange(1, 700))

        self.createBuildersWithLoad(priority=Priority.High,
                                    slavenames={'slave-07': True},
                                    startSlavenames={'slave-08': True},
                                    builders_xrange=xrange(1, 701),
                                    breqs_xrange=xrange(1, 2))

        # add a build with a selectec slave available ?

        yield self.insertTestData(self.testdata)

    @defer.inlineCallbacks
    def generateBuildLoadStartOrResumeBuilds(self, slaves_available=True):

        self.initialized()

        slavenames = self.createSlaveList(available=slaves_available, xrange=xrange(0, 100))
        startSlavenames = self.createSlaveList(available=slaves_available, xrange=xrange(100, 200))

        slavenames2 = self.createSlaveList(available=slaves_available, xrange=xrange(200, 300))
        startSlavenames2 = self.createSlaveList(available=slaves_available, xrange=xrange(300, 400))

        self.createBuildersWithLoad(priority=Priority.Emergency,
                                    slavenames={'slave-01': False},
                                    startSlavenames={'slave-02': True},
                                    builders_xrange=xrange(1, 3),
                                    breqs_xrange=xrange(1, 3))

        self.createBuildersWithLoad(priority=Priority.Emergency,
                                    slavenames={'slave-03': True},
                                    startSlavenames={'slave-04': False},
                                    builders_xrange=xrange(1, 3),
                                    breqs_xrange=xrange(1, 3))

        self.createBuildersWithLoad(priority=Priority.VeryHigh,
                                    slavenames=slavenames,
                                    startSlavenames=startSlavenames,
                                    builders_xrange=xrange(1, 5),
                                    breqs_xrange=xrange(1, 70))

        self.createBuildersWithLoad(priority=Priority.High,
                                    slavenames=slavenames2,
                                    startSlavenames=startSlavenames2,
                                    builders_xrange=xrange(1, 5),
                                    breqs_xrange=xrange(1, 70))

        self.createBuildersWithLoad(priority=Priority.Default,
                                    slavenames=slavenames,
                                    startSlavenames=startSlavenames,
                                    builders_xrange=xrange(1, 3),
                                    breqs_xrange=xrange(1, 4))

        self.createBuildersWithLoad(priority=Priority.High,
                                    slavenames={'slave-01': False},
                                    startSlavenames={'slave-02': False},
                                    builders_xrange=xrange(1, 701),
                                    breqs_xrange=xrange(1, 2))

        self.createBuildersWithLoad(priority=Priority.High,
                                    slavenames={'slave-05': True},
                                    startSlavenames={'slave-06': False},
                                    builders_xrange=xrange(1, 2),
                                    breqs_xrange=xrange(1, 2), selected_slave='slave-05')

        yield self.insertTestData(self.testdata)

    @defer.inlineCallbacks
    def generateLoadBusyBuildFarmResumeBuilds(self):
        self.initialized()

        slavenames = self.createSlaveList(available=False, xrange=xrange(0, 100))
        startSlavenames = self.createSlaveList(available=True, xrange=xrange(100, 120))

        self.createBuildersWithLoad(priority=Priority.Emergency,
                                    slavenames={'slave-01': False},
                                    startSlavenames={'slave-02': False},
                                    builders_xrange=xrange(1, 3),
                                    breqs_xrange=xrange(1, 3))

        self.createBuildersWithLoad(priority=Priority.Emergency,
                                    slavenames={'slave-03': False},
                                    startSlavenames={'slave-04': False},
                                    builders_xrange=xrange(1, 3),
                                    breqs_xrange=xrange(1, 3))

        self.createBuildersWithLoad(priority=Priority.VeryHigh,
                                    slavenames=slavenames,
                                    startSlavenames=startSlavenames,
                                    builders_xrange=xrange(1, 50),
                                    breqs_xrange=xrange(1, 70))

        self.createBuildersWithLoad(priority=Priority.Default,
                                    slavenames=slavenames,
                                    startSlavenames=startSlavenames,
                                    builders_xrange=xrange(1, 50),
                                    breqs_xrange=xrange(1, 70))

        yield self.insertTestData(self.testdata)

    @defer.inlineCallbacks
    def generateBuildLoadWithDifferentMerges(self):
        self.initialized()

        slavenames = self.createSlaveList(available=True, xrange=xrange(0, 200))
        startSlavenames = self.createSlaveList(available=True, xrange=xrange(200, 400))

        self.initialized()
        sources1 = [{'repository': 'repo1', 'codebase': 'cb1', 'branch': 'master', 'revision': 'asz3113'}]
        sources2 = [{'repository': 'repo2', 'codebase': 'cb2', 'branch': 'develop', 'revision': 'asz3114'}]

        for id in xrange(1, 200):
            buildername = 'bldr%d' % (self.lastbuilderid+id)
            if buildername not in self.botmaster.builders.keys():
                self.setupBuilderInMaster(name=buildername, slavenames=slavenames,
                                          startSlavenames=startSlavenames, addRunningBuilds=True)

                # merges pending build
                self.insertBuildrequests(buildername, Priority.High, xrange(1, 30),
                                         results=BEGINNING, sources=sources1)
                # merges with finished builds
                self.insertBuildrequests(buildername, 50, xrange(1, 2),
                                         complete=1, results=0, startbrid=1, sources=sources2)
                self.insertBuildrequests(buildername, Priority.Default, xrange(1, 20),
                                         results=BEGINNING, sources=sources2, startbrid=1)

        yield self.insertTestData(self.testdata)

    @defer.inlineCallbacks
    def generateNewBuildsToBeMerged(self):
        self.testdata = []
        sources1 = [{'repository': 'repo1', 'codebase': 'cb1', 'branch': 'master', 'revision': 'asz3113'}]
        for buildername in self.botmaster.builders.keys():
            # merges with running builds
            self.insertBuildrequests(buildername, Priority.VeryHigh,
                                     xrange(1, 20), results=BEGINNING, sources=sources1)

        yield self.insertTestData(self.testdata)

    @defer.inlineCallbacks
    def test_getNextPriorityBuilderUnclaimedQueueUnderLoad(self):
        yield self.generateBuildLoadCalculateNextPriorityBuilder()
        breq = yield self.profileAsyncFunc(0.319, self.brd._selectNextBuildRequest,
                                           queue=Queue.unclaimed,
                                           asyncFunc=self.brd._maybeStartBuildsOnBuilder)
        self.assertEqual(breq.buildername, 'bldr16')

    @defer.inlineCallbacks
    def test_getNextPriorityBuilderResumeQueueUnderLoad(self):
        yield self.generateBuildLoadCalculateNextPriorityBuilder()
        breq =  yield self.profileAsyncFunc(9, self.brd._selectNextBuildRequest,
                                            queue=Queue.resume,
                                            asyncFunc=self.brd._maybeResumeBuildsOnBuilder)

        self.assertEquals(breq.buildername, 'bldr16')

    @defer.inlineCallbacks
    def test_maybeStartOrResumeBuildsOnUnderLoad(self):
        yield self.generateBuildLoadStartOrResumeBuilds()

        yield self.profileAsyncFunc(10.6, self.brd._maybeStartOrResumeBuildsOn,
                                    new_builders=self.botmaster.builders.keys())

        self.checkBRDCleanedUp()
        self.assertEquals(self.processedBuilds[0], ('slave-02', [1]))
        self.assertEquals(self.processedBuilds[1], ('slave-03', [11]))
        self.assertEquals(len(self.slaves), 406)
        self.assertEquals(len(self.processedBuilds), 403)

    @defer.inlineCallbacks
    def test_maybeStartOrResumeBuildsOnUnderLoadBusyBuildFarm(self):
        yield self.generateBuildLoadStartOrResumeBuilds(slaves_available=False)

        yield self.profileAsyncFunc(3.8, self.brd._maybeStartOrResumeBuildsOn,
                                    new_builders=self.botmaster.builders.keys())

        self.checkBRDCleanedUp()
        self.assertEquals(self.processedBuilds[0], ('slave-02', [1]))
        self.assertEquals(self.processedBuilds[1], ('slave-03', [11]))
        self.assertEquals(len(self.slaves), 406)
        self.assertEquals(len(self.processedBuilds), 3)

    @defer.inlineCallbacks
    def test_maybeStartOrResumeBuildsOnBusyBuildFarmResumeBuilds(self):
        yield self.generateLoadBusyBuildFarmResumeBuilds()

        yield self.profileAsyncFunc(2, self.brd._maybeStartOrResumeBuildsOn,
                                    new_builders=self.botmaster.builders.keys())

        self.checkBRDCleanedUp()
        self.assertEquals(len(self.processedBuilds), 20)

    @defer.inlineCallbacks
    def test_maybeStartOrResumeBuildsUnderLoadHandleMerges(self):
        yield self.generateBuildLoadWithDifferentMerges()

        yield self.profileAsyncFunc(42, self.brd._maybeStartOrResumeBuildsOn,
                                    new_builders=self.botmaster.builders.keys())

        self.checkBRDCleanedUp()
        yield  self.generateNewBuildsToBeMerged()

        yield self.profileAsyncFunc(18, self.brd._maybeStartOrResumeBuildsOn,
                                    new_builders=self.botmaster.builders.keys())
        self.assertEquals(len(self.processedBuilds), 199)
        self.assertEquals(len(self.mergedBuilds), 398)

