from buildbot.steps.slave import CompositeStepMixin

from buildbot.process.buildstep import LoggingBuildStep, SUCCESS, SKIPPED, FAILURE
from twisted.internet import defer
from buildbot.steps.shell import ShellCommand
import re
from buildbot.util import epoch2datetime
from buildbot.util import safeTranslate
from buildbot.process import properties
from buildbot.process.slavebuilder import IDLE, BUILDING
from buildbot.process.buildrequest import BuildRequest
from buildbot.steps.resumebuild import ResumeBuild, ShellCommandResumeBuild
from twisted.python import log
import ntpath

# Change artifact location in August
# datetime.datetime(2017, 7, 31, 23, 59, 59, tzinfo=UTC)
ARTIFACT_LOCATION_CHANGE_DATE = epoch2datetime(1501545599)

def FormatDatetime(value):
    return value.strftime("%d_%m_%Y_%H_%M_%S_%z")

def mkdt(epoch):
    if epoch:
        return epoch2datetime(epoch)

def getBuildSourceStamps(build, build_sourcestamps):
    # every build will generate at least one sourcestamp
    sourcestamps = build.build_status.getSourceStamps()

    # when running rebuild or passing revision as parameter
    for ss in sourcestamps:
        build_sourcestamps.append(
            {'b_codebase': ss.codebase, 'b_revision': ss.revision, 'b_branch': ss.branch,
             'b_sourcestampsetid': ss.sourcestampsetid})

def forceRebuild(build):
    force_rebuild = build.getProperty("force_rebuild", False)
    if type(force_rebuild) != bool:
        force_rebuild = (force_rebuild.lower() == "true")

    force_chain_rebuild = build.getProperty("force_chain_rebuild", False)
    if type(force_chain_rebuild) != bool:
        force_chain_rebuild = (force_chain_rebuild.lower() == "true")

    return force_chain_rebuild or force_rebuild

class PreviousBuildStatus:
    Forced = 1
    Unmergeable = 2
    NotFound = 3
    Found = 4

class FindPreviousSuccessBuildMixin():
    disableUnmergeable = False

    @defer.inlineCallbacks
    def _determinePreviousBuild(self, master, build, build_sourcestamps):
        if forceRebuild(build):
            defer.returnValue((PreviousBuildStatus.Forced, None))

        mergeRequestFn = build.builder.getConfiguredMergeRequestsFn()

        if mergeRequestFn == False and not self.disableUnmergeable:
            log.msg("[brid: %d] is forced - skipping previous build" % build.requests[0].id)
            defer.returnValue((PreviousBuildStatus.Unmergeable, None))

        elif mergeRequestFn == True or mergeRequestFn == False: # Default case, with no merge function assigned
            log.msg("[brid: %d] is searching for previous successful build without merge function" % build.requests[0].id)
            prevBuildRequest = yield master.db.buildrequests \
                .getBuildRequestBySourcestamps(buildername=build.builder.config.name,
                                               sourcestamps=build_sourcestamps)
            if prevBuildRequest:
                log.msg("[brid: %d] previous successful build [%s] found" % (build.requests[0].id, prevBuildRequest['brid']))
                defer.returnValue((PreviousBuildStatus.Found, prevBuildRequest))

        else: # Custom merge function assigned
            log.msg("[brid: %d] is searching for previous successful build with merge function" % build.requests[0].id)
            prevBuildRequests = yield master.db.buildrequests \
                .getBuildRequestsBySourcestamps(buildername=build.builder.config.name,
                                                sourcestamps = build_sourcestamps)
            if len(prevBuildRequests) > 0:
                req1 = build.requests[0]
                buildSetIds = list(set([br['buildsetid'] for br in prevBuildRequests]))
                buildSets = yield master.db.buildsets.getBuildsetsByIds(buildSetIds)
                buildSetsProperties = yield master.db.buildsets.getBuildsetsProperties(buildSetIds)
                for prevBuildRequest in prevBuildRequests:
                    req2 = self._getBuildRequest(master, prevBuildRequest, buildSets, buildSetsProperties, req1.sources)
                    req1.isMergingWithPrevious = req2.isMergingWithPrevious = True
                    try:
                        if (mergeRequestFn(build.builder, req1, req2)):
                            log.msg("[brid: %d] previous successful build [%s] found with matching properties" % (build.requests[0].id, prevBuildRequest['brid']))
                            defer.returnValue((PreviousBuildStatus.Found, prevBuildRequest))
                    finally:
                        req1.isMergingWithPrevious = req2.isMergingWithPrevious = False
                log.msg("[brid: %d] found %d previous successful builds , but merge function did not match" % (build.requests[0].id, len(prevBuildRequests)))

        log.msg("[brid: %d] found no previous successful builds" % build.requests[0].id)
        defer.returnValue((PreviousBuildStatus.NotFound, None))

    def _updateMergedBuildRequests(self, master, build):
        if len(build.requests) > 1:
            yield master.db.buildrequests.updateMergedBuildRequest(build.requests)

    # A more light weight function for making a build request, it expects that the information needed
    # has already been fetched
    def _getBuildRequest(self, master, brdict, buildSets, buildSetsProperties, sources):
        buildSetId = brdict['buildsetid']

        assert buildSetId in buildSets  # schema should guarantee this
        buildset = buildSets[buildSetId]

        # fetch the buildset properties, and convert to Properties
        buildSetProperties = {}
        if buildSetId in buildSetsProperties:
            buildSetProperties = buildSetsProperties[buildSetId]
        props = properties.Properties.fromDict(buildSetProperties)

        return BuildRequest.makeBuildRequest(master, brdict, buildset, props, sources)

