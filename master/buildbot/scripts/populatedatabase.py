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
from time import time

import datetime
import names
from progress_bar import InitBar
from twisted.internet import defer

from buildbot import config as config_module
from buildbot.db import connector
from buildbot.master import BuildMaster
from buildbot.util import in_reactor
from buildbot.util import datetime2epoch
from buildbot.status.results import COMPLETED_RESULTS


MAX_UNIQUE_USER_COUNT = 5494


@in_reactor
@defer.inlineCallbacks
def populate_database(config):
    master = BuildMaster(config['baseDir'])
    master.config = load_config(config, config['configFile'])
    db = connector.DBConnector(master, basedir=config['baseDir'])
    seed = int(time())
    if config['seed']:
        seed = int(config['seed'])
    random.seed(seed)
    if not config['quiet']:
        print("Seed =", seed)

    yield db.setup(check_version=False, verbose=not config['quiet'])
    users = yield populate_user(db, int(config['users']), verbose=not config['quiet'])
    yield populate_build(
        db,
        int(config['builds']),
        master.config.builders,
        master.config.projects,
        users,
        verbose=not config['quiet']
    )


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
def populate_user(db, user_count, verbose=True):
    """
    This function create `user_count` number of random user in database
    :param db: a handler to the DBConnection object
    :param user_count: an integer value with number of new users
    """
    if verbose:
        print("Starting creating users")
    if user_count > MAX_UNIQUE_USER_COUNT:
        raise ValueError("Can not generate more than %d unique user" % MAX_UNIQUE_USER_COUNT)

    users = []
    created = 0
    progress_bar = InitBar(size=user_count, stream=sys.stdout)

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
        if verbose:
            progress_bar(ind+1)

    if verbose:
        print()
        print("Created %d new users, %d skipped" % (created, user_count - created))

    defer.returnValue(map(lambda x: x['identifier'], users))


@defer.inlineCallbacks
def populate_build(db, build_count, builders_list, projects, user_names, verbose=True):
    """
    :param db: a handler to the DBConnection object
    :param build_count: an integer value with number of new builds
    :param builders_list: a list of builders. The builder is a BuilderConfig object
    :param projects: a list of a ProjectConfig objects
    :param user_names: a list of an usernames (identifier) from the database
    :param verbose: a boolean value indicate to print all information to std output
    """

    def handler(result, counter, *args):
        result[counter] += 1

    progress_bar = InitBar(size=build_count, stream=sys.stdout)

    if verbose:
        print("Starting creating builds")
    res = {
        'created': 0,
        'skipped': 0,
    }

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
            'results': random.choice(COMPLETED_RESULTS),
        }
        promise = db.builds.createFullBuildObject(**build)
        promise.addCallback(lambda *args: handler(res, 'created'))
        promise.addErrback(lambda *args: handler(res, 'skipped'))
        yield promise

        if verbose:
            progress_bar(number+1)

    if verbose:
        print()
        print("Created %d new builds, %d skipped" % (res['created'], res['skipped']))
