from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta

from .models import PartnerOrganization, PartnerUser, PartnerApplication
from cases.models import IncidentReport


class PartnerRequiredMixin(LoginRequiredMixin):
    """
    Mixin that ensures the user is a verified partner member.
    """
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        
        try:
            partner_profile = request.user.partner_profile
            if not partner_profile.is_active:
                messages.error(request, "Your partner account is inactive.")
                return redirect('home')
        except PartnerUser.DoesNotExist:
            messages.error(request, "You are not registered as a partner.")
            return redirect('home')
        
        return super().dispatch(request, *args, **kwargs)


class PartnerDashboardView(PartnerRequiredMixin, View):
    """
    Main dashboard for partner organizations.
    Shows jurisdiction pool, assigned cases, and stats.
    """
    
    def get(self, request):
        partner_profile = request.user.partner_profile
        org = partner_profile.organization
        jurisdiction = org.jurisdiction
        
        # Get cases in this jurisdiction
        jurisdiction_cases = IncidentReport.objects.filter(
            jurisdiction__iexact=jurisdiction
        ).order_by('-created_at')
        
        # Separate: My Org's Assigned vs Pool (unassigned)
        my_cases = jurisdiction_cases.filter(assigned_partner=org)
        pool_cases = jurisdiction_cases.filter(
            Q(assigned_partner__isnull=True) | 
            Q(assigned_partner__is_active=False)
        )
        
        # Stats
        stats = {
            'total_pool': pool_cases.count(),
            'my_active': my_cases.filter(status='OPEN').count(),
            'my_resolved': my_cases.filter(status='RESOLVED').count(),
            'critical': jurisdiction_cases.filter(risk_score__gte=8).count(),
            'stale_cases': jurisdiction_cases.filter(
                updated_at__lt=timezone.now() - timedelta(hours=24),
                status='OPEN'
            ).count(),
        }
        
        context = {
            'organization': org,
            'jurisdiction': jurisdiction,
            'my_cases': my_cases[:10],
            'pool_cases': pool_cases[:10],
            'stats': stats,
        }
        
        return render(request, 'partners/dashboard.html', context)


class CasePoolView(PartnerRequiredMixin, View):
    """
    Shows all unassigned cases in the partner's jurisdiction.
    Allows claiming cases.
    """
    
    def get(self, request):
        partner_profile = request.user.partner_profile
        org = partner_profile.organization
        jurisdiction = org.jurisdiction
        
        pool_cases = IncidentReport.objects.filter(
            jurisdiction__iexact=jurisdiction,
            assigned_partner__isnull=True
        ).order_by('-risk_score', '-created_at')
        
        context = {
            'organization': org,
            'cases': pool_cases,
            'jurisdiction': jurisdiction,
        }
        
        return render(request, 'partners/case_pool.html', context)


class ClaimCaseView(PartnerRequiredMixin, View):
    """
    Allows a partner to claim an unassigned case.
    """
    
    def post(self, request, case_id):
        partner_profile = request.user.partner_profile
        org = partner_profile.organization
        
        # Only responders and admins can claim
        if partner_profile.role == PartnerUser.Role.VIEWER:
            messages.error(request, "You don't have permission to claim cases.")
            return redirect('partners:pool')
        
        case = get_object_or_404(IncidentReport, id=case_id)
        
        # Verify jurisdiction match
        if case.jurisdiction.lower() != org.jurisdiction.lower():
            messages.error(request, "This case is not in your jurisdiction.")
            return redirect('partners:pool')
        
        # Check if already assigned
        if case.assigned_partner and case.assigned_partner.is_active:
            messages.warning(request, "This case is already assigned to another partner.")
            return redirect('partners:pool')
        
        # Claim the case
        case.assigned_partner = org
        case.save(update_fields=['assigned_partner'])
        
        messages.success(request, f"Case #{case.case_id} has been claimed by {org.name}.")
        return redirect('partners:dashboard')


class PartnerApplicationView(View):
    """
    Public form for organizations to apply to become partners.
    """
    
    def get(self, request):
        return render(request, 'partners/apply.html')
    
    def post(self, request):
        # Validate Turnstile
        from utils.captcha import validate_turnstile
        token = request.POST.get('cf-turnstile-response')
        is_valid, error_msg = validate_turnstile(token, request.META.get('REMOTE_ADDR'))
        
        if not is_valid:
            messages.error(request, error_msg)
            return render(request, 'partners/apply.html', {'error': error_msg})
        
        # Create application
        application = PartnerApplication.objects.create(
            org_name=request.POST.get('org_name'),
            org_type=request.POST.get('org_type', 'NGO'),
            jurisdiction=request.POST.get('jurisdiction'),
            contact_name=request.POST.get('contact_name'),
            contact_email=request.POST.get('contact_email'),
            contact_phone=request.POST.get('contact_phone', ''),
            website=request.POST.get('website', ''),
            description=request.POST.get('description', ''),
        )
        
        messages.success(
            request, 
            f"Thank you! Your application for {application.org_name} has been submitted. "
            "We will review it and contact you soon."
        )
        return redirect('home')