class FindPreviousSuccessfulBuild(ResumeBuild, FindPreviousSuccessBuildMixin):
    name = "Find Previous Successful Build"
    description="Searching for a previous successful build at the appropriate revision(s)..."
    descriptionDone="Searching complete."

    def __init__(self, **kwargs):
        self.build_sourcestamps = []
        self.master = None
        ResumeBuild.__init__(self, **kwargs)

    @defer.inlineCallbacks
    def start(self):
        if self.master is None:
            self.master = self.build.builder.botmaster.parent

        yield getBuildSourceStamps(self.build, self.build_sourcestamps)

        (previousBuildRequestStatus, prevBuildRequest) = yield self._determinePreviousBuild(self.master, self.build, self.build_sourcestamps)
        if previousBuildRequestStatus == PreviousBuildStatus.Found:
            yield self._previousBuildFound(prevBuildRequest)
        elif previousBuildRequestStatus == PreviousBuildStatus.Forced:
            self._updateMergedBuildRequests(self.master, self.build)
            self.step_status.setText(["Skipping previous build check (forcing a rebuild)."])
            self.finished(SKIPPED)
        elif previousBuildRequestStatus == PreviousBuildStatus.Unmergeable:
            self._updateMergedBuildRequests(self.master, self.build)
            self.step_status.setText(["Skipping previous build check (configured to unmergeable)."])
            self.finished(SKIPPED)
        else:
            self._updateMergedBuildRequests(self.master, self.build)
            self.step_status.setText(["Running build (previous sucessful build not found)."])
            self.finished(SUCCESS)

    @defer.inlineCallbacks
    def _previousBuildFound(self, prevBuildRequest):
        build_list = yield self.master.db.builds.getBuildsForRequest(prevBuildRequest['brid'])
        # there can be many builds per buildrequest for example (retry) when slave lost connection
        # in this case we will display all the builds related to this build request

        for build in build_list:
            build_num = build['number']
            friendly_name = self.build.builder.builder_status.getFriendlyName()
            url = yield self.master.status.getURLForBuildRequest(prevBuildRequest['brid'],
                                                                 self.build.builder.config.name, build_num,
                                                                 friendly_name, self.build_sourcestamps)
            self.addURL(url['text'], url['path'])
        # we are not building but reusing a previous build
        reuse = yield self.master.db.buildrequests.reusePreviousBuild(self.build.requests, prevBuildRequest['brid'])
        self.step_status.setText(["Found previous successful build."])
        self.step_status.stepFinished(SUCCESS)
        self.build.result = SUCCESS
        self.build.setProperty("reusedOldBuild", True)
        self.build.allStepsDone()
        self.resumeBuild = False
        self.finished(SUCCESS)
        return


