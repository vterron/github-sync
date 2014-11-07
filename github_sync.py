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
import warnings

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

    def get(self):
        """ Return the contents of the JSON cache file. """

        with open(self.path, 'rt') as fd:
            return json.load(fd)


class GitRepository(collections.namedtuple('_GitRepository', 'path')):

    # The JSON file where the results of the last query to the GitHub API are
    # cached. This file is located in the directory of the Git repository.
    CACHE_FILE_FILENAME = '.github-last-commit-cache.json'

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
    def cache_path(self):
        """ The path to the on-disk JSON cache. """

        return os.path.join(self.path, self.CACHE_FILE_FILENAME)

    @property
    def revision(self):
        """A human-readable revision number of the Git repository.

        Return the output of git-describe, the Git command that returns an
        identifier which tells us how far (number of commits) off a tag we are
        and the hash of the current HEAD. This allows us to precisely pinpoint
        where we are in the Git repository.

        At least one tag in the commit history is needed for git-describe to
        tell us, well, the latest tag, but with the --always option we will
        fall back to an abbreviated hash if it cannot find any suitable tags.

        """

        # --long: always output the long format even when it matches a tag
        # --dirty: describe the working tree; append '-dirty' if necessary
        # --tags: use any tag found in refs/tags namespace
        # --always: show uniquely abbreviated commit object as fallback

        args = ['git', 'describe', '--long', '--dirty', '--tags', '--always']
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

    def _parse_origin(self):
        """ Return the GitHub username and repository.

        Parse the URL the Git repository was cloned from and extract both the
        username and repository, returning them as a two-element tuple. For
        example, given the URL 'https://github.com/kennethreitz/requests.git',
        the tuple ('kennethreitz', 'requests') would be returned.

        """

        # Match HTTPS and Git clones from GitHub
        REGEXP = "(git@|https://)github\.com(:|/)(?P<username>\w+)/(?P<repository>\w+).git"
        match = re.match(REGEXP, self.origin)
        username   = match.group('username')
        repository = match.group('repository')
        return username, repository

    @property
    def API_URL(self):
        """ Return the URL of the GitHub commits API.

        The GitHub commits API allows us to list, view, and compare commits in
        a repository. More info: https://developer.github.com/v3/repos/commits/

        """

        URL = 'https://api.github.com/repos/{0}/{1}/commits?page=1&per_page=1'
        return URL.format(*self._parse_origin())

    @property
    def URL(self):
        """ Return the URL of the repository on GitHub. """

        URL = "https://github.com/{0}/{1}"
        return URL.format(*self._parse_origin())

    def get_last_github_commit(self, timeout=None, max_hours=1):
        """ Return the short SHA1 of the last commit pushed to GitHub.

        Use the GitHub API to get the SHA1 hash of the last commit pushed to
        GitHub, and then obtain its short version with `git rev-parse`. Return
        a two-element tuple with (a) the short SHA1 and (b) date of the last
        commit as a Unix timestamp. For example: ('51277fc', 1414061493)

        The method uses a JSON file, in the directory of the Git repository, to
        temporarily cache the values returned by the GitHub API. If the cache
        file was last modified less than 'max_hours' hours ago, the contents of
        the JSON file are returned. Otherwise, the GitHub API is queried and
        the result file-cached before the method returns. This is necessary as
        it would be impolite (and also rather inefficient) to make too many
        queries to the GitHub API. Anyway, even if we did not care about that,
        the rate limit for unauthenticated requests would only allow us to make
        up to sixty requests per hour.

        The 'timeout' keyword argument defines the number of seconds after
        which the requests.exceptions.Timeout exception is raised if the server
        has not issued a response. Note that this is not the same as a time
        limit on the entire response download.

        """

        cache = FileCache(self.cache_path)
        if cache.up_to_date(max_hours = max_hours):
            return cache.get()

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
        t = short_hash, date_
        cache.set(*t)
        return t

class UnmergedGitHubWarning(Warning):
    """ Warn that there are unmerged changes on GitHub. """
    pass
