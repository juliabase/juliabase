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

"""This program removes the finished tasks from the database which are older
than a week.

It should be called once a day at night as a cron job.  Maybe run it after the
postgresql_backup script to have a backup, if needed.
"""

import datetime
from samples.models import Task
import django.utils.timezone


Task.objects.filter(status__contains="finished",
                    last_modified__lte=django.utils.timezone.now() - datetime.timedelta(days=7)).delete()