class CheckArtifactExists(ShellCommandResumeBuild, FindPreviousSuccessBuildMixin):
    name = "Check if Artifact Exists"
    description="Checking if artifacts exist from a previous build at the appropriate revision(s)..."
    descriptionDone="Searching complete."

    def __init__(self, artifact=None, artifactDirectory=None, artifactServer=None, artifactServerDir=None,
                 artifactServerURL=None, artifactServerPort=None, stopBuild=True, resumeBuild=None, **kwargs):
        self.master = None
        self.build_sourcestamps = []
        if not isinstance(artifact, list):
            artifact = [artifact]
        self.artifact = artifact
        self.artifactDirectory = artifactDirectory
        self.artifactServer = artifactServer
        self.artifactServerDir = artifactServerDir
        self.artifactServerURL = artifactServerURL
        self.artifactServerPort = artifactServerPort
        self.artifactBuildrequest = None
        self.artifactPath = None
        self.artifactURL = None
        self.stopBuild = stopBuild
        resume_build_val = stopBuild if resumeBuild is None else resumeBuild
        ShellCommandResumeBuild.__init__(self, resumeBuild=resume_build_val, **kwargs)

    @defer.inlineCallbacks
    def createSummary(self, log):
        artifactlist = list(self.artifact)
        stdio = self.getLog('stdio').readlines()
        notfoundregex = re.compile(r'Not found!!')
        for l in stdio:
            m = notfoundregex.search(l)
            if m:
                break
            if len(artifactlist) == 0:
                break
            for a in artifactlist:
                artifact = a
                if artifact.endswith("/"):
                    artifact = artifact[:-1]
                foundregex = re.compile(r'(%s)' % artifact)
                m = foundregex.search(l)
                if (m):
                    artifactURL = self.artifactServerURL + "/" + self.artifactPath + "/" + a
                    self.addURL(a, artifactURL)
                    artifactlist.remove(a)

        if len(artifactlist) == 0:
            artifactsfound = self.build.getProperty("artifactsfound", True)

            if not artifactsfound:
                return

            self.build.setProperty("artifactsfound", True, "CheckArtifactExists %s" % self.artifact)
            self.build.setProperty("reusedOldBuild", True)
            self.resumeBuild = False

            if self.stopBuild:
                # update buildrequest (artifactbrid) with self.artifactBuildrequest
                reuse = yield self.master.db.buildrequests.reusePreviousBuild(self.build.requests,
                                                                              self.artifactBuildrequest['brid'])
                self.step_status.stepFinished(SUCCESS)
                self.build.result = SUCCESS
                self.build.allStepsDone()
        else:
            self.build.setProperty("artifactsfound", False, "CheckArtifactExists %s" % self.artifact)
            self.descriptionDone = ["Artifact not found on server %s." % self.artifactServerURL]
            # update merged buildrequest to reuse artifact generated by current buildrequest
            if len(self.build.requests) > 1:
                yield self.master.db.buildrequests.updateMergedBuildRequest(self.build.requests)

    @defer.inlineCallbacks
    def start(self):
        if self.master is None:
            self.master = self.build.builder.botmaster.parent

        yield getBuildSourceStamps(self.build, self.build_sourcestamps)

        (previousBuildRequestStatus, prevBuildRequest) = yield self._determinePreviousBuild(self.master, self.build, self.build_sourcestamps)
        if previousBuildRequestStatus == PreviousBuildStatus.Found:
            log.msg("[brid %d] is searching for matching artifacts" % self.build.requests[0].id)
            yield self._previousBuildFound(prevBuildRequest)
        elif previousBuildRequestStatus == PreviousBuildStatus.Forced:
            self._updateMergedBuildRequests(self.master, self.build)
            self.step_status.setText(["Skipping artifact check (forcing a rebuild)."])
            self.finished(SKIPPED)
        elif previousBuildRequestStatus == PreviousBuildStatus.Unmergeable:
            self._updateMergedBuildRequests(self.master, self.build)
            self.step_status.setText(["Skipping artifact check (configured to unmergeable)."])
            self.finished(SKIPPED)
        else:
            self._updateMergedBuildRequests(self.master, self.build)
            self.step_status.setText(["Artifact not found."])
            self.finished(SUCCESS)

    def _previousBuildFound(self, prevBuildRequest):
        self.artifactBuildrequest = prevBuildRequest
        self.step_status.setText(["Artifact has been already generated."])

        if self.artifactBuildrequest["submitted_at"] > ARTIFACT_LOCATION_CHANGE_DATE:
            self.artifactPath = "%s/%s_%s" % (self.build.builder.config.builddir,
                                              self.artifactBuildrequest['brid'],
                                              FormatDatetime(self.artifactBuildrequest['submitted_at']))
        else:
            self.artifactPath = "%s_%s_%s" % (self.build.builder.config.builddir,
                                              self.artifactBuildrequest['brid'],
                                              FormatDatetime(self.artifactBuildrequest['submitted_at']))

        if self.artifactDirectory:
            self.artifactPath += "/%s" % self.artifactDirectory

        search_artifact = ""
        for a in self.artifact:
            if a.endswith("/"):
                a = a[:-1]
                if "/" in a:
                    index = a.rfind("/")
                    a = a[:index] + "/*"
            search_artifact += "; ls %s" % a

        command = ["ssh", self.artifactServer]
        if self.artifactServerPort:
            command += ["-p %s" % self.artifactServerPort]
        command += ["cd %s;" % self.artifactServerDir,
                    "if [ -d %s ]; then echo 'Exists'; else echo 'Not found!!'; fi;" % self.artifactPath,
                    "cd %s" % self.artifactPath, search_artifact, "; ls"]
        # ssh to the server to check if it artifact is there
        self.setCommand(command)
        ShellCommandResumeBuild.start(self)

