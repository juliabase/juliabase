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


"""Custom logging class which adds an “X-JuliaBase” header.
"""

from django.conf import settings
import django.utils.log
from django.core.mail.message import EmailMultiAlternatives


class AdminEmailHandler(django.utils.log.AdminEmailHandler):

    def send_mail(self, subject, message, *args, **kwargs):
        # This is taken from the parent class, except that instead of
        # ``mail.mail_admins``, we call the function below.
        mail_admins(subject, message, *args, connection=self.connection(), **kwargs)


# This is taken from ``django.core.mail`` with the addition of the X-JuliaBase
# header.
def mail_admins(subject, message, fail_silently=False, connection=None,
                html_message=None):
    """Send a message to the admins, as defined by the ADMINS setting."""
    if not settings.ADMINS:
        return
    if not all(isinstance(a, (list, tuple)) and len(a) == 2 for a in settings.ADMINS):
        raise ValueError('The ADMINS setting must be a list of 2-tuples.')
    mail = EmailMultiAlternatives(
        '%s%s' % (settings.EMAIL_SUBJECT_PREFIX, subject), message,
        settings.SERVER_EMAIL, [a[1] for a in settings.ADMINS],
        connection=connection,
        # The following line is added
        headers={"X-JuliaBase": "Admins"}
    )
    if html_message:
        mail.attach_alternative(html_message, 'text/html')
    mail.send(fail_silently=fail_silently)
