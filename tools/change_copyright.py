#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, re

old_message = "Copyright © 2008–2015 Torsten Bronger <bronger@physik.rwth-aachen.de>,"

for root, dirnames, filenames in os.walk("/home/bronger/src/juliabase/juliabase"):
    dirnames[:] = [dir for dir in dirnames if dir != ".git"]
    for filename in filenames:
        if filename.endswith((".py", ".po", ".yaml", ".html", ".css", ".txt")) and \
           filename not in ["replace_license_headers.py", "change_copyright.py"]:
            filepath = os.path.join(root, filename)
            content = open(filepath).read()
            if content:
                assert len(re.findall(re.escape(old_message), content)) < 2
                new_content = content.replace(old_message,
                                              "Copyright © 2008–2015 Forschungszentrum Jülich GmbH, Jülich, Germany")
                if new_content == content:
                    print(filepath, "was not changed.")
                else:
                    old_lines = new_content.splitlines(True)
                    new_lines = [line for line in old_lines if "Marvin Goblet <m.goblet@fz-juelich.de>." not in line]
                    assert len(old_lines) == len(new_lines) + 1
                    open(filepath, "w").write("".join(new_lines))
