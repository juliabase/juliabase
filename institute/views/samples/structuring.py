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


from django.utils.translation import ugettext_lazy as _, ugettext
import samples.utils.views as utils
import institute.models as institute_models


class StructuringForm(utils.ProcessForm):
    class Meta:
        model = institute_models.Structuring
        fields = "__all__"


class EditView(utils.RemoveFromMySamplesMixin, utils.ProcessView):
    form_class = StructuringForm


_ = ugettext
