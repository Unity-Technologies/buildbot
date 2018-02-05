import os

from twisted.python import log
from buildslave.commands import base
from buildslave import runprocess


class ReadConfigure(base.Command):
    def __init__(self, *args, **kwargs):
        self.command = None # RunProcess instance
        base.Command.__init__(self, *args, **kwargs)
        
    def start(self):
        args = self.args
        workdir = os.path.join(self.builder.basedir)
        config_file = os.path.join(workdir, 'build', '.katana.yaml')
        if not os.path.exists(config_file):
            log.msg('configure file not found')
            return 

        config = None

        with open(config_file, 'r') as file_handle:
            config = file_handle.read()

        log.msg(config)

        self.sendStatus({'config': config})
        self.sendStatus({'rc': 0})
        self.builder.commandComplete(None)

    def interrupt(self):
        self.interrupted = True
        self.command.kill('command interrupted')
