#! /usr/bin/env python
# encoding: UTF-8

# Author: Victor Terron (c) 2014
# Email: `echo vt2rron1iaa32s | tr 132 @.e`
# License: GNU GPLv3

__author__ = "Víctor Terrón"
__author_username__ = "vterron"

import calendar
import collections
import contextlib
import json
import os
import subprocess
import re
import requests
import tempfile
import time

@contextlib.contextmanager
def tmp_chdir(path):
    """ Temporarily change the working directory. """

    cwd = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(cwd)


class FileCache(collections.namedtuple('_FileCache', 'path')):
    """ Interface to cache data to disk.

    This class allows to easily write and read data from a JSON file, via
    its set() and get() methods. The file is opened and closed every time an
    operation is made, so we do not need to worry about closing it when done
    with the FileCache object.

    """

    def up_to_date(self, max_hours = 1):
        """ Determine whether the cache file has expired.

        Return True if the cache file was last modified less than 'max_hours'
        ago; and False otherwise. If the file does not exist, returns False
        too. In this manner, any time that False is returned we know that we
        cannot use the cached value.

        """

        try:
            max_seconds = max_hours * 3600
            cache_mtime = os.path.getmtime(self.path)
            return (time.time() - cache_mtime) <= (max_seconds)
        except OSError:
            return False

    def set(self, *args):
        """ Write the received arguments to the JSON cache file. """

        with open(self.path, 'wt') as fd:
            json.dump(args, fd)


class GitRepository(collections.namedtuple('_GitRepository', 'path')):

    def check_output(self, args):
        """ Run a command in the Git directory and return its output.

        This method chdirs to the Git directory, runs a command with arguments
        and returns its output as a string with leading and trailing characters
        removed. If the return code is non-zero, CalledProcessError is raised.

        """

        # subprocess.check_output() new in 2.7; we want 2.6 compatibility
        with tmp_chdir(self.path):
            with tempfile.TemporaryFile() as fd:
                subprocess.check_call(args, stdout = fd)
                fd.seek(0)
                return fd.readline().strip()

    @property
    def revision(self):
        """A human-readable revision number of the Git repository.

        Return the output of git-describe, the Git command that returns an
        identifier which tells us how far (number of commits) off a tag we are
        and the hash of the current HEAD. This allows us to precisely pinpoint
        where we are in the Git repository.

        """

        # --long: always output the long format even when it matches a tag
        # --dirty: describe the working tree; append '-dirty' if necessary
        # --tags: use any tag found in refs/tags namespace
        args = ['git', 'describe', '--long', '--dirty', '--tags']
        return self.check_output(args)

    @property
    def last_commit_date(self):
        """ Return the author date of the last commit, as a Unix timestamp. """

        # -<n>: number of commits to show
        # %at: author date, UNIX timestamp
        args = ['git', 'log', '-1', '--format=%at']
        return float(self.check_output(args))

    @property
    def origin(self):
        """ Return the URL the Git repository was originally cloned from. """
        args = ['git', 'config', '--get', 'remote.origin.url']
        return self.check_output(args)

    @property
    def API_URL(self):
        """ Return the URL of the GitHub commits API.

        The GitHub commits API allows us to list, view, and compare commits in
        a repository. More info: https://developer.github.com/v3/repos/commits/

        """

        # Match HTTPS and Git clones from GitHub
        REGEXP = "(git@|https://)github\.com(:|/)(?P<username>\w+)/(?P<repository>\w+).git"
        URL = 'https://api.github.com/repos/{0}/{1}/commits?page=1&per_page=1'
        match = re.match(REGEXP, self.origin)
        username   = match.group('username')
        repository = match.group('repository')
        return URL.format(username, repository)

    def get_last_github_commit(self, timeout=None):
        """ Return the short SHA1 of the last commit pushed to GitHub.

        Use the GitHub API to get the SHA1 hash of the last commit pushed to
        GitHub, and then obtain its short version with `git rev-parse`. Return
        a two-element tuple with (a) the short SHA1 and (b) date of the last
        commit as a Unix timestamp. For example: ('51277fc', 1414061493)

        The 'timeout' keyword argument defines the number of seconds after
        which the requests.exceptions.Timeout exception is raised if the server
        has not issued a response. Note that this is not the same as a time
        limit on the entire response download.

        """

        # [From: https://developer.github.com/v3/#user-agent-required]
        # All API requests MUST include a valid User-Agent header [..] We
        # request that you use your GitHub username, or the name of your
        # application, for the User-Agent header value. This allows us to
        # contact you if there are problems.

        headers = {'User-Agent': __author_username__}
        kwargs = dict(headers=headers, timeout=timeout)
        r = requests.get(self.API_URL, **kwargs)
        last_commit = r.json()[0]
        hash_ = last_commit['sha']
        date_str = last_commit['commit']['author']['date']

        # Timestamps are returned in ISO 8601 format: "YYYY-MM-DDTHH:MM:SSZ",
        # where Z is the zone designator for the zero UTC offset (that is, the
        # time is in UTC). Convert this string to a Unix timestamp value.

        fmt = "%Y-%m-%dT%H:%M:%SZ"
        date_struct = time.strptime(date_str, fmt)
        date_ = calendar.timegm(date_struct)

        args = ['git', 'rev-parse', '--short', hash_]
        short_hash = self.check_output(args)
        return short_hash, date_
