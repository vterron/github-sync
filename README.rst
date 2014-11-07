github_sync
===========

This module compares the last commit in a local repository to the one most recently pushes to the GitHub repository it was originally cloned from. If we are behind, a warning is emitted in order to let your users know that there are unmerged changes available on GitHub — and that doing `git pull` would probably be a good idea.

Usage
=====

.. code:: python

    import github_sync
    github_sync.check(__file__)

Emitted warnings look like this:

.. code:: python

    UserWarning: Your current revision is 'v0.2-298-gc3e6c56' (Tue Jul 29 15:18:09 2014), but there is a more recent version (51277fc, Thu Oct 23 12:51:33 2014) available at https://github.com/vterron/lemon