class CreateArtifactDirectory(ShellCommand):

    name = "Create Remote Artifact Directory"
    description="Creating the artifact directory on the remote artifacts server..."
    descriptionDone="Remote artifact directory created."

    def __init__(self,  artifactDirectory=None, artifactServer=None, artifactServerDir=None, artifactServerPort=None,
                 customArtifactPathRef=None, **kwargs):
        self.artifactDirectory = artifactDirectory
        self.artifactServer = artifactServer
        self.artifactServerDir = artifactServerDir
        self.artifactServerPort = artifactServerPort
        self.customArtifactPathRef = customArtifactPathRef
        ShellCommand.__init__(self, **kwargs)

    def start(self):
        br = self.build.requests[0]
        if callable(self.customArtifactPathRef):
            artifactPath = self.customArtifactPathRef(self.build)
        elif mkdt(br.submittedAt) > ARTIFACT_LOCATION_CHANGE_DATE:
            artifactPath  = "%s/%s_%s" % (self.build.builder.config.builddir,
                                          br.id, FormatDatetime(mkdt(br.submittedAt)))
        else:
            artifactPath  = "%s_%s_%s" % (self.build.builder.config.builddir,
                                          br.id, FormatDatetime(mkdt(br.submittedAt)))

        if (self.artifactDirectory):
            artifactPath += "/%s" % self.artifactDirectory


        command = ["ssh", self.artifactServer]
        if self.artifactServerPort:
            command += ["-p %s" % self.artifactServerPort]
        command += ["cd %s;" % self.artifactServerDir, "mkdir -p ",
                    artifactPath]

        self.setCommand(command)
        ShellCommand.start(self)


def checkWindowsSlaveEnvironment(step, key):
    return key in step.build.slavebuilder.slave.slave_environ.keys() \
           and step.build.slavebuilder.slave.slave_environ[key] == 'Windows_NT'


def _isWindowsSlave(step):
        slave_os = step.build.slavebuilder.slave.os and step.build.slavebuilder.slave.os == 'Windows'
        slave_env = checkWindowsSlaveEnvironment(step, 'os') or checkWindowsSlaveEnvironment(step, 'OS')
        return slave_os or slave_env


def retryCommandLinuxOS(command):
    return 'for i in 1 2 3 4 5; do ' + command + '; if [ $? -eq 0 ]; then exit 0; else sleep 5; fi; done; exit -1'


def retryCommandWindowsOS(command):
    return 'for /L %%i in (1,1,5) do (sleep 5 & ' + command + ' && exit 0)'

