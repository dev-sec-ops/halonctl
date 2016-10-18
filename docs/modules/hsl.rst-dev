``hsl`` - Manage configuration
==============================
::

    halonctl hsl [subcommand] [configdir]

The HSL module manages configuration files. It can dump a node's configuration to text files, for easy versioning or offline editing, as well as push or pull configuration from different nodes.

The HSL module is special in that it works with a *configuration directory*. The directory you give it should be reserved for it and it alone, as it makes certain assumptions about the structure of it. You also should not rename files in it.

You're highly encouraged to put your configuration directory under version control!

``hsl dump`` - Download a node's configuration
----------------------------------------------

::

    halonctl hsl dump [configdir]

This is the recommended way to create a configuration directory. It will dump the **first matched node**'s configuration into the given directory, overwriting any existing files with colliding names.

It's recommended to use the global ``-n`` switch to pick a single node to dump from, as the results may otherwise be unpredictable if multiple nodes have slightly different configurations.

.. note::
   Sometimes, you may not want a file managed - perhaps it contains node-specific keys or other things that wouldn't make sense to share.
   
   In these cases, simply create a file in your configuration directory called ``_ignore`` containing a list of keys (without file extensions) to ignore, one per line. For example, to ignore ``file__4.txt``, enter ``file__4``.

``hsl diff`` - Show a diff of local/remote counterparts
-------------------------------------------------------

::

    halonctl hsl diff [configdir]

Similar to ``git diff``, this will display a list of patches representing all local changes that are not reflected on the remote side, and vice versa.

.. note::
   You may use `Jinja2 <http://jinja.pocoo.org>`_ **template syntax** in your configuration files!
   
   Templates will be rendered per-node, and given access to the ``node`` variable (a :class:`Node <halonctl.models.Node>` instance), and can thus access things such as the name and cluster of the node.
   
   Diffs will consider a file unchanged if the *rendered* file is identical, which means template expressions will not trigger diffs unless their output changes.

``hsl pull`` - Merge remote changes
-----------------------------------

::

    halonctl hsl pull [configdir]

This will merge remote changes into your local configuration directory.

Unlike for instance ``git pull``, you will be asked to apply each patch one by one - configuration is precious, and without version control, a carelessly applied patch could potentially lead to data loss. Read each patch carefully before applying!

Note that if you are using template tags in your configuration files, a remote change will produce a patch which offers to overwrite the template block with its rendered contents for that node.

In these cases, you need to manually merge the two together, as there is no way to reverse a rendered template back to its source.

``hsl push`` - Push configuration to nodes
------------------------------------------

::

    halonctl hsl push [-f] [configdir]

This will push changes to all targeted nodes, asking for confirmation before each patch applied. Templates will be rendered for each node.

.. warning::
   This operation should target only a single node in each cluster.
   
   If the configuration change is written to multiple nodes in a cluster, each node will push it out to its entire cluster, one after another, and each push will cause every node in the cluster to recompile its configuration. If you're pushing to an entire large cluster, this can cause excessive amounts of system load across it!
   
   Attempting to push a configuration change to *all* of your nodes, a confirmation will be displayed.
