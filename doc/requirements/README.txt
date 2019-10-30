.. -*- mode: rst; coding: utf-8; ispell-local-dictionary: "english" -*-
..
.. This file is part of JuliaBase, see http://www.juliabase.org.
.. Copyright © 2008–2015 Forschungszentrum Jülich GmbH, Jülich, Germany
..
.. This program is free software: you can redistribute it and/or modify it under
.. the terms of the GNU Affero General Public License as published by the Free
.. Software Foundation, either version 3 of the License, or (at your option) any
.. later version.
..
.. This program is distributed in the hope that it will be useful, but WITHOUT
.. ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
.. FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
.. details.
..
.. You should have received a copy of the GNU Affero General Public License
.. along with this program.  If not, see <http://www.gnu.org/licenses/>.


Setup with pip
==============

Requirements files to install all Python packages you need to run JuliaBase.
All Packages are provided with fixed version numbers. To get the latest versions,
just remove the numbers and the equal signs. For detailed informations see the
`user guide for pip`_.

.. _user guide for pip: https://pip.pypa.io/en/stable/user_guide.html#requirements-files

The files also includes the database connectors for PostgreSQL and MySQL. 
If you use other databases you need to add the connectors yourself.

To install the Python packages use:

.. code-block:: shell-session

    username@server:~$ sudo pip3 install -r requirements/base.txt