def retryCommandWindowsOSPwShell(command):
    return 'powershell.exe -C for ($i=1; $i -le  5; $i++) { '+ command \
           +'; if ($?) { exit 0 } else { sleep 5} } exit -1'

def rsyncWithRetry(step, origin, destination, port=None):

    rsync_command = "rsync -var --progress --partial '%s' '%s'" % (origin, destination)
    if port:
        rsync_command += " --rsh='ssh -p %s'" % port
    if _isWindowsSlave(step):
        if step.usePowerShell:
            return retryCommandWindowsOSPwShell(rsync_command)
        return retryCommandWindowsOS(rsync_command)

    return retryCommandLinuxOS(rsync_command)

def mkDir(step, dir):
    if _isWindowsSlave(step):
        return ['mkdir', ntpath.normpath(dir) ]
    else:
        return ['mkdir', '-p', dir]


def getRemoteLocation(artifactServer, artifactServerDir, artifactPath, artifact):
    return artifactServer + ":" + artifactServerDir + "/" + artifactPath + "/" + artifact.replace(" ", r"\ ")

class UploadArtifact(ShellCommand):

    name = "Upload Artifact(s)"
    description="Uploading artifact(s) to remote artifact server..."
    descriptionDone="Artifact(s) uploaded."

    def __init__(self, artifact=None, artifactDirectory=None, artifactServer=None, artifactServerDir=None,
                 artifactServerURL=None, artifactServerPort=None, usePowerShell=True,
                 customArtifactPathRef=None, **kwargs):
        self.artifact=artifact
        self.artifactURL = None
        self.artifactDirectory = artifactDirectory
        self.artifactServer = artifactServer
        self.artifactServerDir = artifactServerDir
        self.artifactServerURL = artifactServerURL
        self.artifactServerPort = artifactServerPort
        self.usePowerShell = usePowerShell
        self.customArtifactPathRef = customArtifactPathRef
        ShellCommand.__init__(self, **kwargs)

    @defer.inlineCallbacks
    def start(self):
        br = self.build.requests[0]

        # this means that we are merging build requests with this one
        if len(self.build.requests) > 1:
            master = self.build.builder.botmaster.parent
            reuse = yield master.db.buildrequests.updateMergedBuildRequest(self.build.requests)

        if callable(self.customArtifactPathRef):
            artifactPath = self.customArtifactPathRef(self.build)
        elif mkdt(br.submittedAt) > ARTIFACT_LOCATION_CHANGE_DATE:
            artifactPath  = "%s/%s_%s" % (self.build.builder.config.builddir, br.id, FormatDatetime(mkdt(br.submittedAt)))
        else:
            artifactPath = "%s_%s_%s" % (self.build.builder.config.builddir, br.id, FormatDatetime(mkdt(br.submittedAt)))

        artifactServerPath = self.build.getProperty("artifactServerPath", None)
        if artifactServerPath is None:
            self.build.setProperty("artifactServerPath", self.artifactServerURL + "/" + artifactPath, "UploadArtifact")

        if (self.artifactDirectory):
            artifactPath += "/%s" % self.artifactDirectory

        remotelocation = getRemoteLocation(self.artifactServer, self.artifactServerDir, artifactPath, self.artifact)

        command = rsyncWithRetry(self, self.artifact, remotelocation, self.artifactServerPort)

        self.artifactURL = self.artifactServerURL + "/" + artifactPath + "/" + self.artifact
        self.setCommand(command)
        ShellCommand.start(self)

    def finished(self, results):
        if results == SUCCESS:
            self.addURL(self.artifact, self.artifactURL)
        ShellCommand.finished(self, results)


