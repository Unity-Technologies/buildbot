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

BEGINNING = -1
SUCCESS = 0
WARNINGS = 1
FAILURE = 2
SKIPPED = 3
EXCEPTION = 4
RETRY = 5
CANCELED = 6
NOT_REBUILT = 7
DEPENDENCY_FAILURE = 8
RESUME = 9
MERGED = 10
INTERRUPTED = 11


Results = ["success", "warnings", "failure", "skipped", "exception", "retry", "canceled", "not-rebuilt",
           "dependency-failure", "resume", "merged", "interrupted"]

COMPLETED_RESULTS = [
    SUCCESS, WARNINGS, FAILURE, SKIPPED, EXCEPTION, CANCELED,
    NOT_REBUILT, DEPENDENCY_FAILURE, MERGED, INTERRUPTED,
]


RESULT_TO_CSS = {
    BEGINNING: "running",
    SUCCESS: "success",
    WARNINGS: "warnings",
    FAILURE: "failure",
    SKIPPED: "skipped",
    EXCEPTION: "exception",
    RETRY: "retry",
    CANCELED: "canceled",
    NOT_REBUILT: "not-rebuilt",
    DEPENDENCY_FAILURE: "dependency-failure",
    RESUME: "waiting-for-dependency",
    MERGED: "not-started",
    INTERRUPTED: "interrupted",
}

def worst_status(a, b):
    # SUCCESS > WARNINGS > FAILURE > EXCEPTION > RETRY
    # Retry needs to be considered the worst so that conusmers don't have to
    # worry about other failures undermining the RETRY.
    for s in (RETRY, CANCELED, INTERRUPTED, EXCEPTION, DEPENDENCY_FAILURE, FAILURE, WARNINGS, SKIPPED,
              NOT_REBUILT, SUCCESS):
        if s in (a, b):
            return s
