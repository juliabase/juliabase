from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from samples.utils.views import digest_process
from samples.models import Process
import pprint
from django.utils.timezone import localtime
from django.core.serializers.json import DjangoJSONEncoder
from samples.templatetags.samples_extras import get_safe_operator_name, timestamp, get_really_full_name

# class SafeJSONEncoder(DjangoJSONEncoder):
#     def default(self, obj):
#         # If it's a Django model instance, return something useful
#         if hasattr(obj, "_meta"):
#             # Could return a dict instead of just str(obj)
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
#         # Fallback: always stringify
#         try:
#             return super().default(obj)
#         except TypeError:
#             return str(obj)
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

        # User instance
        # User = get_user_model()
        # if isinstance(obj, User):
        #     return str(obj)  # or obj.get_full_name()

        # Fallback: let DjangoJSONEncoder try
        try:
            return super().default(obj)
        except TypeError:
            return str(obj)  # last resort


def process_details(request, process_id):
    process = get_object_or_404(Process, pk=process_id)
    process_context = digest_process(process, request.user)  # however you currently build it

    # Add pre-rendered values
    process_context["operator_safe"] = get_safe_operator_name(process_context["operator"])
    process_context["operator_full_name"] = get_really_full_name(process_context["operator"])
    process_context["timestamp_display"] = timestamp(process_context["timestamp"], 0, keep_as_is=True)
    # process_context["process_finished"] = process.finished
    # raise ValueError("DEBUG:", process_context["timestamp"], type(process_context["timestamp"]), process_context["timestamp"].value)

    # raise ValueError(process.finished)


    return JsonResponse(process_context, encoder=SafeJSONEncoder)
