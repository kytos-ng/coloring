|Tag| |License| |Build| |Coverage| |Quality|

.. raw:: html

  <div align="center">
    <h1><code>kytos/coloring</code></h1>

    <strong>NApp reponsible for coloring switches on the network topology</strong>

    <h3><a href="https://kytos-ng.github.io/api/coloring.html">OpenAPI Docs</a></h3>
  </div>


Overview
========
NApp to color switches based on the network topology.

After picking a color for each switch, installs high
priority flows in each switch, that send to the controller
packets with a neighbors' color.

Requirements
============

- `amlight/flow_stats <https://github.com/kytos-ng/flow_stats>`_
- `kytos/flow_manager <https://github.com/kytos-ng/flow_manager>`_

Events
======

Subscribed
----------

- ``kytos/topology.updated``

.. TAGs

.. |License| image:: https://img.shields.io/github/license/kytos-ng/kytos.svg
   :target: https://github.com/kytos-ng/kytos/blob/master/LICENSE
.. |Build| image:: https://scrutinizer-ci.com/g/kytos-ng/coloring/badges/build.png?b=master
  :alt: Build status
  :target: https://scrutinizer-ci.com/g/kytos-ng/coloring/?branch=master
.. |Coverage| image:: https://scrutinizer-ci.com/g/kytos-ng/coloring/badges/coverage.png?b=master
  :alt: Code coverage
  :target: https://scrutinizer-ci.com/g/kytos-ng/coloring/?branch=master
.. |Quality| image:: https://scrutinizer-ci.com/g/kytos-ng/coloring/badges/quality-score.png?b=master
  :alt: Code-quality score
  :target: https://scrutinizer-ci.com/g/kytos-ng/coloring/?branch=master
.. |Stable| image:: https://img.shields.io/badge/stability-stable-green.svg
   :target: https://github.com/kytos-ng/coloring
.. |Tag| image:: https://img.shields.io/github/tag/kytos-ng/coloring.svg
   :target: https://github.com/kytos-ng/coloring/tags
