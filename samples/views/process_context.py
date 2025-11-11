from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from samples.utils.views import digest_process
from samples.models import Process, Sample
from django.utils.timezone import localtime
from django.core.serializers.json import DjangoJSONEncoder
from samples.templatetags.samples_extras import get_safe_operator_name, timestamp, get_really_full_name
import json

# class SafeJSONEncoder(DjangoJSONEncoder):
#     def default(self, obj):
#         # Django model instance
#         if hasattr(obj, "_meta"):
#             try:
#                 get_absolute_url = obj.get_absolute_url()
#             except AttributeError:
#                 get_absolute_url = None

#             return {
#                 "id": getattr(obj, "id", None),
#                 "label": str(obj),
#                 "get_absolute_url": get_absolute_url,
#                 "finished": getattr(obj, "finished", None),
#             }

#         # datetime → ISO string
#         if hasattr(obj, "isoformat"):
#             return obj.isoformat()

#         # Fallback: let DjangoJSONEncoder try
#         try:
#             return super().default(obj)
#         except TypeError:
#             return str(obj)  # last resort

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



def process_details(request, process_id, sample_id):
    process = get_object_or_404(Process, pk=process_id)
    if process.actual_instance._meta.verbose_name == "sample split":
        sample = get_object_or_404(Sample, pk=sample_id)
        local_context = {"sample": sample,
                        "original_sample": sample,
                        "latest_descendant": None,
                        "cutoff_timestamp": None}
        # raise ValueError(process.actual_instance._meta.verbose_name)
        process_context = digest_process(process, request.user, local_context)  # however you currently build it

    else:
        process_context = digest_process(process, request.user)  # however you currently build it

    # if sample._

    # Add pre-rendered values
    process_context["operator_safe"] = get_safe_operator_name(process_context["operator"])
    process_context["operator_full_name"] = get_really_full_name(process_context["operator"])
    process_context["timestamp_display"] = timestamp(process_context["timestamp"], 0, keep_as_is=True)
    # process_context["process_finished"] = process.finished
    # raise ValueError("DEBUG:", process_context["timestamp"], type(process_context["timestamp"]), process_context["timestamp"].value)

    # raise ValueError(process.finished)


    return JsonResponse(process_context, encoder=SafeJSONEncoder)
