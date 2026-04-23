from django.urls import path

from . import views

app_name = "dynamic_quotation"

urlpatterns = [
    path("lead/<int:lead_id>/create/", views.create_quotation, name="quotation_create"),
    path("<int:pk>/", views.quotation_detail, name="quotation_detail"),
    path("<int:pk>/download/", views.quotation_download_pdf, name="quotation_download_pdf"),
    path("<int:pk>/approve/", views.quotation_approve, name="quotation_approve"),
    path("<int:pk>/reject/", views.quotation_reject, name="quotation_reject"),
]
