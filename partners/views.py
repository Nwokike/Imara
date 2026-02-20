from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.decorators import method_decorator
from datetime import timedelta

from .models import PartnerOrganization, PartnerUser
from cases.models import IncidentReport
from utils.ratelimit import login_ratelimit, form_ratelimit


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
        
        # Use atomic transaction to prevent race condition
        from django.db import transaction
        
        with transaction.atomic():
            # Lock the row for update
            case = IncidentReport.objects.select_for_update().get(id=case_id)
            
            # Check if already assigned
            if case.assigned_partner_id and case.assigned_partner.is_active:
                messages.warning(request, "This case is already assigned to another partner.")
                return redirect('partners:pool')
            
            # Claim the case
            case.assigned_partner = org
            case.status = 'CLAIMED'
            case.save(update_fields=['assigned_partner', 'status'])
            
            # Audit log
            from .models import PartnerAuditLog
            PartnerAuditLog.objects.create(
                organization=org,
                user=request.user,
                action='CLAIM',
                details=f"Claimed case #{case.case_id}"
            )
        
        messages.success(request, f"Case #{case.case_id} has been claimed by {org.name}.")
        return redirect('partners:dashboard')


class PartnerLoginView(View):
    """
    Custom branded login for partners (NOT Django admin).
    Supports Turnstile captcha for security.
    """
    
    def get(self, request):
        if request.user.is_authenticated:
            try:
                request.user.partner_profile
                return redirect('partners:dashboard')
            except PartnerUser.DoesNotExist:
                pass
        return render(request, 'partners/login.html')
    
    @method_decorator(login_ratelimit)
    def post(self, request):
        from django.contrib.auth import authenticate, login
        from utils.captcha import validate_turnstile
        
        # Validate Turnstile
        token = request.POST.get('cf-turnstile-response')
        is_valid, error_msg = validate_turnstile(token, request.META.get('REMOTE_ADDR'))
        
        if not is_valid:
            messages.error(request, error_msg)
            return render(request, 'partners/login.html')
        
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            try:
                partner_profile = user.partner_profile
                if not partner_profile.is_active:
                    messages.error(request, "Your partner account is inactive.")
                    return render(request, 'partners/login.html')
                
                login(request, user)
                messages.success(request, f"Welcome back, {user.first_name or user.username}!")
                return redirect('partners:dashboard')
            except PartnerUser.DoesNotExist:
                messages.error(request, "This account is not registered as a partner.")
        else:
            messages.error(request, "Invalid username or password.")
        
        return render(request, 'partners/login.html')


