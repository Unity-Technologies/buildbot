# -*- coding: utf-8 -*-
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
from __future__ import print_function

import random
import sys
import traceback

import datetime
import names
from twisted.internet import defer

from buildbot import config as config_module
from buildbot.db import connector
from buildbot.master import BuildMaster
from buildbot.util import in_reactor
from buildbot.util import datetime2epoch
from buildbot.status import results

MAX_UNIQUE_USER_COUNT = 5494


@in_reactor
@defer.inlineCallbacks
def populate_database(config):
    master = BuildMaster(config['baseDir'])
    master.config = load_config(config, config['configFile'])
    db = connector.DBConnector(master, basedir=config['baseDir'])

    yield db.setup(check_version=False, verbose=not config['quiet'])
    users = yield populate_user(db, 100)
    yield populate_build(db, 50000, master.config.builders, master.config.projects, users)


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
    """
    This function create `user_count` number of random user in database
    :param db: a handler to the DBConnection object
    :param user_count: an integer value with number of new users
    """
    print("Starting creating users")
    if user_count > MAX_UNIQUE_USER_COUNT:
        raise ValueError("Can not generate more than %d unique user" % MAX_UNIQUE_USER_COUNT)

    users = []
    created = 0
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
        result = yield db.users.createUser(user)
        if result:
            created += 1
        users.append(user)

        print_progress_bar(ind+1, user_count)

    print("Created %d new users, %d skipped" % (created, user_count - created))
    defer.returnValue(map(lambda x: x['identifier'], users))


@defer.inlineCallbacks
def populate_build(db, build_count, builders_list, projects, user_names):
    """

    :param db: a handler to the DBConnection object
    :param build_count: an integer value with number of new builds
    :param builders_list: a list of builders. The builder is a BuilderConfig object
    :param projects: a list of a ProjectConfig objects
    :param user_names: a list of an usernames (identifier) from the database
    """
    print("Starting creating builds")
    created = 0
    completed_results = [
        results.SUCCESS,
        results.WARNINGS,
        results.FAILURE,
        results.SKIPPED,
        results.EXCEPTION,
        results.CANCELED,
        results.NOT_REBUILT,
        results.DEPENDENCY_FAILURE,
        results.MERGED,
        results.INTERRUPTED,
    ]

    for number in range(build_count):
        builder = random.choice(builders_list)
        codebases = random.choice(projects[builder.project].codebases)
        codebase = random.choice(codebases.keys())
        repository = codebases[codebase]
        submitted_at = datetime2epoch(
            datetime.datetime.now() + datetime.timedelta(seconds=random.randint(-3*60*60, -3*60*60))
        )
        complete_at = submitted_at + random.randint(60 * 60, 3 * 60 * 60)
        build = {
            'branch': repository['branch'],
            'revision': "%032x" % random.getrandbits(160),  # Random sha-1 hash
            'repository': repository['repository'],
            'codebase': codebase,
            'project': builder.project,
            'reason': 'A build was forced by {username} {username}@localhost'.format(username=random.choice(user_names)),
            'submitted_at': submitted_at,
            'complete_at': complete_at,
            'buildername': builder.name,
            'slavepool': None,
            'number': number,
            'slavename': random.choice(builder.slavenames),
            'results': random.choice(completed_results),
        }
        result = yield db.builds.createFullBuildObject(**build)
        if result:
            created += 1
        print_progress_bar(number+1, build_count)

    print("Created %d new builds, %d skipped" % (created, build_count - created))


def print_progress_bar(iteration, total, prefix='', suffix='', decimals=1, length=100, fill=u'█'):
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    print('\r%s |%s| %s%% %s' % (prefix, bar, percent, suffix), end='\r')
    # Print New Line on Complete
    if iteration == total:
        print()
