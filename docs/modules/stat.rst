``stat`` - Query stat counters
==============================

The ``stat`` module queries stat counters on affected nodes.

There are two kinds of stat counters, both of which are queried using this module, but using slightly different syntaxes.

.. option:: -s --sum
   
   Only print the sum of all nodes to the standard output, rather than per-node information.

Querying ``statd`` counters
---------------------------
::

    halonctl stat [my-counter-name]

The ``statd`` daemon keeps track of counters such as ``system-cpu-usage`` and ``interface-ether1-bandwidth``. The available counters are fixed, but may vary depending on available network interfaces, configured mail servers, etc. Running the ``stat`` module without any arguments lists all available counters per node.

These are some of the counters with their descriptions:

* ``system-cpu-usage`` - System CPU usage
* ``system-mem-usage`` - System RAM usage
* ``system-storage-iops`` - Current read/write operations on the storage disk
* ``system-storage-latency`` - Current latency to the storage disk (in ms)
* ``system-storage-usage`` - Currently used space on the storage disk (in %)
* ``system-swap-iops`` - Current read/write operations on the swap disk
* ``system-swap-usage`` - Currently used space on the swap disk (in %)

* ``mail-license-count`` - Number of users currently counting towards your license
* ``mail-quarantine-count`` - Number of letters stuck in quarantine
* ``mail-queue-count`` - Number of letters currently in the queue

* ``interface-*-bandwidth`` - Current bandwidth usage (in bytes)
* ``interface-*-packets`` - Number of packets currently in transit

Querying ``stat()`` counters
----------------------------
::

    halonctl stat [key1] [key2] [key3]

This version reads arbitrary stat counters created with the HSL ``stat()`` function. This kind of stat counters has up to three keys, and any of these three can be queried.

Leave a key as ``.`` if you do not care about its value, or ``-`` to query for a blank value (NULL).

To fetch all stat counters, you would do this::

    halonctl stat . . .

To fetch only the "mail:total" counter::

    halonctl stat mail:total . .

Specifically for example.org::

    halonctl stat mail:total . example.org

Blank third key (total to all domains, in this case)::

    halonctl stat mail:total . -

All counters for example.org::

    halonctl stat . . example.org
