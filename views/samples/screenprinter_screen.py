import iek5.models as ipv_models
import samples.utils.views as utils

class ScreenprinterScreenForm(utils.ProcessForm):
    class Meta:
        model = ipv_models.ScreenprinterScreen
        fields = "__all__"
    
    def __init__(self, user, *args, **kwargs):
        self.no_operator = True
        super().__init__(user, *args, **kwargs)


class EditView(utils.ProcessView):
    form_class = ScreenprinterScreenForm

    def build_forms(self):
        self.forms["sample"] = None
        super().build_forms()
        self.forms.pop("sample")

    def is_referentially_valid(self):
        return True

    def is_all_valid(self):
        return True
    
    def save_to_database(self):
        process = self.forms["process"].save()
        return process
    
    def create_successful_response(self, request):
        success_report = ("Screen was successfully changed in the database.")
        return utils.successful_response(request, success_report, "iek5:lab_notebook_screenprinter_screen", {"year_and_month": "2024/1"})
    
    def startup(self):
        """Fetch the process to-be-edited from the database and check permissions.
        This method has no parameters and no return values, ``self`` is
        modified in-situ.
        """
        try:
            self.identifying_field = parameter_name = self.model.JBMeta.identifying_field
        except AttributeError:
            self.identifying_field, parameter_name = "id", self.class_name + "_id"
        self.id = self.kwargs[parameter_name]
        self.process = self.model.objects.get(**{self.identifying_field: self.id}) if self.id else None
        # permissions.assert_can_add_edit_physical_process(self.request.user, self.process, self.model)
        self.preset_sample = utils.extract_preset_sample(self.request) if not self.process else None
        self.data = self.request.POST or None