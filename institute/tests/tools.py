# This file is part of JuliaBase-Institute, see http://www.juliabase.org.
# Copyright © 2008–2017 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# In particular, you may modify this file freely and even remove this license,
# and offer it as part of a web service, as long as you do not distribute it.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.


import logging, io
import django.test
import jb_remote.common


log = io.StringIO()
logging.basicConfig(stream=log)


class TestCase(django.test.TestCase):
    """Test case class with additional JuliaBase functionality.
    """

    def _remove_dynamic_fields(self, dictionary):
        for key, value in list(dictionary.items()):
            if key == "last_modified":
                del dictionary[key]
            elif isinstance(value, dict):
                self._remove_dynamic_fields(value)

    def assertJsonDictEqual(self, response, dictionary):
        data = response.json()
        self._remove_dynamic_fields(data)
        self.assertEqual(data, dictionary)


class JuliaBaseConnection(jb_remote.common.JuliaBaseConnection):
    """Connection mock for unit testing the remote client.  An instance of this
    class can be injected into the remote client module
    (e.g. ``jb_remote_inm``) before it is used.  This module typically has got
    a top-level variable called ``connection`` (possible imported from
    ``jb_remote.common``, which must be rebound.
    """

    def __init__(self, client):
        """Class constructor.

        :param client: Django test client

        :type client: ``django.test.Client``
        """
        self.client = client
        super().__init__()
        self.root_url = "/"
        self.extra = {"HTTP_ACCEPT": "application/json,text/html;q=0.9,application/xhtml+xml;q=0.9,text/*;q=0.8,*/*;q=0.7"}

    def _do_http_request(self, url, data=None):
        if data is None:
            return self.client.post(url, data, **self.extra)
        else:
            return self.client.get(url, **self.extra)

    def open(self, relative_url, data=None, response_is_json=True):
        response = self._do_http_request(self.root_url + relative_url, self._clean_data(data))
        if response_is_json:
            return response.json()
        else:
            return response.content
