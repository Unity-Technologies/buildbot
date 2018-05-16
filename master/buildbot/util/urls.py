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
from itertools import ifilter


def get_url_and_name_build_in_chain(build_id, chained_builds, project, request):
    """ This function find build in chain and return its name and link

    :param build_id: id of selected build
    :type build_id: int
    :param chained_builds: list of build in chain
    :type chained_builds: list
    :param project: builder project
    :param request: request object
    :return: tuple with two elements: link to build and build name
    """
    from buildbot.status.web.base import path_to_build_by_params

    build_url, build_name = None, None

    selected_build = next(ifilter(lambda b: b['id'] == build_id, chained_builds), None)

    if selected_build:
        build_url = path_to_build_by_params(
            request,
            selected_build['buildername'],
            selected_build['number'],
            project,
        )
        build_name = "{friendly_name} #{build_number}".format(
            friendly_name=selected_build['friendly_name'],
            build_number=selected_build['number'],
        )

    return build_url, build_name
