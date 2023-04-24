#########
Changelog
#########
All notable changes to the coloring NApp will be documented in this file.

[UNRELEASED] - Under development
********************************

General Information
===================
- ``@rest`` endpoints are now run by ``starlette/uvicorn`` instead of ``flask/werkzeug``.

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
