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

from zope.interface import implements
from twisted.python import log
from twisted.internet import defer
from buildbot import interfaces
from buildbot.util.eventual import eventually

class BuildRequestStatus:
    implements(interfaces.IBuildRequestStatus)

    def __init__(self, buildername, brid, status):
        self.buildername = buildername
        self.brid = brid
        self.status = status
        self.master = status.master

        self._buildrequest = None
        self._buildrequest_lock = defer.DeferredLock()

    @defer.inlineCallbacks
    def _getBuildRequest(self):
        """
        Get the underlying BuildRequest object for this status.  This is a slow
        operation!

        @returns: BuildRequest instance or None, via Deferred
        """
        # late binding to avoid an import cycle
        from buildbot.process import buildrequest

        # this is only set once, so no need to lock if we already have it
        if self._buildrequest:
            defer.returnValue(self._buildrequest)
            return

        yield self._buildrequest_lock.acquire()

        try:
            if not self._buildrequest:
                brd = yield self.master.db.buildrequests.getBuildRequest(
                                                                    self.brid)

                br = yield buildrequest.BuildRequest.fromBrdict(self.master,
                                                                    brd)
                self._buildrequest = br
        except: # try/finally isn't allowed in generators in older Pythons
            self._buildrequest_lock.release()
            raise

        self._buildrequest_lock.release()

        defer.returnValue(self._buildrequest)

    def buildStarted(self, build):
        self.status._buildrequest_buildStarted(build.status)
        self.builds.append(build.status)

    # methods called by our clients
    @defer.inlineCallbacks
    def getBsid(self):
        br = yield self._getBuildRequest()
        defer.returnValue(br.bsid)

    @defer.inlineCallbacks
    def getBuildProperties(self):
        br = yield self._getBuildRequest()
        defer.returnValue(br.properties)

    @defer.inlineCallbacks
    def getSourceStamp(self):
        br = yield self._getBuildRequest()
        defer.returnValue(br.source)

    @defer.inlineCallbacks
    def getSourceStamps(self):
        br = yield self._getBuildRequest()
        defer.returnValue(br.sources)

    def getBuilderName(self):
        return self.buildername

    @defer.inlineCallbacks
    def getBuilds(self):
        builder = self.status.getBuilder(self.getBuilderName())
        builds = []

        if not builder:
            log.msg("Buildrequest %d has unknown builder %s" % (self.brid, self.buildername))
            defer.returnValue(builds)
            return

        bdicts = yield self.master.db.builds.getBuildsForRequest(self.brid)

        buildnums = sorted([ bdict['number'] for bdict in bdicts ])

        for buildnum in buildnums:
            bs = builder.getBuild(buildnum)
            if bs:
                builds.append(bs)
        defer.returnValue(builds)

    def subscribe(self, observer):
        d = self.getBuilds()
        def notify_old(oldbuilds):
            for bs in oldbuilds:
                eventually(observer, bs)
        d.addCallback(notify_old)
        d.addCallback(lambda _ :
            self.status._buildrequest_subscribe(self.brid, observer))
        d.addErrback(log.err, 'while notifying subscribers')

    def unsubscribe(self, observer):
        self.status._buildrequest_unsubscribe(self.brid, observer)

    @defer.inlineCallbacks
    def getSubmitTime(self):
        br = yield self._getBuildRequest()
        defer.returnValue(br.submittedAt)

    @defer.inlineCallbacks
    def getReason(self):
        br = yield self._getBuildRequest()
        defer.returnValue(br.reason)

    @defer.inlineCallbacks
    def getResults(self):
        br = yield self._getBuildRequest()
        if hasattr(br, 'results'):
            defer.returnValue(br.results)
        else:
            defer.returnValue(-1)

    def getSlaves(self):
        builder = self.status.getBuilder(self.getBuilderName())
        if builder is not None:
            return builder.slavenames

        return []

    def asDict(self):
        result = {}
        # Constant
        result['brid'] = self.brid
        result['source'] = None # not available sync, sorry
        result['builderName'] = self.buildername
        result['submittedAt'] = None # not availably sync, sorry
        result['slaves'] =  self.getSlaves()
        result['reason'] = None # not availably sync, sorry
        result['builderURL'] = self.status.getURLForThing(self.status.getBuilder(self.getBuilderName()))

        # Transient
        result['builds'] = [] # not available async, sorry
        return result

    @defer.inlineCallbacks
    def asDict_async(self, request=None):
        result = {}

        builder = self.status.getBuilder(self.getBuilderName())
        if not builder:
            defer.returnValue(result)
            return

        ss = yield self.getSourceStamp()
        sources = yield self.getSourceStamps()
        result['brid'] = self.brid
        result['source'] = ss.asDict(self.status)
        result['sources'] = [s.asDict() for s in sources.values()]
        props = yield self.getBuildProperties()
        result['properties'] = props.asList()
        result['builderName'] = self.getBuilderName()
        result['reason'] = yield self.getReason()
        result['slaves'] =  self.getSlaves()
        result['submittedAt'] = yield self.getSubmitTime()
        result['results'] = yield self.getResults()

        result['builderFriendlyName'] = builder.getFriendlyName()
        result['builderURL'] = self.status.getURLForThing(builder)

        if request is not None:
            from buildbot.status.web.base import getCodebasesArg
            result['builderURL'] += getCodebasesArg(request)

        builds = yield self.getBuilds()
        all_builds = [build.asDict() for build in builds]
        sorted_builds = sorted(all_builds, key=lambda build: build['number'], reverse=True)
        result['builds'] = sorted_builds
        result['lastBuildNumber'] = sorted_builds[0]['number'] if sorted_builds and len(sorted_builds) > 0 \
                                                                  and 'number' in sorted_builds[0] else None

        defer.returnValue(result)
