# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2017 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.



import importlib
from django.conf import settings


storage = None

def set_storage_backend():
    """Sets the global variable ``storage`` to the storage backend selected in the
    settings.  This should be called exactly once during startup.  Currently,
    it is called in the ``ready`` method of the jb_common app.
    """
    global storage
    assert not storage
    module_name, __, class_name = settings.BLOB_STORAGE_BACKEND[0].rpartition(".")
    module = importlib.import_module(module_name)
    storage = getattr(module, class_name)(*settings.BLOB_STORAGE_BACKEND[1])
