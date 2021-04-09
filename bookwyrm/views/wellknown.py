""" responds to various requests to /.well-know """

from dateutil.relativedelta import relativedelta
from django.http import HttpResponseNotFound
from django.http import JsonResponse
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from bookwyrm import models
from bookwyrm.settings import DOMAIN, VERSION


@require_GET
def webfinger(request):
    """ allow other servers to ask about a user """
    resource = request.GET.get("resource")
    if not resource or not resource.startswith("acct:"):
        return HttpResponseNotFound()

    username = resource.replace("acct:", "")
    try:
        user = models.User.objects.get(username=username)
    except models.User.DoesNotExist:
        return HttpResponseNotFound("No account found")

    return JsonResponse(
        {
            "subject": "acct:%s" % (user.username),
            "links": [
                {
                    "rel": "self",
                    "type": "application/activity+json",
                    "href": user.remote_id,
                }
            ],
        }
    )


@require_GET
def nodeinfo_pointer(_):
    """ direct servers to nodeinfo """
    return JsonResponse(
        {
            "links": [
                {
                    "rel": "http://nodeinfo.diaspora.software/ns/schema/2.0",
                    "href": "https://%s/nodeinfo/2.0" % DOMAIN,
                }
            ]
        }
    )


@require_GET
def nodeinfo(_):
    """ basic info about the server """
    status_count = models.Status.objects.filter(user__local=True).count()
    user_count = models.User.objects.filter(local=True).count()

    month_ago = timezone.now() - relativedelta(months=1)
    last_month_count = models.User.objects.filter(
        local=True, last_active_date__gt=month_ago
    ).count()

    six_months_ago = timezone.now() - relativedelta(months=6)
    six_month_count = models.User.objects.filter(
        local=True, last_active_date__gt=six_months_ago
    ).count()

    site = models.SiteSettings.get()
    return JsonResponse(
        {
            "version": "2.0",
            "software": {"name": "bookwyrm", "version": VERSION},
            "protocols": ["activitypub"],
            "usage": {
                "users": {
                    "total": user_count,
                    "activeMonth": last_month_count,
                    "activeHalfyear": six_month_count,
                },
                "localPosts": status_count,
            },
            "openRegistrations": site.allow_registration,
        }
    )


@require_GET
def instance_info(_):
    """ let's talk about your cool unique instance """
    user_count = models.User.objects.filter(local=True).count()
    status_count = models.Status.objects.filter(user__local=True).count()

    site = models.SiteSettings.get()
    return JsonResponse(
        {
            "uri": DOMAIN,
            "title": site.name,
            "short_description": "",
            "description": site.instance_description,
            "version": "0.0.1",
            "stats": {
                "user_count": user_count,
                "status_count": status_count,
            },
            "thumbnail": "https://%s/static/images/logo.png" % DOMAIN,
            "languages": ["en"],
            "registrations": site.allow_registration,
            "approval_required": False,
        }
    )


@require_GET
def peers(_):
    """ list of federated servers this instance connects with """
    names = models.FederatedServer.objects.values_list("server_name", flat=True)
    return JsonResponse(list(names), safe=False)


@require_GET
def host_meta(request):
    """ meta of the host """
    return TemplateResponse(request, "host_meta.xml", {"DOMAIN": DOMAIN})