class AcceptInviteView(View):
    """
    Handles partner invite acceptance and password setup.
    """
    
    def get(self, request, token):
        from .models import PartnerInvite
        
        try:
            invite = PartnerInvite.objects.get(token=token)
        except PartnerInvite.DoesNotExist:
            messages.error(request, "Invalid or expired invitation link.")
            return redirect('partners:login')
        
        if not invite.is_valid:
            if invite.is_accepted:
                messages.info(request, "This invitation has already been used. Please login.")
            else:
                messages.error(request, "This invitation has expired.")
            return redirect('partners:login')
        
        return render(request, 'partners/accept_invite.html', {
            'invite': invite,
            'organization': invite.organization
        })
    
    def post(self, request, token):
        from django.contrib.auth import login
        from django.contrib.auth.models import User
        from .models import PartnerInvite, PartnerUser
        from utils.captcha import validate_turnstile
        
        # Validate Turnstile
        captcha_token = request.POST.get('cf-turnstile-response')
        is_valid, error_msg = validate_turnstile(captcha_token, request.META.get('REMOTE_ADDR'))
        
        if not is_valid:
            messages.error(request, error_msg)
            return redirect('partners:accept_invite', token=token)
        
        try:
            invite = PartnerInvite.objects.get(token=token)
        except PartnerInvite.DoesNotExist:
            messages.error(request, "Invalid invitation.")
            return redirect('partners:login')
        
        if not invite.is_valid:
            messages.error(request, "This invitation is no longer valid.")
            return redirect('partners:login')
        
        # Get form data
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        
        # Validate passwords
        if password != password_confirm:
            messages.error(request, "Passwords do not match.")
            return render(request, 'partners/accept_invite.html', {
                'invite': invite,
                'organization': invite.organization
            })
        
        # Use Django's password validators
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError
        try:
            validate_password(password)
        except ValidationError as e:
            for error in e.messages:
                messages.error(request, error)
            return render(request, 'partners/accept_invite.html', {
                'invite': invite,
                'organization': invite.organization
            })
        
        # Create username from email
        username = invite.email.split('@')[0]
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        
        # Create user
        user = User.objects.create_user(
            username=username,
            email=invite.email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        
        # Create partner profile
        PartnerUser.objects.create(
            user=user,
            organization=invite.organization,
            role=invite.role,
            is_active=True
        )
        
        # Mark invite as accepted
        from django.utils import timezone
        invite.is_accepted = True
        invite.accepted_at = timezone.now()
        invite.save()
        
        # Log them in
        login(request, user)
        
        messages.success(
            request,
            f"Welcome to Imara, {first_name}! You are now part of {invite.organization.name}."
        )
        return redirect('partners:dashboard')


class PartnerCaseDetailView(PartnerRequiredMixin, View):
    """
    Detail view for a case claimed by the partner organization.
    Allows viewing evidence and updating status.
    """
    
    def get(self, request, case_id):
        partner_profile = request.user.partner_profile
        org = partner_profile.organization
        
        case = get_object_or_404(
            IncidentReport,
            id=case_id,
            assigned_partner=org
        )
        
        context = {
            'case': case,
            'organization': org,
            'can_edit': partner_profile.role != PartnerUser.Role.VIEWER
        }
        
        return render(request, 'partners/case_detail.html', context)
    
    def post(self, request, case_id):
        partner_profile = request.user.partner_profile
        org = partner_profile.organization
        
        if partner_profile.role == PartnerUser.Role.VIEWER:
            messages.error(request, "You don't have permission to update cases.")
            return redirect('partners:case_detail', case_id=case_id)
        
        case = get_object_or_404(
            IncidentReport,
            id=case_id,
            assigned_partner=org
        )
        
        new_status = request.POST.get('status')
        notes_text = request.POST.get('notes', '').strip()
        
        if new_status and new_status in dict(IncidentReport.status.field.choices):
            old_status = case.status
            if old_status != new_status:
                case.status = new_status
                # Audit log
                from .models import PartnerAuditLog
                PartnerAuditLog.objects.create(
                    organization=org,
                    user=request.user,
                    action='STATUS_CHANGE',
                    details=f"Case #{case.case_id} status changed from {old_status} to {new_status}"
                )
        
        # Add human note
        if notes_text:
            from .models import CaseNote
            CaseNote.objects.create(
                case=case,
                author=partner_profile,
                text=notes_text
            )
        
        case.save()
        messages.success(request, "Case updated successfully.")
        return redirect('partners:case_detail', case_id=case_id)


class AdminRequiredMixin(PartnerRequiredMixin):
    """Mixin that ensures the user is an organization admin."""
    
    def dispatch(self, request, *args, **kwargs):
        result = super().dispatch(request, *args, **kwargs)
        if hasattr(result, 'status_code') and result.status_code != 200:
            return result
        
        if request.user.partner_profile.role != PartnerUser.Role.ADMIN:
            messages.error(request, "Only organization admins can access this page.")
            return redirect('partners:dashboard')
        
        return result


class TeamListView(PartnerRequiredMixin, View):
    """List all team members in the organization."""
    
    def get(self, request):
        partner_profile = request.user.partner_profile
        org = partner_profile.organization
        
        team_members = org.members.filter(is_active=True).select_related('user')
        pending_invites = org.invites.filter(is_accepted=False)
        
        context = {
            'organization': org,
            'team_members': team_members,
            'pending_invites': pending_invites,
            'is_admin': partner_profile.role == PartnerUser.Role.ADMIN,
            'roles': PartnerUser.Role.choices,
        }
        
        return render(request, 'partners/team.html', context)


class MyCasesView(PartnerRequiredMixin, View):
    """List all cases assigned to the partner organization."""

    def get(self, request):
        org = request.user.partner_profile.organization

        my_cases = IncidentReport.objects.filter(
            assigned_partner=org
        ).order_by('-risk_score', '-created_at')

        stats = {
            "open": my_cases.filter(status='OPEN').count(),
            "claimed": my_cases.filter(status='CLAIMED').count(),
            "in_progress": my_cases.filter(status='IN_PROGRESS').count(),
            "resolved": my_cases.filter(status='RESOLVED').count(),
            "closed": my_cases.filter(status='CLOSED').count(),
        }

        return render(request, 'partners/my_cases.html', {
            "organization": org,
            "jurisdiction": org.jurisdiction,
            "cases": my_cases,
            "stats": stats,
        })


class PartnerSettingsView(PartnerRequiredMixin, View):
    """Organization settings (admin-only edits)."""

    def get(self, request):
        org = request.user.partner_profile.organization
        is_admin = request.user.partner_profile.role == PartnerUser.Role.ADMIN
        return render(request, 'partners/settings.html', {
            "organization": org,
            "is_admin": is_admin,
        })

    def post(self, request):
        org = request.user.partner_profile.organization
        is_admin = request.user.partner_profile.role == PartnerUser.Role.ADMIN

        if not is_admin:
            messages.error(request, "Only organization admins can update settings.")
            return redirect('partners:settings')

        contact_email = (request.POST.get('contact_email') or '').strip()
        phone = (request.POST.get('phone') or '').strip()
        website = (request.POST.get('website') or '').strip()

        if contact_email:
            org.contact_email = contact_email
        org.phone = phone
        org.website = website
        org.save(update_fields=['contact_email', 'phone', 'website'])

        messages.success(request, "Settings updated.")
        return redirect('partners:settings')


class InviteTeamMemberView(AdminRequiredMixin, View):
    """Org admin invites a new team member."""
    
    def post(self, request):
        from .models import PartnerInvite
        
        org = request.user.partner_profile.organization
        
        # Check seat limit
        if org.is_at_capacity:
            messages.error(request, f"Your organization has reached the maximum of {org.max_seats} members. Remove someone first.")
            return redirect('partners:team')
        
        email = request.POST.get('email', '').strip().lower()
        role = request.POST.get('role', PartnerUser.Role.RESPONDER)
        
        if not email:
            messages.error(request, "Email is required.")
            return redirect('partners:team')
        
        # Check if already a member
        from django.contrib.auth.models import User
        existing_user = User.objects.filter(email=email).first()
        if existing_user:
            try:
                existing_profile = existing_user.partner_profile
                if existing_profile.organization == org:
                    messages.error(request, "This person is already a team member.")
                    return redirect('partners:team')
            except PartnerUser.DoesNotExist:
                pass
        
        # Check for pending invite
        if org.invites.filter(email=email, is_accepted=False).exists():
            messages.error(request, "An invite is already pending for this email.")
            return redirect('partners:team')
        
        # Create invite
        invite = PartnerInvite.objects.create(
            email=email,
            organization=org,
            role=role,
            invited_by=request.user
        )
        
        # Send invite email
        from django.urls import reverse
        from django.conf import settings
        from dispatch.tasks import send_email_task
        
        invite_url = request.build_absolute_uri(
            reverse('partners:accept_invite', args=[invite.token])
        )
        
        html_content = f"""
        <h2>You're invited to join {org.name} on Project Imara</h2>
        <p>Hello,</p>
        <p>You have been invited to join <strong>{org.name}</strong> as a <strong>{invite.get_role_display()}</strong> on the Project Imara Partner Portal.</p>
        <p>Project Imara is a digital platform protecting women and girls from online violence across Africa.</p>
        <p style="margin: 30px 0;">
            <a href="{invite_url}" style="background-color: #2D1B36; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 6px;">Accept Invitation</a>
        </p>
        <p>Or copy this link: {invite_url}</p>
        <p>This invitation expires in 7 days.</p>
        <hr>
        <p style="color: #666; font-size: 12px;">If you did not expect this invitation, you can safely ignore this email.</p>
        """
        
        email_payload = {
            "sender": {"name": "Project Imara", "email": settings.BREVO_SENDER_EMAIL},
            "to": [{"email": email}],
            "subject": f"You're invited to join {org.name} on Project Imara",
            "htmlContent": html_content
        }
        send_email_task(email_payload)
        
        messages.success(request, f"Invite sent to {email}!")
        return redirect('partners:team')


class UpdateMemberRoleView(AdminRequiredMixin, View):
    """Org admin changes a team member's role."""
    
    def post(self, request, member_id):
        org = request.user.partner_profile.organization
        
        member = get_object_or_404(PartnerUser, id=member_id, organization=org, is_active=True)
        
        # Cannot change your own role
        if member.user == request.user:
            messages.error(request, "You cannot change your own role.")
            return redirect('partners:team')
        
        new_role = request.POST.get('role')
        if new_role in dict(PartnerUser.Role.choices):
            old_role = member.role
            member.role = new_role
            member.save()
            
            # Audit log
            from .models import PartnerAuditLog
            PartnerAuditLog.objects.create(
                organization=org,
                user=request.user,
                action='ROLE_CHANGE',
                details=f"Updated {member.user.username} role from {old_role} to {new_role}"
            )
            
            messages.success(request, f"{member.user.get_full_name() or member.user.username}'s role updated to {member.get_role_display()}.")
        
        return redirect('partners:team')


class RemoveMemberView(AdminRequiredMixin, View):
    """Org admin removes a team member (frees a seat)."""
    
    def post(self, request, member_id):
        org = request.user.partner_profile.organization
        
        member = get_object_or_404(PartnerUser, id=member_id, organization=org, is_active=True)
        
        # Cannot remove yourself
        if member.user == request.user:
            messages.error(request, "You cannot remove yourself.")
            return redirect('partners:team')
        
        # Deactivate (soft delete to preserve history)
        member.is_active = False
        member.save()
        
        # Audit log
        from .models import PartnerAuditLog
        PartnerAuditLog.objects.create(
            organization=org,
            user=request.user,
            action='MEMBER_REMOVE',
            details=f"Removed member {member.user.username}"
        )
        
        messages.success(request, f"{member.user.get_full_name() or member.user.username} has been removed from the team.")
        return redirect('partners:team')


class CancelInviteView(AdminRequiredMixin, View):
    """Org admin cancels a pending invite."""
    
    def post(self, request, invite_id):
        from .models import PartnerInvite
        
        org = request.user.partner_profile.organization
        
        invite = get_object_or_404(PartnerInvite, id=invite_id, organization=org, is_accepted=False)
        invite.delete()
        
        messages.success(request, f"Invite to {invite.email} has been cancelled.")
        return redirect('partners:team')


