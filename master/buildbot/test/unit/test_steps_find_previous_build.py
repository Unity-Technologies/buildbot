import mock
from twisted.trial import unittest
from buildbot.status import master
from buildbot.test.util import steps
from buildbot.steps import artifact
from buildbot.test.fake import fakemaster, fakedb
from buildbot.status.results import SUCCESS, SKIPPED
from buildbot.test.util import config
from buildbot.test.fake.remotecommand import ExpectShell

class FakeSourceStamp(object):

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def asDict(self, includePatch = True):
        return self.__dict__.copy()

    def getDict(self):
        return self.__dict__.copy()


class TestFindPreviousSuccessfulBuild(steps.BuildStepMixin, config.ConfigErrorsMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def setupStep(self, step, sourcestampsInBuild=None, force_rebuild=False, force_chain_rebuild=False,
                  configuredMergeFnResponse=True, *args, **kwargs):
        sourcestamps = sourcestampsInBuild or []
        got_revisions = {}

        steps.BuildStepMixin.setupStep(self, step, *args, **kwargs)

        m = fakemaster.make_master()
        self.build.builder.botmaster = m.botmaster
        m.db = fakedb.FakeDBConnector(self)
        m.status = master.Status(m)
        m.config.buildbotURL = "baseurl/"
        m.db.mastersconfig.setupMaster()

        if len(sourcestamps) < 1:
            ss = FakeSourceStamp(codebase='c',
                                 repository='https://url/project',
                                 branch='mybranch',
                                 revision=3,
                                 sourcestampsetid=3)
            sourcestamps.append(ss)

        def getAllSourceStamps():
            return sourcestamps
        self.build.getAllSourceStamps = getAllSourceStamps
        self.build.build_status.getSourceStamps = getAllSourceStamps
        if force_rebuild:
            self.build.setProperty("force_rebuild", True, "FindPreviousBuildTest")
        if force_chain_rebuild:
            self.build.setProperty("force_chain_rebuild", True, "FindPreviousBuildTest")

        def getAllGotRevisions():
            return got_revisions
        self.build.build_status.getAllGotRevisions = getAllGotRevisions

        def getSourceValues():
            return [mock.Mock()]
        buildRequest = mock.Mock()
        buildRequest.id = 1
        buildRequest.sources.values = getSourceValues
        self.build.requests = [
            buildRequest
        ]
        self.build.builder.config.name = "A"
        self.build.builder.config.builddir = "build"

        def getConfiguredMergeRequestsFn():
            return configuredMergeFnResponse
        self.build.builder.getConfiguredMergeRequestsFn = getConfiguredMergeRequestsFn

        self.build.builder.builder_status.getFriendlyName = lambda: "A"

        def addURL(name, url, results=None):
            self.step_status.urls[name] = url
            if results is not None:
                self.step_status.urls[name] = {'url': url, 'results': results}

        self.step_status.addURL = addURL

        fake_buildset = fakedb.Buildset(id=1, sourcestampsetid=1)
        fake_br = fakedb.BuildRequest(id=1, buildsetid=1, buildername="A", complete=1, results=0)
        fake_ss = fakedb.SourceStamp(id=1, branch='master', repository='https://url/project',
                                     codebase='c', revision='12', sourcestampsetid=1)
        fake_build = fakedb.Build(id=1, number=1, brid=1)

        m.db.insertTestData([fake_buildset, fake_br, fake_ss, fake_build])
        m.db.buildrequests.setRelatedSourcestamps(1, [FakeSourceStamp(codebase='c',
                                                              repository='https://url/project',
                                                              branch='master',
                                                              revision=12, sourcestampsetid=1)])

    # tests FindPreviousSuccessfulBuild

    def test_previous_build_not_invalid_ResumeSlavepoolParmeter(self):
        self.assertRaisesConfigError("resumeSlavepool='zzstartSlavenames', "
                                     "this parameter must be equals to 'startSlavenames' or 'slavenames'",
                                     lambda: artifact.FindPreviousSuccessfulBuild(resumeSlavepool="zzstartSlavenames"))

    def test_previous_build_valid_ResumeSlavepoolParmeter(self):
        self.setupStep(artifact.FindPreviousSuccessfulBuild(resumeSlavepool='startSlavenames'))
        self.expectOutcome(result=SUCCESS, status_text=['Running build (previous sucessful build not found).'])
        return self.runStep()

    def test_previous_build_not_found(self):
        self.setupStep(artifact.FindPreviousSuccessfulBuild())
        self.expectOutcome(result=SUCCESS, status_text=['Running build (previous sucessful build not found).'])
        return self.runStep()

    # check build url
    def test_previous_build_found(self):
        self.setupStep(artifact.FindPreviousSuccessfulBuild(),
                       sourcestampsInBuild = [FakeSourceStamp(codebase='c',
                                                              repository='https://url/project',
                                                              branch='master',
                                                              revision=12, sourcestampsetid=2)])


        self.expectOutcome(result=SUCCESS, status_text=['Found previous successful build.'])
        self.expectURLS({'A #1': 'baseurl/builders/A/builds/1?c_branch=master'})
        return self.runStep()

    def test_previous_build_exists_when_merge_function_is_false_then_previous_success_build_is_not_found(self):
        self.setupStep(artifact.FindPreviousSuccessfulBuild(),
                       sourcestampsInBuild = [FakeSourceStamp(codebase='c',
                                                              repository='https://url/project',
                                                              branch='master',
                                                              revision=12, sourcestampsetid=2)],
                       configuredMergeFnResponse=False)

        self.expectOutcome(result=SKIPPED, status_text=['Skipping previous build check (configured to unmergeable).'])
        return self.runStep()

    def test_previous_build_exists_when_merge_function_returns_false_then_previous_success_build_is_not_found(self):
        def cannotMerge(builder, req1, req2):
            return False
        self.setupStep(artifact.FindPreviousSuccessfulBuild(),
                       sourcestampsInBuild = [FakeSourceStamp(codebase='c',
                                                              repository='https://url/project',
                                                              branch='master',
                                                              revision=12, sourcestampsetid=2)],
                       configuredMergeFnResponse=cannotMerge)

        self.expectOutcome(result=SUCCESS, status_text=['Running build (previous sucessful build not found).'])
        return self.runStep()

    def test_previous_build_exists_when_merge_function_returns_true_then_previous_success_build_is_found(self):
        def canMerge(builder, req1, req2):
            return True
        self.setupStep(artifact.FindPreviousSuccessfulBuild(),
                       sourcestampsInBuild = [FakeSourceStamp(codebase='c',
                                                              repository='https://url/project',
                                                              branch='master',
                                                              revision=12, sourcestampsetid=2)],
                       configuredMergeFnResponse=canMerge)

        self.expectOutcome(result=SUCCESS, status_text=['Found previous successful build.'])
        self.expectURLS({'A #1': 'baseurl/builders/A/builds/1?c_branch=master'})
        return self.runStep()

    def test_previous_build_exists_when_is_mergin_with_previous_is_true_then_then_previous_success_build_is_found(self):
        def isMergingWithPrevious(builder, req1, req2):
            return req1.isMergingWithPrevious and req2.isMergingWithPrevious
        self.setupStep(artifact.FindPreviousSuccessfulBuild(),
                       sourcestampsInBuild = [FakeSourceStamp(codebase='c',
                                                              repository='https://url/project',
                                                              branch='master',
                                                              revision=12, sourcestampsetid=2)],
                       configuredMergeFnResponse=isMergingWithPrevious)

        self.expectOutcome(result=SUCCESS, status_text=['Found previous successful build.'])
        self.expectURLS({'A #1': 'baseurl/builders/A/builds/1?c_branch=master'})
        return self.runStep()

    def test_force_rebuild(self):
        self.setupStep(artifact.FindPreviousSuccessfulBuild(),
                       sourcestampsInBuild = [FakeSourceStamp(codebase='c',
                                                              repository='https://url/project',
                                                              branch='master',
                                                              revision=12, sourcestampsetid=2)], force_rebuild=True)

        self.expectOutcome(result=SKIPPED, status_text=['Skipping previous build check (forcing a rebuild).'])
        return self.runStep()


    def test_force_chain_rebuild(self):
        self.setupStep(artifact.FindPreviousSuccessfulBuild(),
                       sourcestampsInBuild = [FakeSourceStamp(codebase='c',
                                                              repository='https://url/project',
                                                              branch='master',
                                                              revision=12, sourcestampsetid=2)],
                       force_chain_rebuild=True)

        self.expectOutcome(result=SKIPPED, status_text=['Skipping previous build check (forcing a rebuild).'])
        return self.runStep()

    # tests CheckArtifactExists

    def test_checkartifact_previous_build_not_found(self):
        self.setupStep(artifact.CheckArtifactExists(artifact="myartifact.py", artifactDirectory="artifact",
                                        artifactServer='usr@srv.com', artifactServerDir='/home/srv/web/dir',
                                        artifactServerURL="http://srv.com/dir"))
        self.expectOutcome(result=SUCCESS, status_text=["Artifact not found."])
        return self.runStep()

    def test_checkartifact_force_rebuild(self):
        self.setupStep(artifact.CheckArtifactExists(artifact="myartifact.py", artifactDirectory="artifact",
                                        artifactServer='usr@srv.com', artifactServerDir='/home/srv/web/dir',
                                        artifactServerURL="http://srv.com/dir"),
                       sourcestampsInBuild = [FakeSourceStamp(codebase='c',
                                                              repository='https://url/project',
                                                              branch='master',
                                                              revision=12, sourcestampsetid=2)], force_rebuild=True)

        self.expectOutcome(result=SKIPPED, status_text=['Skipping artifact check (forcing a rebuild).'])
        return self.runStep()

    def test_checkartifact_when_merge_function_is_false_then_unable_to_merge(self):
        self.setupStep(artifact.CheckArtifactExists(artifact="myartifact.py", artifactDirectory="artifact",
                                        artifactServer='usr@srv.com', artifactServerDir='/home/srv/web/dir',
                                        artifactServerURL="http://srv.com/dir"),
                       sourcestampsInBuild = [FakeSourceStamp(codebase='c',
                                                              repository='https://url/project',
                                                              branch='master',
                                                              revision=12, sourcestampsetid=2)],
                        configuredMergeFnResponse=False)

        self.expectOutcome(result=SKIPPED, status_text=['Skipping artifact check (configured to unmergeable).'])
        return self.runStep()


    def test_force_chain_rebuild(self):
        self.setupStep(artifact.CheckArtifactExists(artifact="myartifact.py", artifactDirectory="artifact",
                                        artifactServer='usr@srv.com', artifactServerDir='/home/srv/web/dir',
                                        artifactServerURL="http://srv.com/dir"),
                       sourcestampsInBuild = [FakeSourceStamp(codebase='c',
                                                              repository='https://url/project',
                                                              branch='master',
                                                              revision=12, sourcestampsetid=2)],
                       force_chain_rebuild=True)

        self.expectOutcome(result=SKIPPED, status_text=['Skipping artifact check (forcing a rebuild).'])
        return self.runStep()

    def test_checkartifact_build_found_artifact_not_in_srv(self):
        self.setupStep(artifact.CheckArtifactExists(artifact="myartifact.py", artifactDirectory="artifact",
                                        artifactServer='usr@srv.com', artifactServerDir='/home/srv/web/dir',
                                        artifactServerURL="http://srv.com/dir"),
                       sourcestampsInBuild = [FakeSourceStamp(codebase='c',
                                                              repository='https://url/project',
                                                              branch='master',
                                                              revision=12, sourcestampsetid=2)])

        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command= ['ssh',
              'usr@srv.com',
              'cd /home/srv/web/dir;',
              "if [ -d build/1_01_01_1970_00_00_00_+0000/artifact ]; then echo 'Exists'; else echo 'Not found!!'; fi;",
              'cd build/1_01_01_1970_00_00_00_+0000/artifact',
              '; ls myartifact.py',
              '; ls'])
            + ExpectShell.log('stdio', stdout='Not found!!')
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=['Artifact not found on server http://srv.com/dir.'])
        return self.runStep()


    def test_checkartifact_build_found_artifact_not_in_dir(self):
        self.setupStep(artifact.CheckArtifactExists(artifact="myartifact.py", artifactDirectory="artifact",
                                        artifactServer='usr@srv.com', artifactServerDir='/home/srv/web/dir',
                                        artifactServerURL="http://srv.com/dir"),
                       sourcestampsInBuild = [FakeSourceStamp(codebase='c',
                                                              repository='https://url/project',
                                                              branch='master',
                                                              revision=12, sourcestampsetid=2)])

        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command= ['ssh',
              'usr@srv.com',
              'cd /home/srv/web/dir;',
              "if [ -d build/1_01_01_1970_00_00_00_+0000/artifact ]; then echo 'Exists'; else echo 'Not found!!'; fi;",
              'cd build/1_01_01_1970_00_00_00_+0000/artifact',
              '; ls myartifact.py',
              '; ls'])
            + ExpectShell.log('stdio', stdout='')
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=['Artifact not found on server http://srv.com/dir.'])
        return self.runStep()

    def test_checkartifact_build_found_artifact_found(self):
        self.setupStep(artifact.CheckArtifactExists(artifact="myartifact.py", artifactDirectory="artifact",
                                        artifactServer='usr@srv.com', artifactServerDir='/home/srv/web/dir',
                                        artifactServerURL="http://srv.com/dir"),
                       sourcestampsInBuild = [FakeSourceStamp(codebase='c',
                                                              repository='https://url/project',
                                                              branch='master',
                                                              revision=12, sourcestampsetid=2)])

        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command= ['ssh',
              'usr@srv.com',
              'cd /home/srv/web/dir;',
              "if [ -d build/1_01_01_1970_00_00_00_+0000/artifact ]; then echo 'Exists'; else echo 'Not found!!'; fi;",
              'cd build/1_01_01_1970_00_00_00_+0000/artifact',
              '; ls myartifact.py',
              '; ls'])
            + ExpectShell.log('stdio', stdout='myartifact.py')
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=['Searching complete.'])
        return self.runStep()

    def test_checkartifact_when_build_found_artifact_exists_and_merge_function_returns_true_then_artifact_found(self):
        def canMerge(builder, req1, req2):
            return True
        self.setupStep(artifact.CheckArtifactExists(artifact="myartifact.py", artifactDirectory="artifact",
                                        artifactServer='usr@srv.com', artifactServerDir='/home/srv/web/dir',
                                        artifactServerURL="http://srv.com/dir"),
                       sourcestampsInBuild = [FakeSourceStamp(codebase='c',
                                                              repository='https://url/project',
                                                              branch='master',
                                                              revision=12, sourcestampsetid=2)],
                       configuredMergeFnResponse=canMerge)

        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command= ['ssh',
              'usr@srv.com',
              'cd /home/srv/web/dir;',
              "if [ -d build/1_01_01_1970_00_00_00_+0000/artifact ]; then echo 'Exists'; else echo 'Not found!!'; fi;",
              'cd build/1_01_01_1970_00_00_00_+0000/artifact',
              '; ls myartifact.py',
              '; ls'])
            + ExpectShell.log('stdio', stdout='myartifact.py')
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=['Searching complete.'])
        return self.runStep()

    def test_checkartifact_when_build_found_artifact_exists_and_merge_function_returns_false_then_artifact_not_found(self):
        def cannotMerge(builder, req1, req2):
            return False
        self.setupStep(artifact.CheckArtifactExists(artifact="myartifact.py", artifactDirectory="artifact",
                                        artifactServer='usr@srv.com', artifactServerDir='/home/srv/web/dir',
                                        artifactServerURL="http://srv.com/dir"),
                       sourcestampsInBuild = [FakeSourceStamp(codebase='c',
                                                              repository='https://url/project',
                                                              branch='master',
                                                              revision=12, sourcestampsetid=2)],
                       configuredMergeFnResponse=cannotMerge)
        self.expectOutcome(result=SUCCESS, status_text=['Artifact not found.'])
        return self.runStep()

    def test_checkartifact_when_is_mergin_with_previous_is_true_then_artifact_found(self):
        def isMergingWithPrevious(builder, req1, req2):
            return req1.isMergingWithPrevious and req2.isMergingWithPrevious
        self.setupStep(artifact.CheckArtifactExists(artifact="myartifact.py", artifactDirectory="artifact",
                                        artifactServer='usr@srv.com', artifactServerDir='/home/srv/web/dir',
                                        artifactServerURL="http://srv.com/dir"),
                       sourcestampsInBuild = [FakeSourceStamp(codebase='c',
                                                              repository='https://url/project',
                                                              branch='master',
                                                              revision=12, sourcestampsetid=2)],
                       configuredMergeFnResponse=isMergingWithPrevious)
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command= ['ssh',
              'usr@srv.com',
              'cd /home/srv/web/dir;',
              "if [ -d build/1_01_01_1970_00_00_00_+0000/artifact ]; then echo 'Exists'; else echo 'Not found!!'; fi;",
              'cd build/1_01_01_1970_00_00_00_+0000/artifact',
              '; ls myartifact.py',
              '; ls'])
            + ExpectShell.log('stdio', stdout='myartifact.py')
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=['Searching complete.'])
        return self.runStep()
