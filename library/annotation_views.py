from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def retired(request, *args, **kwargs):
    return HttpResponse("This page is no longer available.", status=410)
