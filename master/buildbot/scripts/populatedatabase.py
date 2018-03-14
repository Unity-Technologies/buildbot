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

import names
from twisted.internet import defer

from buildbot.db import connector
from buildbot.master import BuildMaster
from buildbot.util import in_reactor
from buildbot import config as config_module


MAX_UNIQUE_USER_COUNT = 5494


@in_reactor
@defer.inlineCallbacks
def populate_database(config):
    master = BuildMaster(config['baseDir'])
    master.config = load_config(config, config['configFile'])
    db = connector.DBConnector(master, basedir=config['baseDir'])

    yield db.setup(check_version=False, verbose=not config['quiet'])
    yield populate_user(db, 100)
    yield populate_build(db)


def load_config(config, config_file_name='master.cfg'):
    if not config['quiet']:
        print("checking %s" % config_file_name)

    try:
        master_cfg = config_module.MasterConfig.loadConfig(
            config['baseDir'],
            config_file_name,
        )
    except config_module.ConfigErrors as e:
        print("Errors loading configuration:")
        for msg in e.errors:
            print("  " + msg)
        return
    except Exception:
        print("Errors loading configuration:")
        traceback.print_exc(file=sys.stdout)
        return

    return master_cfg


@defer.inlineCallbacks
def populate_user(db, user_count):
    if user_count > MAX_UNIQUE_USER_COUNT:
        raise ValueError("Can not generate more than %d unique user" % MAX_UNIQUE_USER_COUNT)

    users = []
    unique_identifier = set()
    for ind in range(user_count):
        # generate random identifier
        identifier = names.get_first_name()
        attempt = 0
        while identifier in unique_identifier:
            identifier = names.get_first_name()
            attempt += 1
            if attempt > user_count:
                raise RuntimeError("Can not find unique name. Please choose small amount of records")

        unique_identifier.add(identifier)
        user = {
            'identifier': identifier,
            'bb_username': identifier,
            'bb_password': 'pyflakes'
        }
        users.append(user)

    created, skipped = yield db.users.createUsers(users)
    print_summary('users', created, skipped)


def populate_build(db):
    print(db, 'start', 'build')


def end_populating(db):
    pass


def error_populate(err):
    print(err, 'error')


def print_summary(table, created, skipped):
    print("Created %d new %s, %d skipped" % (created, table, skipped))
