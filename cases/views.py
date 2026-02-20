from django.views.generic import DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from .models import IncidentReport


class CaseDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """
    Forensic case detail view.
    Accessible to staff or partner members assigned to the case.
    """
    model = IncidentReport
    template_name = 'cases/case_detail.html'
    context_object_name = 'case'
    slug_field = 'case_id'
    slug_url_kwarg = 'case_id'
    
    def test_func(self):
        user = self.request.user
        if user.is_staff:
            return True
        
        # Check if user is a partner assigned to this case
        case = self.get_object()
        try:
            partner_profile = user.partner_profile
            return case.assigned_partner == partner_profile.organization
        except Exception:
            return False

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['evidence'] = self.object.evidence_assets.all()
        return context