class DownloadArtifact(ShellCommand):
    name = "Download Artifact(s)"
    description="Downloading artifact(s) from the remote artifacts server..."
    descriptionDone="Artifact(s) downloaded."

    def __init__(self, artifactBuilderName=None, artifact=None, artifactDirectory=None, artifactDestination=None,
                 artifactServer=None, artifactServerDir=None, artifactServerPort=None, usePowerShell=True,
                 customArtifactPathRef=None, **kwargs):
        self.artifactBuilderName = artifactBuilderName
        self.artifact = artifact
        self.artifactDirectory = artifactDirectory
        self.artifactServer = artifactServer
        self.artifactServerDir = artifactServerDir
        self.artifactServerPort = artifactServerPort
        self.artifactDestination = artifactDestination or artifact
        self.master = None
        self.usePowerShell = usePowerShell
        self.customArtifactPathRef = customArtifactPathRef
        name = "Download Artifact for '%s'" % artifactBuilderName
        description = "Downloading artifact '%s'..." % artifactBuilderName
        descriptionDone="Downloaded '%s'." % artifactBuilderName
        ShellCommand.__init__(self, name=name, description=description, descriptionDone=descriptionDone,  **kwargs)


    @defer.inlineCallbacks
    def start(self):
        if self.master is None:
            self.master = self.build.builder.botmaster.parent

        #find artifact dependency
        br = yield self._getBuildRequest()

        if callable(self.customArtifactPathRef):
            artifactPath = self.customArtifactPathRef(self.build)
        elif br["submitted_at"] > ARTIFACT_LOCATION_CHANGE_DATE:
            artifactPath  = "%s/%s_%s" % (safeTranslate(self.artifactBuilderName),
                                          br['brid'], FormatDatetime(br["submitted_at"]))
        else:
            artifactPath  = "%s_%s_%s" % (safeTranslate(self.artifactBuilderName),
                                          br['brid'], FormatDatetime(br["submitted_at"]))

        if (self.artifactDirectory):
            artifactPath += "/%s" % self.artifactDirectory

        remotelocation = getRemoteLocation(self.artifactServer, self.artifactServerDir, artifactPath, self.artifact)

        command = rsyncWithRetry(self, remotelocation, self.artifactDestination, self.artifactServerPort)

        self.setCommand(command)
        ShellCommand.start(self)

    @defer.inlineCallbacks
    def _getBuildRequest(self):
        triggeredbybrid = self.build.requests[0].id
        br = yield self.master.db.buildrequests.getBuildRequestTriggered(triggeredbybrid, self.artifactBuilderName)
        defer.returnValue(br)


