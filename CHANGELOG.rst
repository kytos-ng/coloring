#########
Changelog
#########
All notable changes to the coloring NApp will be documented in this file.

[UNRELEASED] - Under development
********************************

[2023.1.0] - 2023-06-12
***********************

Changed
=======
- ``of_coloring`` now supports table group settings from ``of_multi_table``

Added
=====
- Subscribed to new event ``kytos/of_multi_table.enable_table`` as well as publishing ``kytos/coloring.enable_table`` required to set a different ``table_id`` to flows.
- Added ``settings.TABLE_GROUP_ALLOWED`` set containing the allowed table groups, for now there is only ``'base'``.

General Information
===================
- ``@rest`` endpoints are now run by ``starlette/uvicorn`` instead of ``flask/werkzeug``.

[2022.3.1] - 2023-02-17
***********************

Fixed
=====
- ``get_cookie`` could overflow 8 bytes for certain dpid values
- Made sure that the generated matched ``dl_src`` is a local unicast address

General Information
===================

If you have been running this NApp version 2022.3.0 or prior in production it's recommended that you delete the previous flows before you start ``kytosd`` again since it this new version can end up pushing flows might not completely overwrite the old ones depending on dpids values:

.. code:: bash

  $ curl -X DELETE http://127.0.0.1:8181/api/kytos/flow_manager/v2/flows/ -H 'Content-type: application/json' -d '{ "flows": [ { "cookie": 12393906174523604992, "cookie_mask": 18374686479671623680 } ] }'

[2022.3.0] - 2022-12-15
***********************

Added
=====
- Added cookie pattern to flow_mod prefix

[2022.2.1] - 2022-08-15
***********************

Fixed
=====
- Protected shared iterables from size changed thread RuntimeError


[2022.2.0] - 2022-08-08
***********************

General Information
===================
- Increased unit test coverage to at least 85%

[2022.1.0] - 2022-02-08
***********************

Added
=====
- Enhanced and standardized setup.py `install_requires` to install pinned dependencies
