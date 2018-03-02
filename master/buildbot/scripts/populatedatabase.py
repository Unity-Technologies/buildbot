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
import sys
import traceback

from twisted.internet import defer, reactor

from buildbot.db import connector
from buildbot.master import BuildMaster
from buildbot.util import in_reactor
from buildbot import config as config_module


@in_reactor
def populateDatabase(config):
    master = BuildMaster(config['baseDir'])
    master.config = loadConfig(config, config['configFile'])
    db = connector.DBConnector(master, basedir=config['baseDir'])

    deferDb = db.setup(check_version=False, verbose=not config['quiet'])
    deferDb.addCallback(lambda x: populateUser(db, 1000))
    deferDb.addCallback(lambda x: populateBuild(db))
    deferDb.addCallback(endPopulating)
    deferDb.addErrback(errorPopulate)


def loadConfig(config, configFileName='master.cfg'):
    if not config['quiet']:
        print "checking %s" % configFileName

    try:
        master_cfg = config_module.MasterConfig.loadConfig(
            config['baseDir'],
            configFileName,
        )
    except config_module.ConfigErrors, e:
        print "Errors loading configuration:"
        for msg in e.errors:
            print "  " + msg
        return
    except:
        print "Errors loading configuration:"
        traceback.print_exc(file=sys.stdout)
        return

    return master_cfg

@defer.inlineCallbacks
def populateUser(db, userCount):
    users = []
    for ind in xrange(userCount):
        user = dict(
            identifier='ABC',
            bb_username='',
            bb_password='pyflakes'
        )
    yield db.users.createBulkUser(users)


def populateBuild(db):
    print db, 'start', 'build'


def endPopulating(db):
    pass


def errorPopulate(err):
    print err, 'error'
    reactor.kill()