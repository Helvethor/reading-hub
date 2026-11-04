from django.contrib import admin
from django.urls import include, path

admin.site.index_template = "library/admin_index.html"
urlpatterns = [path("admin/", admin.site.urls), path("", include("library.urls"))]
