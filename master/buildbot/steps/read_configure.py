import yaml

from buildbot.process import buildstep
from twisted.python import log

class ReadConfigure(buildstep.LoggingBuildStep):
    name = "readConfigure"

    description = None # set this to a list of short strings to override
    descriptionDone = None # alternate description when the step is complete
    descriptionSuffix = None # extra information to append to suffix
    flunkOnFailure = True

    def __init__(self, **kwargs):
        self.workdir = './build'
        buildstep.LoggingBuildStep.__init__(self, **kwargs)

    def start(self):
        warnings = []
        args = []
        log.msg("Start ReadConfigure")
        cmd = buildstep.RemoteCommand(
            self.name,
            args,
            collectStdout=True,
            collectStderr=True,
        )
        
        self.startCommand(cmd, warnings)

    def commandComplete(self, cmd):
        config = yaml.load(cmd.updates['config'][0])

        log.msg('CommandComplete', config['priority'])

