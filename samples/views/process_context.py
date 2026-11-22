from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods
from samples import permissions
from samples.utils.views import digest_process
from samples.models import Sample
from samples.views.sample import find_sample_process, is_process_cleared
from django.core.serializers.json import DjangoJSONEncoder
from samples.templatetags.samples_extras import get_safe_operator_name, timestamp, get_really_full_name

class SafeJSONEncoder(DjangoJSONEncoder):
    def default(self, obj):
        # Django model instance
        if hasattr(obj, "_meta"):
            try:
                get_absolute_url = obj.get_absolute_url()
            except AttributeError:
                get_absolute_url = None

            return {
                "id": getattr(obj, "id", None),
                "label": str(obj),
                "get_absolute_url": get_absolute_url,
                "finished": getattr(obj, "finished", None),
            }

        # datetime → ISO string
        if hasattr(obj, "isoformat"):
            return obj.isoformat()

        # Fallback: let DjangoJSONEncoder try
        try:
            return super().default(obj)
        except TypeError:
            return str(obj)  # last resort

    def iterencode(self, value, **kwargs):
        # Recursively coerce bad dict keys
        def normalize_keys(obj):
            if isinstance(obj, dict):
                new_dict = {}
                for k, v in obj.items():
                    if not isinstance(k, (str, int, float, bool, type(None))):
                        k = str(k)  # ← coerce key
                    new_dict[k] = normalize_keys(v)
                return new_dict
            elif isinstance(obj, list):
                return [normalize_keys(i) for i in obj]
            return obj

        normalized = normalize_keys(value)
        return super().iterencode(normalized, **kwargs)



@login_required
@require_http_methods(["GET"])
def process_details(request, process_id, sample_id):
    """Returns the body of a process as shown on the data sheet of a sample.
    The user may load it exactly if the process is shown to them on the data
    sheet of this sample.

    :param request: the current HTTP Request object
    :param process_id: the ID of the process
    :param sample_id: the ID of the sample whose data sheet shows the process

    :type request: HttpRequest
    :type process_id: str
    :type sample_id: str

    :return:
      the HTTP response object

    :rtype: HttpResponse

    :raises Http404: if the sample does not exist or if the process is not
        shown on its data sheet
    :raises samples.permissions.PermissionError: if the user is not allowed to
        view the sample
    """
    sample = get_object_or_404(Sample, pk=int(sample_id))
    clearance = permissions.get_sample_clearance(request.user, sample)
    entry = find_sample_process(sample, int(process_id))
    if entry is None or not is_process_cleared(request.user, clearance, entry.process):
        raise Http404("The process is not shown on the data sheet of this sample.")
    process = entry.process
    process_context = digest_process(process, request.user, entry.local_context).copy()
    # Add pre-rendered values
    process_context["operator_safe"] = get_safe_operator_name(process_context["operator"])
    process_context["operator_full_name"] = get_really_full_name(process_context["operator"])
    process_context["timestamp_display"] = timestamp(process_context["timestamp"], 0, keep_as_is=True)
    process_context["show_process_url"] = process.get_absolute_url()
    
    return JsonResponse(process_context, encoder=SafeJSONEncoder)
