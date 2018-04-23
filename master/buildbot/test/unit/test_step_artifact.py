from twisted.trial import unittest
from buildbot.test.util import steps

from buildbot.steps import artifact
from buildbot.status.results import SUCCESS
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.fake import fakemaster, fakedb


class TestArtifactSteps(steps.BuildStepMixin, unittest.TestCase):
    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def setupStep(self, step, brqs=None, winslave=False):
        steps.BuildStepMixin.setupStep(self, step)

        self.remote = '\'usr@srv.com:/home/srv/web/dir/build/1_17_12_2014_13_31_26_+0000/mydir/myartifact.py\''
        self.remote_2 = '\'usr@srv.com:/home/srv/web/dir/B/2_01_01_1970_00_00_00_+0000/mydir/myartifact.py\''
        self.remote_custom = '\'usr@srv.com:/home/srv/web/dir/foobar/mydir/myartifact.py\''
        self.local = '\'myartifact.py\''

        fake_br = fakedb.BuildRequest(id=1, buildsetid=1, buildername="A", complete=1, results=0)
        fake_br.submittedAt = 1418823086
        self.build.requests = [fake_br]
        self.build.builder.config.builddir = "build"

        m = fakemaster.make_master()
        self.build.builder.botmaster = m.botmaster
        m.db = fakedb.FakeDBConnector(self)

        breqs = [fake_br]
        if brqs:
            breqs += brqs

        self.build.slavebuilder.slave.slave_environ = {}

        if winslave:
            self.build.slavebuilder.slave.slave_environ['os'] = 'Windows_NT'

        m.db.insertTestData(breqs)

    def test_create_artifact_directory(self):
        self.setupStep(artifact.CreateArtifactDirectory(artifactDirectory="mydir",
                                                        artifactServer='usr@srv.com',
                                                        artifactServerDir='/home/srv/web/dir'))
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command=['ssh', 'usr@srv.com', 'cd /home/srv/web/dir;', 'mkdir -p ',
                                 'build/1_17_12_2014_13_31_26_+0000/mydir'])
            + ExpectShell.log('stdio', stdout='')
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=['Remote artifact directory created.'])
        return self.runStep()

    def test_create_artifact_directory_with_port(self):
        self.setupStep(artifact.CreateArtifactDirectory(artifactDirectory="mydir",
                                                        artifactServer='usr@srv.com',
                                                        artifactServerDir='/home/srv/web/dir',
                                                        artifactServerPort=222))
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command=['ssh', 'usr@srv.com', '-p 222', 'cd /home/srv/web/dir;', 'mkdir -p ',
                                 'build/1_17_12_2014_13_31_26_+0000/mydir'])
            + ExpectShell.log('stdio', stdout='')
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=['Remote artifact directory created.'])
        return self.runStep()

    def test_create_artifact_directory_with_customArtifactPath(self):
        self.setupStep(artifact.CreateArtifactDirectory(artifactDirectory="mydir",
                                                        artifactServer='usr@srv.com',
                                                        artifactServerDir='/home/srv/web/dir',
                                                        artifactServerPort=222,
                                                        customArtifactPath='foobar'))
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command=['ssh', 'usr@srv.com', '-p 222', 'cd /home/srv/web/dir;',
                                 'mkdir -p ',
                                 'foobar/mydir'])
            + ExpectShell.log('stdio', stdout='')
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=['Remote artifact directory created.'])
        return self.runStep()

    def test_upload_artifact(self):
        self.setupStep(artifact.UploadArtifact(artifact="myartifact.py", artifactDirectory="mydir",
                                               artifactServer='usr@srv.com', artifactServerDir='/home/srv/web/dir',
                                               artifactServerURL="http://srv.com/dir"))
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command='for i in 1 2 3 4 5; do rsync -var --progress --partial ' +
                                self.local + ' ' + self.remote +
                                '; if [ $? -eq 0 ]; then exit 0; else sleep 5; fi; done; exit -1')
            + ExpectShell.log('stdio', stdout='')
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=['Artifact(s) uploaded.'])
        self.expectProperty('artifactServerPath',
                            'http://srv.com/dir/build/1_17_12_2014_13_31_26_+0000',
                            'UploadArtifact')
        return self.runStep()

    def test_upload_artifact_with_port(self):
        self.setupStep(artifact.UploadArtifact(artifact="myartifact.py", artifactDirectory="mydir",
                                               artifactServer='usr@srv.com', artifactServerDir='/home/srv/web/dir',
                                               artifactServerPort=222,
                                               artifactServerURL="http://srv.com/dir"))
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command='for i in 1 2 3 4 5; do rsync -var --progress --partial ' +
                                self.local + ' ' + self.remote +
                                ' --rsh=\'ssh -p 222\'; if [ $? -eq 0 ]; then exit 0; else sleep 5; fi; done; exit -1')
            + ExpectShell.log('stdio', stdout='')
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=['Artifact(s) uploaded.'])
        self.expectProperty('artifactServerPath',
                            'http://srv.com/dir/build/1_17_12_2014_13_31_26_+0000',
                            'UploadArtifact')
        return self.runStep()

    def test_upload_artifact_with_customArtifactPath(self):
        self.setupStep(artifact.UploadArtifact(artifact="myartifact.py", artifactDirectory="mydir",
                                               artifactServer='usr@srv.com',
                                               artifactServerDir='/home/srv/web/dir',
                                               artifactServerURL="http://srv.com/dir",
                                               customArtifactPath="foobar"))
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command='for i in 1 2 3 4 5; do rsync -var --progress --partial ' +
                                self.local + ' ' + self.remote_custom +
                                '; if [ $? -eq 0 ]; then exit 0; else sleep 5; fi; done; exit -1')
            + ExpectShell.log('stdio', stdout='')
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=['Artifact(s) uploaded.'])
        self.expectProperty('artifactServerPath',
                            'http://srv.com/dir/foobar',
                            'UploadArtifact')
        return self.runStep()

    def test_upload_artifact_Win_DOS(self):
        self.setupStep(artifact.UploadArtifact(artifact="myartifact.py", artifactDirectory="mydir",
                                               artifactServer='usr@srv.com', artifactServerDir='/home/srv/web/dir',
                                               artifactServerURL="http://srv.com/dir", usePowerShell=False),
                       winslave=True)

        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command='for /L %%i in (1,1,5) do (sleep 5 & rsync -var --progress --partial ' +
                                self.local + ' ' + self.remote +
                                ' && exit 0)')
            + ExpectShell.log('stdio', stdout='')
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=['Artifact(s) uploaded.'])
        return self.runStep()

    def test_upload_artifact_Win_DOS_with_port(self):
        self.setupStep(artifact.UploadArtifact(artifact="myartifact.py", artifactDirectory="mydir",
                                               artifactServer='usr@srv.com', artifactServerDir='/home/srv/web/dir',
                                               artifactServerPort=222,
                                               artifactServerURL="http://srv.com/dir", usePowerShell=False),
                       winslave=True)

        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command='for /L %%i in (1,1,5) do (sleep 5 & rsync -var --progress --partial ' +
                                self.local + ' ' + self.remote +
                                ' --rsh=\'ssh -p 222\' && exit 0)')
            + ExpectShell.log('stdio', stdout='')
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=['Artifact(s) uploaded.'])
        return self.runStep()

    def test_upload_artifact_Win(self):
        self.setupStep(artifact.UploadArtifact(artifact="myartifact.py", artifactDirectory="mydir",
                                               artifactServer='usr@srv.com', artifactServerDir='/home/srv/web/dir',
                                               artifactServerURL="http://srv.com/dir"), winslave=True)

        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command='powershell.exe -C for ($i=1; $i -le  5; $i++) ' +
                                '{ rsync -var --progress --partial ' + self.local + ' ' + self.remote +
                                '; if ($?) { exit 0 } else { sleep 5} } exit -1')
            + ExpectShell.log('stdio', stdout='')
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=['Artifact(s) uploaded.'])
        return self.runStep()

    def test_upload_artifact_Win_with_port(self):
        self.setupStep(artifact.UploadArtifact(artifact="myartifact.py", artifactDirectory="mydir",
                                               artifactServer='usr@srv.com', artifactServerDir='/home/srv/web/dir',
                                               artifactServerPort=222,
                                               artifactServerURL="http://srv.com/dir"), winslave=True)

        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command='powershell.exe -C for ($i=1; $i -le  5; $i++) ' +
                                '{ rsync -var --progress --partial ' + self.local + ' ' + self.remote +
                                ' --rsh=\'ssh -p 222\'; if ($?) { exit 0 } else { sleep 5} } exit -1')
            + ExpectShell.log('stdio', stdout='')
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=['Artifact(s) uploaded.'])
        return self.runStep()

    def test_download_artifact(self):
        fake_trigger = fakedb.BuildRequest(id=2, buildsetid=2, buildername="B", complete=1,
                                           results=0, triggeredbybrid=1, startbrid=1)
        self.setupStep(artifact.DownloadArtifact(artifactBuilderName="B", artifact="myartifact.py",
                                                 artifactDirectory="mydir",
                                                 artifactServer='usr@srv.com',
                                                 artifactServerDir='/home/srv/web/dir'), [fake_trigger])

        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command='for i in 1 2 3 4 5; do rsync -var --progress --partial ' +
                                self.remote_2 + ' ' + self.local +
                                '; if [ $? -eq 0 ]; then exit 0; else sleep 5; fi; done; exit -1')
            + ExpectShell.log('stdio', stdout='')
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=["Downloaded 'B'."])
        return self.runStep()

    def test_download_artifact_with_port(self):
        fake_trigger = fakedb.BuildRequest(id=2, buildsetid=2, buildername="B", complete=1,
                                           results=0, triggeredbybrid=1, startbrid=1)
        self.setupStep(artifact.DownloadArtifact(artifactBuilderName="B", artifact="myartifact.py",
                                                 artifactDirectory="mydir",
                                                 artifactServer='usr@srv.com',
                                                 artifactServerPort=222,
                                                 artifactServerDir='/home/srv/web/dir'), [fake_trigger])

        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command='for i in 1 2 3 4 5; do rsync -var --progress --partial ' +
                                self.remote_2 + ' ' + self.local +
                                ' --rsh=\'ssh -p 222\'; if [ $? -eq 0 ]; then exit 0; else sleep 5; fi; done; exit -1')
            + ExpectShell.log('stdio', stdout='')
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=["Downloaded 'B'."])
        return self.runStep()

    def test_download_artifact_with_customArtifactPath(self):
        fake_trigger = fakedb.BuildRequest(id=2, buildsetid=2, buildername="B", complete=1,
                                           results=0, triggeredbybrid=1, startbrid=1)
        self.setupStep(artifact.DownloadArtifact(artifactBuilderName="B", artifact="myartifact.py",
                                                 artifactDirectory="mydir",
                                                 artifactServer='usr@srv.com',
                                                 artifactServerDir='/home/srv/web/dir',
                                                 customArtifactPath='foobar'),
                       [fake_trigger])

        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command='for i in 1 2 3 4 5; do rsync -var --progress --partial ' +
                                self.remote_custom + ' ' + self.local +
                                '; if [ $? -eq 0 ]; then exit 0; else sleep 5; fi; done; exit -1')
            + ExpectShell.log('stdio', stdout='')
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=["Downloaded 'B'."])
        return self.runStep()


    def test_download_artifact_Win_DOS(self):
        fake_trigger = fakedb.BuildRequest(id=2, buildsetid=2, buildername="B", complete=1,
                                           results=0, triggeredbybrid=1, startbrid=1)
        self.setupStep(artifact.DownloadArtifact(artifactBuilderName="B", artifact="myartifact.py",
                                                 artifactDirectory="mydir",
                                                 artifactServer='usr@srv.com',
                                                 artifactServerDir='/home/srv/web/dir', usePowerShell=False),
                       [fake_trigger], winslave=True)

        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command='for /L %%i in (1,1,5) do (sleep 5 & rsync -var --progress --partial ' +
                                self.remote_2 + ' ' + self.local + ' && exit 0)')
            + ExpectShell.log('stdio', stdout='')
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=["Downloaded 'B'."])
        return self.runStep()

    def test_download_artifact_Win_DOS_with_port(self):
        fake_trigger = fakedb.BuildRequest(id=2, buildsetid=2, buildername="B", complete=1,
                                           results=0, triggeredbybrid=1, startbrid=1)
        self.setupStep(artifact.DownloadArtifact(artifactBuilderName="B", artifact="myartifact.py",
                                                 artifactDirectory="mydir",
                                                 artifactServer='usr@srv.com',
                                                 artifactServerPort=222,
                                                 artifactServerDir='/home/srv/web/dir', usePowerShell=False),
                       [fake_trigger], winslave=True)

        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command='for /L %%i in (1,1,5) do (sleep 5 & rsync -var --progress --partial ' +
                                self.remote_2 + ' ' + self.local + ' --rsh=\'ssh -p 222\' && exit 0)')
            + ExpectShell.log('stdio', stdout='')
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=["Downloaded 'B'."])
        return self.runStep()

    def test_download_artifact_Win(self):
        fake_trigger = fakedb.BuildRequest(id=2, buildsetid=2, buildername="B", complete=1,
                                           results=0, triggeredbybrid=1, startbrid=1)
        self.setupStep(artifact.DownloadArtifact(artifactBuilderName="B", artifact="myartifact.py",
                                                 artifactDirectory="mydir",
                                                 artifactServer='usr@srv.com',
                                                 artifactServerDir='/home/srv/web/dir'), [fake_trigger], winslave=True)

        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command='powershell.exe -C for ($i=1; $i -le  5; $i++) ' +
                                '{ rsync -var --progress --partial ' +
                                self.remote_2 + ' ' +
                                self.local + '; if ($?) { exit 0 } else { sleep 5} } exit -1')
            + ExpectShell.log('stdio', stdout='')
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=["Downloaded 'B'."])
        return self.runStep()

    def test_download_artifact_Win_with_port(self):
        fake_trigger = fakedb.BuildRequest(id=2, buildsetid=2, buildername="B", complete=1,
                                           results=0, triggeredbybrid=1, startbrid=1)
        self.setupStep(artifact.DownloadArtifact(artifactBuilderName="B", artifact="myartifact.py",
                                                 artifactDirectory="mydir",
                                                 artifactServer='usr@srv.com',
                                                 artifactServerPort=222,
                                                 artifactServerDir='/home/srv/web/dir'), [fake_trigger], winslave=True)

        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command='powershell.exe -C for ($i=1; $i -le  5; $i++) ' +
                                '{ rsync -var --progress --partial ' +
                                self.remote_2 + ' ' +
                                self.local + ' --rsh=\'ssh -p 222\'; if ($?) { exit 0 } else { sleep 5} } exit -1')
            + ExpectShell.log('stdio', stdout='')
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=["Downloaded 'B'."])
        return self.runStep()

    def test_download_artifact_reusing_build(self):
        fake_br2 = fakedb.BuildRequest(id=2, buildsetid=2, buildername="B", complete=1,
                                       results=0, triggeredbybrid=0, startbrid=0)
        fake_trigger = fakedb.BuildRequest(id=3, buildsetid=3, buildername="B", complete=1,
                                           results=0, triggeredbybrid=1, startbrid=1, artifactbrid=2)
        self.setupStep(artifact.DownloadArtifact(artifactBuilderName="B", artifact="myartifact.py",
                                                 artifactDirectory="mydir",
                                                 artifactServer='usr@srv.com',
                                                 artifactServerDir='/home/srv/web/dir'), [fake_br2, fake_trigger])
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command='for i in 1 2 3 4 5; do rsync -var --progress --partial ' +
                                self.remote_2 + ' ' +
                                self.local + '; if [ $? -eq 0 ]; then exit 0; else sleep 5; fi; done; exit -1')
            + ExpectShell.log('stdio', stdout='')
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=["Downloaded 'B'."])
        return self.runStep()

    def test_download_artifact_fromchildren_reusing_artifacts(self):
        # In this test we expect DownloadArtifactsFromChildren to download artifacts from following build request ids:
        # '2' because `artifactbrid` is null which means that build request contains artifacts on itself
        # '666' - because build request '3' reused it
        # The test data also include and build request '4', referring '666'.
        # The test also checks that it will not be downloaded.
        # We don't want to download the same artifact more than once
        br2 = fakedb.BuildRequest(id=2, buildsetid=2, buildername="B", triggeredbybrid=1, artifactbrid=None)
        br3 = fakedb.BuildRequest(id=3, buildsetid=3, buildername="B", triggeredbybrid=1, artifactbrid=666)
        br4 = fakedb.BuildRequest(id=4, buildsetid=4, buildername="B", triggeredbybrid=1, artifactbrid=666)
        br666 = fakedb.BuildRequest(id=666, buildsetid=5, buildername="B", triggeredbybrid=None)

        self.setupStep(
            artifact.DownloadArtifactsFromChildren(
                workdir='build',
                artifactServer='usr@srv.com',
                artifactServerDir='/artifacts',
                artifactServerPort=22,
                artifactDirectory='mydir',
                artifactBuilderName='B',
                artifactDestination='./base/local',
        ), [br2, br3, br4, br666])

        expectedRemote1 = '\'usr@srv.com:/artifacts/B/2_01_01_1970_00_00_00_+0000/mydir/\''
        expectedRemote2 = '\'usr@srv.com:/artifacts/B/666_01_01_1970_00_00_00_+0000/mydir/\''

        expectedLocal1 = './base/local/2'
        expectedLocal2 = './base/local/666'

        self.expectCommands(
            ExpectShell(workdir='build', usePTY='slave-config',
                        command=['mkdir', '-p', expectedLocal1]) +
            0,
            ExpectShell(workdir='build', usePTY='slave-config',
                        command='for i in 1 2 3 4 5; do rsync -var --progress --partial ' +
                                expectedRemote1 + " '" + expectedLocal1 + "'"
                                ' --rsh=\'ssh -p 22\'; if [ $? -eq 0 ]; then exit 0; else sleep 5; fi; done; exit -1'
                        ) +
            0,
            ExpectShell(workdir='build', usePTY='slave-config',
                        command=['mkdir', '-p', expectedLocal2]) +
            0,
            ExpectShell(workdir='build', usePTY='slave-config',
                        command='for i in 1 2 3 4 5; do rsync -var --progress --partial ' +
                                expectedRemote2 + " '" + expectedLocal2 + "'" +
                                ' --rsh=\'ssh -p 22\'; if [ $? -eq 0 ]; then exit 0; else sleep 5; fi; done; exit -1'
                        ) +
            0 +
            ExpectShell.log('stdio', stdout='')
        )

        self.expectOutcome(result=SUCCESS, status_text=['Downloaded artifacts from 2 partitions'])
        return self.runStep()

    def test_download_artifact_fromchildren_windows(self):
        br2 = fakedb.BuildRequest(id=2, buildsetid=2, buildername="B", triggeredbybrid=1)

        self.setupStep(
            artifact.DownloadArtifactsFromChildren(
                workdir='build',
                artifactServer='usr@srv.com',
                artifactServerDir='/artifacts',
                artifactServerPort=22,
                artifactDirectory='mydir',
                artifactBuilderName='B',
                artifactDestination='./base/local'
        ), [br2], winslave=True)

        expectedRemote = '\'usr@srv.com:/artifacts/B/2_01_01_1970_00_00_00_+0000/mydir/\''
        expectedLocal = './base/local/2'
        expectedLocalMkDirPath = r'base\local\2'

        self.expectCommands(
            ExpectShell(workdir='build', usePTY='slave-config',
                        command=['mkdir', expectedLocalMkDirPath]) +
            0,
            ExpectShell(workdir='build', usePTY='slave-config',
                        command='powershell.exe -C for ($i=1; $i -le  5; $i++) { rsync -var --progress --partial ' +
                                expectedRemote + " '" + expectedLocal + "'" +
                                ' --rsh=\'ssh -p 22\'; if ($?) { exit 0 } else { sleep 5} } exit -1'
                        ) +
            0 +
            ExpectShell.log('stdio', stdout='')
        )

        self.expectOutcome(result=SUCCESS,  status_text=['Downloaded artifacts from 1 partitions'])
        return self.runStep()

    def test_download_artifact_fromchildren_defaultparams(self):
        br2 = fakedb.BuildRequest(id=2, buildsetid=2, buildername="B", triggeredbybrid=1)

        self.setupStep(
            artifact.DownloadArtifactsFromChildren(
                workdir='build',
                artifactServer='usr@srv.com',
                artifactServerDir='/artifacts',
                artifactServerPort=22,
                artifactBuilderName='B',
        ), [br2])

        expectedRemote = '\'usr@srv.com:/artifacts/B/2_01_01_1970_00_00_00_+0000/\''
        expectedLocal = '2'

        self.expectCommands(
            ExpectShell(workdir='build', usePTY='slave-config',
                        command=['mkdir', '-p', expectedLocal]) + 0,
            ExpectShell(workdir='build', usePTY='slave-config',
                        command='for i in 1 2 3 4 5; do rsync -var --progress --partial ' +
                                expectedRemote +  " '" + expectedLocal + "'" +
                                ' --rsh=\'ssh -p 22\'; if [ $? -eq 0 ]; then exit 0; else sleep 5; fi; done; exit -1'
                        ) +
            0 +
            ExpectShell.log('stdio', stdout='')
        )

        self.expectOutcome(result=SUCCESS, status_text=['Downloaded artifacts from 1 partitions'])
        return self.runStep()