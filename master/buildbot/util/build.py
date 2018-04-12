from itertools import chain
from operator import itemgetter

from buildbot.status.results import RESULT_TO_CSS, Results

from twisted.internet import defer


@defer.inlineCallbacks
def prepare_mybuilds(master, user_id):
    """
    Return information about builds for user by his user_id.
    We use these builds to show as HTML (MybuildsResource) or JSON (MyBuildsJsonResource)

    @param master: instance of buildbot.master.BuildMaster
    @param user_id: uid from `users` table
    @return: list of dicts (builds)
    """
    status = master.getStatus()
    display_repositories = prepare_display_repositories(status)

    builds = yield master.db.builds.getLastBuildsOwnedBy(
        user_id,
        status.botmaster,
        master.config.myBuildDaysCount,
    )
    builds_by_ssid = prepare_builds_by_ssid(builds)
    sourcestamps = yield master.db.sourcestamps.getSourceStampsForManyIds(builds_by_ssid.keys())

    builds = merge_sourcestamps_to_build(
        builds_by_ssid,
        display_repositories,
        sourcestamps,
        status,
    )
    defer.returnValue(builds)


def merge_sourcestamps_to_build(builds_by_ssid, display_repositories, sourcestamps, status):
    """
    One build can have many sourcestamps. We merge here sourcestamps to related builds.

    @param builds_by_ssid: dict with builds. Key is the sourcestampsetid, value is build's data
    @param display_repositories: dict with repositories setup (from master.cfg)
    @param sourcestamps: list of sourcestamps which we want to merge into builds
    @param status: instance of buildbot.status.master.Status
    @return: list of builds sorted by builds_id
    """
    for row in sourcestamps:
        build = builds_by_ssid[row['sourcestampsetid']]
        query_param = "%s_branch=%s" % (row['codebase'], row['branch'])
        build['query_params'].append(query_param)

        row['revision_url'] = status.get_rev_url(row['revision'], row['repository'])
        row['display_repository'] = display_repositories.get(row['repository'], row['repository'])

        build['sourcestamps'].append(row)

    return sorted(builds_by_ssid.values(), key=itemgetter('builds_id'), reverse=True)


def prepare_display_repositories(status):
    """
    prepare all repositories setup (from master.cfg)

    @param status: instance of buildbot.status.master.Status
    @return: dict of repositories data
    """
    display_repositories = {}
    flatten_codebases = chain(*map(lambda x: x.codebases, status.getProjects().values()))
    properties = map(lambda y: y.values(), flatten_codebases)
    for prop in chain(*properties):
        display_repository = prop.get('display_repository', prop['repository'])
        display_repositories[prop['repository']] = display_repository
    return display_repositories


def prepare_builds_by_ssid(builds):
    """
    Repack builds from DB to dict.
    Use sourcestampsetid as key.
    Add extra fields: sourcestamps, query_params.
    Change datetime objects to string

    @param builds: builds data from DB
    @return: dict, repacked builds
    """
    builds_by_ssid = {}
    for row in builds:
        builds_by_ssid[row['sourcestampsetid']] = row.copy()
        builds_by_ssid[row['sourcestampsetid']].update({
            'submitted_at': str(row['submitted_at']),
            'complete_at': str(row['complete_at']),
            'sourcestamps': [],
            'query_params': [],
        })
    return builds_by_ssid


def add_css_classes_to_results(builds):
    """
    Change build['results'] <int> to human name and suitable CSS class
    Add new information as new keys and values in build <dict>
    Use new copy of dicts instead in-place update.

    @param builds: list of builds (dicts)
    @return: new list of builds with CSS data (name, class)
    """
    builds_with_css = []
    for build_ in builds:
        build = build_.copy()
        build['result_css_class'] = RESULT_TO_CSS.get(build['results'], "")
        build['result_name'] = Results[build['results']] if build['results'] >= 0 else "running"
        builds_with_css.append(build)
    return builds_with_css