class DownloadArtifactsFromChildren(LoggingBuildStep, CompositeStepMixin):
    name = "Download Artifact(s) from triggered builds"
    description="Downloading artifact(s) from triggered builds..."
    descriptionDone="Downloaded artifact(s) from triggered builds"

    def __init__(self,
                 artifactServer,
                 artifactServerDir,
                 artifactBuilderName,
                 workdir='',
                 artifactServerPort=None,
                 artifactDestination=None,
                 artifactDirectory=None,
                 artifact=None,
                 usePowerShell=True,
                 **kwargs):
        self.workdir = workdir
        self.artifact = artifact
        self.artifactBuilderName = artifactBuilderName
        self.artifactDirectory = artifactDirectory
        self.artifactServer = artifactServer
        self.artifactServerDir = artifactServerDir
        self.artifactServerPort = artifactServerPort
        self.artifactDestination = artifactDestination
        self.master = None
        self.usePowerShell = usePowerShell
        LoggingBuildStep.__init__(self, **kwargs)

    @defer.inlineCallbacks
    def start(self):
        if self.master is None:
            self.master = self.build.builder.botmaster.parent

        self._setUpLogs()

        partitionRequests = yield self.master.db.buildrequests.getBuildRequestsTriggeredBy(self.build.requests[0].id, self.artifactBuilderName)
        buildRequetsIdsWithArtifacts = self._getBuildRequestIdsWithArtifacts(partitionRequests)
        self.partitionCount = len(buildRequetsIdsWithArtifacts)
        self.step_status.setText(["Downloading artifacts from %d triggered partitions" % self.partitionCount])
        artifactsMap = {}
        self.build.setProperty("artifactsMap", {})
        for brid in buildRequetsIdsWithArtifacts:
            buildRequest = yield self.master.db.buildrequests.getBuildRequestById(brid)

            localdir = self._getLocalDir(brid)
            command = mkDir(self, localdir)
            yield self._docmd(command)

            artifactPath = self._getArtifactPath(buildRequest)
            remotelocation = self._getRemoteLocation(artifactPath)

            rsync = rsyncWithRetry(self, remotelocation, localdir, self.artifactServerPort)
            yield self._docmd(rsync)

            if self.artifact:
                artifactsMap[localdir] = artifactPath + '/' + self.artifact
            else:
                artifactsMap[localdir] = artifactPath + '/'

        self.build.setProperty('artifactsMap', artifactsMap, 'DownloadArtifactsFromChildren')
        self.finished(SUCCESS)

    def finished(self, results):
        if results == SUCCESS:
            self.step_status.setText(["Downloaded artifacts from %s partitions" % self.partitionCount])
        LoggingBuildStep.finished(self, results)

    def _setUpLogs(self):
        self.stdio_log = self.addLogForRemoteCommands("stdio")
        self.stdio_log.setTimestampsMode(self.timestamp_stdio)

    def _getLocalDir(self, brid):
        localdir = str(brid)
        if self.artifactDestination:
            localdir = self.artifactDestination + '/' + localdir
        return localdir

    def _getArtifactPath(self, buildRequest):
        artifactPath = "%s/%s_%s" % (
            safeTranslate(self.artifactBuilderName),
            buildRequest['brid'],
            FormatDatetime(buildRequest["submitted_at"])
        )
        if self.artifactDirectory:
            artifactPath += "/%s" % self.artifactDirectory
        return artifactPath

    def _getRemoteLocation(self,  artifactPath):
        if (self.artifact):
            return getRemoteLocation(self.artifactServer, self.artifactServerDir, artifactPath, self.artifact)
        else:
            return getRemoteLocation(self.artifactServer, self.artifactServerDir, artifactPath, "")

    def _docmd(self, command):
        if not command:
            raise ValueError("No command specified")
        from buildbot.process import buildstep
        cmd = buildstep.RemoteShellCommand(self.workdir,
                command, collectStdout=False,
                collectStderr=True)
        cmd.useLog(self.stdio_log, False)
        d = self.runCommand(cmd)
        def evaluateCommand(cmd):
            if cmd.didFail():
                raise buildstep.BuildStepFailed()

            return cmd.rc
        d.addCallback(lambda _: evaluateCommand(cmd))
        return d

    @staticmethod
    def _getBuildRequestIdsWithArtifacts(buildrequests):
        ids = []
        for br in buildrequests:
            artifactbrid = br['artifactbrid']
            if artifactbrid == None:
                ids.append(br['brid'])
            else:
                ids.append(artifactbrid)
        return sorted(set(ids))

class AcquireBuildLocks(LoggingBuildStep):
    name = "Acquire Build Slave"
    description="Acquiring build slave..."
    descriptionDone="Build slave acquired."

    def __init__(self, hideStepIf = True, locks=None, **kwargs):
        LoggingBuildStep.__init__(self, hideStepIf = hideStepIf, locks=locks, **kwargs)

    def start(self):
        self.step_status.setText(["Acquiring build slave to complete build."])
        self.build.locks = self.locks

        if self.build.slavebuilder.state == IDLE:
            self.build.slavebuilder.state = BUILDING

        if self.build.builder.builder_status.currentBigState == "idle":
            self.build.builder.builder_status.setBigState("building")

        self.build.releaseLockInstance = self
        self.finished(SUCCESS)
        return

    def releaseLocks(self):
        return


class ReleaseBuildLocks(LoggingBuildStep):
    name = "Release Builder Locks"
    description="Releasing builder locks..."
    descriptionDone="Build locks released."

    def __init__(self, hideStepIf=True, **kwargs):
        self.releaseLockInstance = None
        LoggingBuildStep.__init__(self, hideStepIf=hideStepIf, **kwargs)

    def start(self):
        self.step_status.setText(["Releasing build locks."])
        self.locks = self.build.locks
        self.releaseLockInstance = self.build.releaseLockInstance
        # release slave lock
        self.build.slavebuilder.state = IDLE
        self.build.builder.builder_status.setBigState("idle")
        self.finished(SUCCESS)
        # notify that the slave may now be available to start a build.
        self.build.builder.botmaster.maybeStartBuildsForSlave(self.buildslave.slavename)
        return
