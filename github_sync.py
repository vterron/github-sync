#! /usr/bin/env python

# Author: Victor Terron (c) 2014
# Email: `echo vt2rron1iaa32s | tr 132 @.e`
# License: GNU GPLv3

import collections
import contextlib
import os
import subprocess
import tempfile

@contextlib.contextmanager
def tmp_chdir(path):
    """ Temporarily change the working directory. """

    cwd = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(cwd)


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
