from django.views.generic import DetailView
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from .models import IncidentReport


@method_decorator(staff_member_required, name='dispatch')
class CaseDetailView(DetailView):
    """Staff-only view to display case details."""
    model = IncidentReport
    template_name = 'cases/case_detail.html'
    context_object_name = 'case'
    slug_field = 'case_id'
    slug_url_kwarg = 'case_id'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['evidence'] = self.object.evidence.all()
        return context
