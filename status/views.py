from django.shortcuts import render
from django.views.decorators.http import require_POST

from .forms import SubscribeForm
from .models import Subscriber


def status_page(request, form=None, message=None):
    data = request.company.fetch_status_data()
    return render(
        request,
        "status/page.html",
        {
            "data": data,
            "form": form or SubscribeForm(),
            "message": message,
        },
    )


@require_POST
def subscribe(request):
    # The company comes from the hostname, never from the form, so one
    # customer's page can't subscribe people to another's.
    form = SubscribeForm(request.POST)
    if not form.is_valid():
        return status_page(request, form=form)
    Subscriber.objects.get_or_create(
        company=request.company, email=form.cleaned_data["email"]
    )
    message = f"Subscribed to {request.company.name} status updates."
    return status_page(request, message=message)
