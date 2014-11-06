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
