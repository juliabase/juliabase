#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os

old_licence = """# This file is part of JuliaBase, the samples database.
#
# Copyright © 2008–2014 Forschungszentrum Jülich, Germany,
#                       Marvin Goblet <m.goblet@fz-juelich.de>,
#                       Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.
"""

agpl_licence = """# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2015 Torsten Bronger <bronger@physik.rwth-aachen.de>,
#                       Marvin Goblet <m.goblet@fz-juelich.de>.
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
"""

gpl_licence = """# This file is part of JuliaBase-Institute, see http://www.juliabase.org.
# Copyright © 2008–2015 Torsten Bronger <bronger@physik.rwth-aachen.de>,
#                       Marvin Goblet <m.goblet@fz-juelich.de>.
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
"""

old_licence_html = """{% comment %}
This file is part of JuliaBase, the samples database.

Copyright © 2008–2014 Forschungszentrum Jülich, Germany,
                      Marvin Goblet <m.goblet@fz-juelich.de>,
                      Torsten Bronger <t.bronger@fz-juelich.de>

You must not use, install, pass on, offer, sell, analyse, modify, or distribute
this software without explicit permission of the copyright holder.  If you have
received a copy of this software without the explicit permission of the
copyright holder, you must destroy it immediately and completely.
{% endcomment %}
"""

agpl_licence_html = """{% comment %}
This file is part of JuliaBase, see http://www.juliabase.org.
Copyright © 2008–2015 Torsten Bronger <bronger@physik.rwth-aachen.de>,
                      Marvin Goblet <m.goblet@fz-juelich.de>.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU Affero General Public License as published by the Free
Software Foundation, either version 3 of the License, or (at your option) any
later version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
{% endcomment %}
"""

gpl_licence_html = """{% comment %}
This file is part of JuliaBase-Institute, see http://www.juliabase.org.
Copyright © 2008–2015 Torsten Bronger <bronger@physik.rwth-aachen.de>,
                      Marvin Goblet <m.goblet@fz-juelich.de>.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

In particular, you may modify this file freely and even remove this license,
and offer it as part of a web service, as long as you do not distribute it.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
details.

You should have received a copy of the GNU General Public License along with
this program.  If not, see <http://www.gnu.org/licenses/>.
{% endcomment %}
"""

old_licence_css = """/*
This file is part of JuliaBase, the samples database.

Copyright © 2008–2014 Forschungszentrum Jülich, Germany,
                      Marvin Goblet <m.goblet@fz-juelich.de>,
                      Torsten Bronger <t.bronger@fz-juelich.de>

You must not use, install, pass on, offer, sell, analyse, modify, or distribute
this software without explicit permission of the copyright holder.  If you have
received a copy of this software without the explicit permission of the
copyright holder, you must destroy it immediately and completely.
*/
"""

agpl_licence_css = """/*
This file is part of JuliaBase, see http://www.juliabase.org.
Copyright © 2008–2015 Torsten Bronger <bronger@physik.rwth-aachen.de>,
                      Marvin Goblet <m.goblet@fz-juelich.de>.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU Affero General Public License as published by the Free
Software Foundation, either version 3 of the License, or (at your option) any
later version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/
"""

gpl_licence_css = """/*
This file is part of JuliaBase-Institute, see http://www.juliabase.org.
Copyright © 2008–2015 Torsten Bronger <bronger@physik.rwth-aachen.de>,
                      Marvin Goblet <m.goblet@fz-juelich.de>.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

In particular, you may modify this file freely and even remove this license,
and offer it as part of a web service, as long as you do not distribute it.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
details.

You should have received a copy of the GNU General Public License along with
this program.  If not, see <http://www.gnu.org/licenses/>.
*/
"""


old_licence_rst = """.. This file is part of JuliaBase, the samples database.
..
.. Copyright © 2008–2014 Forschungszentrum Jülich, Germany,
..                       Marvin Goblet <m.goblet@fz-juelich.de>,
..                       Torsten Bronger <t.bronger@fz-juelich.de>
..
.. You must not use, install, pass on, offer, sell, analyse, modify, or
.. distribute this software without explicit permission of the copyright
.. holder.  If you have received a copy of this software without the explicit
.. permission of the copyright holder, you must destroy it immediately and
.. completely.
"""

agpl_licence_rst = """.. This file is part of JuliaBase, see http://www.juliabase.org.
.. Copyright © 2008–2015 Torsten Bronger <bronger@physik.rwth-aachen.de>,
..                       Marvin Goblet <m.goblet@fz-juelich.de>.
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
"""

gpl_licence_rst = """.. This file is part of JuliaBase-Institute, see http://www.juliabase.org.
.. Copyright © 2008–2015 Torsten Bronger <bronger@physik.rwth-aachen.de>,
..                       Marvin Goblet <m.goblet@fz-juelich.de>.
..
.. This program is free software: you can redistribute it and/or modify it under
.. the terms of the GNU General Public License as published by the Free Software
.. Foundation, either version 3 of the License, or (at your option) any later
.. version.
..
.. In particular, you may modify this file freely and even remove this license,
.. and offer it as part of a web service, as long as you do not distribute it.
..
.. This program is distributed in the hope that it will be useful, but WITHOUT
.. ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
.. FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
.. details.
..
.. You should have received a copy of the GNU General Public License along with
.. this program.  If not, see <http://www.gnu.org/licenses/>.
"""


for root, dirnames, filenames in os.walk("/home/bronger/src/juliabase/juliabase"):
    dirnames[:] = [dir for dir in dirnames if dir != ".git"]
    for filename in filenames:
        if filename.endswith((".py", ".po", ".yaml")):
            filepath = os.path.join(root, filename)
            content = open(filepath).read()
            if root.startswith("/home/bronger/src/juliabase/juliabase/institute") or \
               root == "/home/bronger/src/juliabase/juliabase":
                new_content = content.replace(old_licence, gpl_licence)
            else:
                assert "manage.py" not in filepath
                new_content = content.replace(old_licence, agpl_licence)
            if content and new_content == content:
                print(filepath, "was not changed.")
            open(filepath, "w").write(new_content)
        elif filename.endswith(".html"):
            filepath = os.path.join(root, filename)
            content = open(filepath).read()
            if root.startswith("/home/bronger/src/juliabase/juliabase/institute") or \
               root == "/home/bronger/src/juliabase/juliabase":
                new_content = content.replace(old_licence_html, gpl_licence_html)
            else:
                new_content = content.replace(old_licence_html, agpl_licence_html)
            if content and new_content == content:
                print(filepath, "was not changed.")
            open(filepath, "w").write(new_content)
        elif filename.endswith(".css"):
            filepath = os.path.join(root, filename)
            content = open(filepath).read()
            if root.startswith("/home/bronger/src/juliabase/juliabase/institute") or \
               root == "/home/bronger/src/juliabase/juliabase":
                new_content = content.replace(old_licence_css, gpl_licence_css)
            else:
                new_content = content.replace(old_licence_css, agpl_licence_css)
            if content and new_content == content:
                print(filepath, "was not changed.")
            open(filepath, "w").write(new_content)
        elif filename.endswith(".txt"):
            filepath = os.path.join(root, filename)
            content = open(filepath).read()
            if root.startswith("/home/bronger/src/juliabase/juliabase/institute") or \
               root == "/home/bronger/src/juliabase/juliabase":
                new_content = content.replace(old_licence_rst, gpl_licence_rst)
            else:
                new_content = content.replace(old_licence_rst, agpl_licence_rst)
            if content and new_content == content:
                print(filepath, "was not changed.")
            open(filepath, "w").write(new_content)
