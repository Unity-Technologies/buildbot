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

from __future__ import with_statement

import os
import re
import shutil
import time
from urlparse import urljoin
from cPickle import dump

from zope.interface import implements
from twisted.python import log, runtime, components
from twisted.persisted import styles
from twisted.internet import reactor, defer, threads
from buildbot import interfaces, util, sourcestamp
from buildbot.process import properties
from buildbot.process.buildtag import BuildTag
from buildbot.status.buildstep import BuildStepStatus
from buildbot.status.results import SUCCESS, NOT_REBUILT, SKIPPED, RESUME, CANCELED, RETRY, MERGED

# Avoid doing an import since it creates circular reference

TriggerType = "<class 'buildbot.steps.trigger.Trigger'>"
AcquireBuildLocksType = "<class 'buildbot.steps.artifact.AcquireBuildLocks'>"


class BuildStatus(styles.Versioned, properties.PropertiesMixin):
    implements(interfaces.IBuildStatus, interfaces.IStatusEvent)

    persistenceVersion = 4
    persistenceForgets = ( 'wasUpgraded', )

    sources = None
    reason = None
    changes = []
    blamelist = []
    progress = None
    resume = []
    resumeSlavepool = None
    started = None
    finished = None
    submitted = None
    owners = None
    buildChainID = None
    brids = []
    currentStep = None
    text = []
    results = None
    slavename = "???"
    foi_url = None
    artifacts = None

    set_runtime_properties = True

    # these lists/dicts are defined here so that unserialized instances have
    # (empty) values. They are set in __init__ to new objects to make sure
    # each instance gets its own copy.
    watchers = []
    updates = {}
    finishedWatchers = []
    testResults = {}

    def __init__(self, parent, master, number):
        """
        @type  parent: L{BuilderStatus}
        @type  number: int
        """
        assert interfaces.IBuilderStatus(parent)
        self.builder = parent
        self.master = master
        self.number = number
        self.watchers = []
        self.updates = {}
        self.finishedWatchers = []
        self.steps = []
        self.testResults = {}
        self.resume = []
        self.resumeSlavepool = None
        self.properties = properties.Properties()

    def __repr__(self):
        return "<%s #%s>" % (self.__class__.__name__, self.number)

    # IBuildStatus

    def getBuilder(self):
        """
        @rtype: L{BuilderStatus}
        """
        return self.builder

    def getNumber(self):
        return self.number

    def getPreviousBuild(self):
        if self.number == 0:
            return None
        return self.builder.getBuild(self.number-1)

    def getAllGotRevisions(self):
        all_got_revisions = self.properties.getProperty('got_revision', {})
        # For backwards compatibility all_got_revisions is a string if codebases
        # are not used. Convert to the default internal type (dict)
        if not isinstance(all_got_revisions, dict):
            all_got_revisions = {'': all_got_revisions}
        return all_got_revisions

    def getSourceStamps(self, absolute=False):
        sourcestamps = []
        if not absolute:
            if self.sources is not None:
                sourcestamps.extend(self.sources)
        else:
            all_got_revisions = self.getAllGotRevisions() or {}
            # always make a new instance
            for ss in self.sources:
                if ss.codebase in all_got_revisions:
                    got_revision = all_got_revisions[ss.codebase]
                    sourcestamps.append(ss.getAbsoluteSourceStamp(got_revision))
                else:
                    # No absolute revision information available
                    # Probably build has been stopped before ending all sourcesteps
                    # Return a clone with original revision
                    sourcestamps.append(ss.clone())
        return sourcestamps

    def updateSourceStamps(self):
        all_got_revisions = self.getAllGotRevisions() or {}
        # always make a new instance
        for ss in self.sources:
            if ss.codebase in all_got_revisions:
                ss.revision = all_got_revisions[ss.codebase]

    def getReason(self):
        return self.reason

    def getChanges(self):
        return self.changes

    def getRevisions(self):
        revs = []
        for c in self.changes:
            rev = str(c.revision)
            if rev > 7:  # for long hashes
                rev = rev[:7]
            revs.append(rev)
        return ", ".join(revs)

    def getResponsibleUsers(self):
        return self.blamelist

    def getInterestedUsers(self):
        # TODO: the Builder should add others: sheriffs, domain-owners
        return self.properties.getProperty('owners', [])

    def getSteps(self):
        """Return a list of IBuildStepStatus objects. For invariant builds
        (those which always use the same set of Steps), this should be the
        complete list, however some of the steps may not have started yet
        (step.getTimes()[0] will be None). For variant builds, this may not
        be complete (asking again later may give you more of them)."""
        return self.steps

    def getTimes(self):
        return (self.started, self.finished)

    _sentinel = [] # used as a sentinel to indicate unspecified initial_value
    def getSummaryStatistic(self, name, summary_fn, initial_value=_sentinel):
        """Summarize the named statistic over all steps in which it
        exists, using combination_fn and initial_value to combine multiple
        results into a single result.  This translates to a call to Python's
        X{reduce}::
            return reduce(summary_fn, step_stats_list, initial_value)
        """
        step_stats_list = [
                st.getStatistic(name)
                for st in self.steps
                if st.hasStatistic(name) ]
        if initial_value is self._sentinel:
            return reduce(summary_fn, step_stats_list)
        else:
            return reduce(summary_fn, step_stats_list, initial_value)

    def isResuming(self):
        return self.getResults() == RESUME and self.started is None

    def isFinished(self):
        return (self.finished is not None)

    def waitUntilFinished(self):
        if self.finished:
            d = defer.succeed(self)
        else:
            d = defer.Deferred()
            self.finishedWatchers.append(d)
        return d

    # while the build is running, the following methods make sense.
    # Afterwards they return None

    def getETA(self):
        if self.finished is not None:
            return None
        if not self.progress:
            return None
        eta = self.progress.eta()
        if eta is None:
            return None
        return eta - util.now()

    def getCurrentStep(self):
        return self.currentStep

    # Once you know the build has finished, the following methods are legal.
    # Before this build has finished, they all return None.

    def getText(self):
        text = []
        text.extend(self.text)
        for s in self.steps:
            text.extend(s.text2)
        return text

    def getResults(self):
        return self.results

    def getSlavename(self):
        return self.slavename

    def getTestResults(self):
        return self.testResults

    def getLogs(self):
        logs = []
        for s in self.steps:
            for loog in s.getLogs():
                logs.append(loog)
        return logs

    def getCustomUrls(self):
        """
        If the build is finished returns formated custom urls
        :return: Configured custom build urls in the format [{'name': name, 'url': ur}]
        """
        customUrls = []
        if self.isFinished():
            builderConfig = self.builder.getBuilderConfig()
            if builderConfig:
                customUrls = builderConfig.getCustomBuildUrls(
                        buildbotUrl=self.master.status.getBuildbotURL(),
                        buildNumber=self.number,
                        buildUrl=self.getBuildUrl()
                )
        return customUrls

    def getBuildUrl(self):
        return self.master.status.getURLForThing(self)['path'] if 'path' in self.master.status.getURLForThing(
            self) else ''

    def getTopBuildUrl(self, codebases_arg):
        d = self.master.db.buildrequests.getTopBuildData(self.buildChainID)

        def createTopBuildUrl(build_chain):
            buildername = build_chain['buildername']
            build_number = build_chain['build_number']

            if self.builder.name == buildername and self.number == build_number:
                return None

            build_path = self.master.status.getBuildersPath(buildername, build_number)

            return '{}{}'.format(urljoin('/', build_path), codebases_arg)

        def handleKeyError(failure):
            failure.trap(KeyError)

        d.addCallback(createTopBuildUrl)
        d.addErrback(handleKeyError)

        return d

    def hasMergedBuilds(self):
        return self.master.db.buildrequests.haveMergedBuildRequests(self.brids)

    # subscription interface

    def subscribe(self, receiver, updateInterval=None):
        # will receive stepStarted and stepFinished messages
        # and maybe buildETAUpdate
        self.watchers.append(receiver)
        if updateInterval is not None:
            self.sendETAUpdate(receiver, updateInterval)

    def sendETAUpdate(self, receiver, updateInterval):
        self.updates[receiver] = None
        ETA = self.getETA()
        if ETA is not None:
            receiver.buildETAUpdate(self, self.getETA())
        # they might have unsubscribed during buildETAUpdate
        if receiver in self.watchers:
            self.updates[receiver] = reactor.callLater(updateInterval,
                                                       self.sendETAUpdate,
                                                       receiver,
                                                       updateInterval)

    def unsubscribe(self, receiver):
        if receiver in self.watchers:
            self.watchers.remove(receiver)
        if receiver in self.updates:
            if self.updates[receiver] is not None:
                self.updates[receiver].cancel()
            del self.updates[receiver]

    # methods for the base.Build to invoke

    def getStepByName(self, name):
        for s in self.steps:
            if s.name == name:
                return s
        return None

    def addStepWithName(self, name, step_type, index=None):
        """The Build is setting up, and has added a new BuildStep to its
        list. Create a BuildStepStatus object to which it can send status
        updates."""

        s = BuildStepStatus(self, self.master, len(self.steps), step_type)
        s.setName(name)
        if index is None:
            self.steps.append(s)
        else:
            self.steps.insert(index, s)

        return s

    def addTestResult(self, result):
        self.testResults[result.getName()] = result

    def setSourceStamps(self, sourceStamps):
        self.sources = sourceStamps
        self.changes = []
        for source in self.sources:
            self.changes.extend(source.changes)

    def setSubmitted(self, submitted):
        self.submitted = submitted

    def setBuildChainID(self, buildChainID):
        self.buildChainID = buildChainID

    def setBuildRequestIDs(self, brids):
        self.brids = brids

    def updateBuildRequestIDs(self, brids):
        self.brids = [] if self.brids is None else self.brids
        for brid in brids:
            if brid not in self.brids:
                self.brids.append(brid)

    def setOwners(self, owners):
        self.owners = owners

    def setReason(self, reason):
        self.reason = reason

    def setBlamelist(self, blamelist):
        self.blamelist = blamelist
    def setProgress(self, progress):
        self.progress = progress

    def buildStarted(self, build):
        """The Build has been set up and is about to be started. It can now
        be safely queried, so it is time to announce the new build."""

        self.started = util.now()
        # now that we're ready to report status, let the BuilderStatus tell
        # the world about us
        self.builder.buildStarted(self)

    def setSlavename(self, slavename):
        self.slavename = slavename

    def setText(self, text):
        assert isinstance(text, (list, tuple))
        self.text = text

    def setResults(self, results):
        self.results = results

    def buildFinished(self):
        self.finished = util.now()

        if self.results == RESUME:
            build_data = {'start': self.started,
                          'finished': self.finished,
                          'startTime': time.ctime(self.started),
                          'finishedTime': time.ctime(self.finished),
                          'slavename': self.slavename,
                          'lastStepName': self.currentStep.name,
                          'lastStepNumber': self.currentStep.step_number+1,
                          'elapsed': util.formatInterval(self.finished - self.started),
                          'resumeSlavepool': self.resumeSlavepool}

            self.resume.append(build_data)
            self.setText(["Build Will Be Resumed"])
            self.finished = None
            self.started = None

        self.currentStep = None
        for r in self.updates.keys():
            if self.updates[r] is not None:
                self.updates[r].cancel()
                del self.updates[r]

        watchers = self.finishedWatchers
        self.finishedWatchers = []
        for w in watchers:
            w.callback(self)

    # methods called by our BuildStepStatus children

    def stepStarted(self, step):
        self.currentStep = step
        for w in self.watchers:
            receiver = w.stepStarted(self, step)
            if receiver:
                if type(receiver) == type(()):
                    step.subscribe(receiver[0], receiver[1])
                else:
                    step.subscribe(receiver)
                d = step.waitUntilFinished()
                d.addCallback(lambda step: step.unsubscribe(receiver))

        step.waitUntilFinished().addCallback(self._stepFinished)

    def _stepFinished(self, step):
        results = step.getResults()
        for w in self.watchers:
            w.stepFinished(self, step, results)

    # methods called by our BuilderStatus parent

    def pruneSteps(self):
        # this build is very old: remove the build steps too
        self.steps = []

    # persistence stuff

    def generateLogfileName(self, stepname, logname):
        """Return a filename (relative to the Builder's base directory) where
        the logfile's contents can be stored uniquely.

        The base filename is made by combining our build number, the Step's
        name, and the log's name, then removing unsuitable characters. The
        filename is then made unique by appending _0, _1, etc, until it does
        not collide with any other logfile.

        These files are kept in the Builder's basedir (rather than a
        per-Build subdirectory) because that makes cleanup easier: cron and
        find will help get rid of the old logs, but the empty directories are
        more of a hassle to remove."""

        starting_filename = "%d-log-%s-%s" % (self.number, stepname, logname)
        starting_filename = re.sub(r'[^\w\.\-]', '_', starting_filename)
        # now make it unique
        unique_counter = 0
        filename = starting_filename
        while filename in [l.filename
                           for step in self.steps
                           for l in step.getLogs()
                           if l.filename]:
            filename = "%s_%d" % (starting_filename, unique_counter)
            unique_counter += 1
        return filename

    def __getstate__(self):
        d = styles.Versioned.__getstate__(self)
        # for now, a serialized Build is always "finished". We will never
        # save unfinished builds.
        if not self.finished:
            d['finished'] = util.now()
            # TODO: push an "interrupted" step so it is clear that the build
            # was interrupted. The builder will have a 'shutdown' event, but
            # someone looking at just this build will be confused as to why
            # the last log is truncated.
        for k in [ 'builder', 'watchers', 'updates', 'finishedWatchers',
                   'master' ]:
            if k in d: del d[k]
        return d

    def __setstate__(self, d):
        styles.Versioned.__setstate__(self, d)
        self.watchers = []
        self.updates = {}
        self.finishedWatchers = []

    def setProcessObjects(self, builder, master):
        self.builder = builder
        self.master = master
        for step in self.steps:
            step.setProcessObjects(self, master)
    def upgradeToVersion1(self):
        if hasattr(self, "sourceStamp"):
            # the old .sourceStamp attribute wasn't actually very useful
            maxChangeNumber, patch = self.sourceStamp
            changes = getattr(self, 'changes', [])
            source = sourcestamp.SourceStamp(branch=None,
                                             revision=None,
                                             patch=patch,
                                             changes=changes)
            self.source = source
            self.changes = source.changes
            del self.sourceStamp
        self.wasUpgraded = True

    def upgradeToVersion2(self):
        self.properties = {}
        self.wasUpgraded = True

    def upgradeToVersion3(self):
        # in version 3, self.properties became a Properties object
        propdict = self.properties
        self.properties = properties.Properties()
        self.properties.update(propdict, "Upgrade from previous version")
        self.wasUpgraded = True

    def upgradeToVersion4(self):
        # buildstatus contains list of sourcestamps, convert single to list
        if hasattr(self, "source"):
            self.sources = [self.source]
            del self.source
        self.wasUpgraded = True
        
    def checkLogfiles(self):
        # check that all logfiles exist, and remove references to any that
        # have been deleted (e.g., by purge())
        for s in self.steps:
            s.checkLogfiles()

    def cancelYourself(self):
        self.results = CANCELED
        self.started = util.now() if self.started is None else self.started
        self.finished = util.now() if self.finished is None else self.finished
        self.setText(["Build Canceled"])
        self.buildFinished()
        self.saveYourself()

    def retryResume(self):
        failure = "Failed to resume build %s # %d while loading steps, will retry" % (self.builder.name, self.number)
        log.msg(failure)
        self.setResults(RETRY)
        self.finished = util.now()
        self.setText(["Failed to Resume, Will Retry"])
        self.buildFinished()
        self.saveYourself()
        raise RuntimeError(failure)

    @defer.inlineCallbacks
    def buildMerged(self, url):
        self.setResults(MERGED)
        self.finished = util.now()
        self.setText(["Build has been merged with: %s" % url['text']])
        yield threads.deferToThread(self.saveYourself)

    def saveYourself(self):
        filename = os.path.join(self.builder.basedir, "%d" % self.number)
        if os.path.isdir(filename):
            # leftover from 0.5.0, which stored builds in directories
            shutil.rmtree(filename, ignore_errors=True)
        tmpfilename = filename + ".tmp"

        try:
            with open(tmpfilename, "wb") as f:
                dump(self, f, -1)
            if runtime.platformType  == 'win32':
                # windows cannot rename a file on top of an existing one, so
                # fall back to delete-first. There are ways this can fail and
                # lose the builder's history, so we avoid using it in the
                # general (non-windows) case
                if os.path.exists(filename):
                    os.unlink(filename)

            os.rename(tmpfilename, filename)
        except:
            log.msg("unable to save build %s-#%d" % (self.builder.name,
                                                     self.number))
            log.err()

    def currentStepDict(self, dict):
        if self.getCurrentStep():
            dict['currentStep'] = self.getCurrentStep().asDict()

            step_type = self.getCurrentStep().getStepType()
            if step_type == str(AcquireBuildLocksType) or step_type == str(TriggerType):
                dict['isWaiting'] = True
        else:
            dict['currentStep'] = None

        return dict

    def get_failure_of_interest(self):
        if self.foi_url is not None:
            return self.foi_url

        build_result = self.getResults()
        if self.isFinished() and (build_result != SUCCESS and build_result != NOT_REBUILT):
            for s in self.getSteps():
                if s.isHidden():
                    continue

                r = s.getResults()[0]
                if r != SUCCESS and r != SKIPPED:
                    logs = s.getLogs()
                    if len(logs) > 0:
                        failure_log = next((l for l in logs if l.getName() == "TestReport.html"), None)
                        if failure_log is not None and s.getStatistic('passed', 0) == 0:
                            failure_log = None

                        log_types = ["stdio", "interrupt", "err.text"]
                        for t in log_types:
                            if failure_log is not None:
                                break
                            failure_log = next((l for l in logs if l.getName() == t), None)

                        if failure_log is not None:
                            self.foi_url = self.master.status.getURLForThing(failure_log)
                            return self.foi_url

        return None

    def get_artifacts(self):
        if self.artifacts is not None:
            return self.artifacts

        artifacts = {}
        for s in self.steps:
            if len(s.urls) > 0:
                for name, url in s.urls.iteritems():
                    if isinstance(url, basestring):
                        artifacts[name] = url

        if len(artifacts) > 0:
            # Only cache when we have completed the build and no futher artifacts
            # can be found
            if self.isFinished():
                self.artifacts = artifacts
            return self.artifacts

    def getBuildTags(self):
        build_tags = []
        builder = self.master.botmaster.builders.get(self.builder.name)
        if not builder:
            return build_tags
        config = builder.config
        if not config.build_tags:
            return build_tags
        for build_tag in config.build_tags:
            if callable(build_tag):
                build_tag = build_tag(self.properties)
            if not build_tag:
                continue
            if isinstance(build_tag, BuildTag):
                build_tags.append(build_tag.asDict())
        return build_tags

    def asBaseDict(self, request=None, include_current_step=False, include_artifacts=False, include_failure_url=False):
        from buildbot.status.web.base import getCodebasesArg

        result = {}
        sourcestamps = self.getSourceStamps()
        status = self.master.status
        args = getCodebasesArg(request, sourcestamps=sourcestamps)

        # Constant
        result['builderName'] = self.builder.name
        result['builderFriendlyName'] = self.builder.getFriendlyName()
        result['number'] = self.getNumber()
        result['reason'] = self.getReason()
        result['submittedTime'] = self.submitted
        result['owners'] = self.owners
        result['brids'] = self.brids
        result['buildChainID'] = self.buildChainID
        result['blame'] = self.getResponsibleUsers()
        result['url'] = status.getURLForThing(self)
        result['url']['path'] += args
        result['builder_url'] = status.getURLForThing(self.builder) + args
        result['builder_tags'] = self.builder.tags
        result['build_tags'] = self.getBuildTags()

        if self.resume:
            result['resume'] = self.resume

        if self.resumeSlavepool:
            result['resumeSlavepool'] = self.resumeSlavepool

        if include_failure_url:
            result['failure_url'] = self.get_failure_of_interest()
            if result['failure_url'] is not None:
                result['failure_url'] += args

        if include_artifacts:
            result['artifacts'] = self.get_artifacts()

        # Transient
        result['times'] = self.getTimes()
        result['text'] = self.getText()
        result['results'] = self.getResults()
        result['slave'] = self.getSlavename()
        slave = status.getSlave(self.getSlavename())
        if slave is not None:
            result['slave_friendly_name'] = slave.getFriendlyName()
            result['slave_url'] = status.getURLForThing(slave)
        result['eta'] = self.getETA()

        #Lazy importing here to avoid python import errors
        from buildbot.status.web.base import css_classes
        result['results_text'] = css_classes.get(result['results'], "")

        if include_current_step:
            result = self.currentStepDict(result)

        # Constant
        project = None
        for p, obj in status.getProjects().iteritems():
            if p == self.builder.project:
                project = obj
                break

        def getCodebaseObj(repo):
            for c in project.codebases:
                if c.values()[0]['repository'] == repo:
                    return c.values()[0]

        stamp_array = []
        for ss in sourcestamps:
            d = ss.asDict(status)
            c = getCodebaseObj(d['repository'])
            if c is not None and c.has_key("display_repository"):
                d['display_repository'] = c['display_repository']
            else:
                d['display_repository'] = d['repository']

            stamp_array.append(d)

        result['sourceStamps'] = stamp_array

        return result

    def asDict(self, request=None, include_artifacts=False, include_failure_url=False, include_steps=True,
               include_properties=True):
        from buildbot.status.web.base import getCodebasesArg
        result = self.asBaseDict(request, include_artifacts=include_artifacts, include_failure_url=include_failure_url)

        # TODO(maruel): Add.
        #result['test_results'] = self.getTestResults()
        args = getCodebasesArg(request)
        result['logs'] = [[l.getName(),
                           self.master.status.getURLForThing(l) + args] for l in self.getLogs()]

        result['isWaiting'] = False

        if include_steps:
            result['steps'] = [bss.asDict(request) for bss in self.steps]

        result = self.currentStepDict(result)

        # Transient
        if include_properties:
            result['properties'] = self.getProperties().asList()

        return result

components.registerAdapter(lambda build_status : build_status.properties,
        BuildStatus, interfaces.IProperties)
