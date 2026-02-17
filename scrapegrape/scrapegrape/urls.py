"""
URL configuration for scrapegrape project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path

import publishers.views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("django-rq/", include("django_rq.urls")),
    path("publishers/create", publishers.views.create, name="publisher-create"),
    path("publishers/<int:publisher_id>/edit", publishers.views.update, name="publisher-update"),
    path("publishers/bulk-upload", publishers.views.bulk_upload, name="publisher-bulk-upload"),
    path("publishers/<int:publisher_id>", publishers.views.publisher_detail, name="publisher-detail"),
    path("submit", publishers.views.submit_url, name="submit-url"),
    path("jobs/<uuid:job_id>", publishers.views.job_show, name="job-show"),
    path("api/jobs/<uuid:job_id>/stream", publishers.views.job_stream, name="job-stream"),
    path("", publishers.views.table, name="table"),
]
