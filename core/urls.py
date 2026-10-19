from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("leads/", views.lead_list, name="lead_list"),
    path("leads/<int:pk>/", views.lead_detail, name="lead_detail"),
    path("signals/", views.signal_list, name="signal_list"),
    path("leads/<int:pk>/draft/", views.lead_draft_outreach, name="lead_draft_outreach"),
    path("outreach/", views.approval_queue, name="approval_queue"),
    path("outreach/<int:pk>/approve/", views.approve_outreach_view, name="approve_outreach"),
    path("outreach/<int:pk>/reject/", views.reject_outreach_view, name="reject_outreach"),
]