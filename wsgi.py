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


# For a proper configuration you need to add your projeckt and the
# juliabase package to the python path.
#import os
#import sys
#sys.path.append("/home/username/myproject")
#sys.path.append("/home/username/myproject/juliabase")

# When the WSGI server loads your projeckt, Django needs to import your
# settings module. So you have to add the settinge module to your server
# configuration or uncomment the following statement.
#os.environ["DJANGO_SETTINGS_MODULE"] = "mysite.settings"

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
