from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views import View
from django.contrib.auth.views import LoginView

from .forms import CustomUserCreationForm, CustomAuthenticationForm, ProfileUpdateForm
from .models import User


ROLE_DASHBOARD_MAP = {
    'faculty': '/events/dashboard/',
    'club_head': '/events/dashboard/',
    'hod': '/events/approver-dashboard/',
    'hr': '/events/approver-dashboard/',
    'dean_research': '/events/approver-dashboard/',
    'dean_accounts': '/events/approver-dashboard/',
    'dean_academics': '/events/approver-dashboard/',
    'student': '/events/student-dashboard/',
    'transport': '/events/student-dashboard/',
    'mess': '/events/student-dashboard/',
    'maintenance': '/events/student-dashboard/',
}


class RegisterView(View):
    template_name = 'accounts/register.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect(self._get_dashboard(request.user))
        form = CustomUserCreationForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Welcome, {user.get_full_name()}! Your account has been created.')
            return redirect(self._get_dashboard(user))
        return render(request, self.template_name, {'form': form})

    def _get_dashboard(self, user):
        return ROLE_DASHBOARD_MAP.get(user.role, '/events/dashboard/')


class CustomLoginView(LoginView):
    authentication_form = CustomAuthenticationForm
    template_name = 'accounts/login.html'

    def get_success_url(self):
        user = self.request.user
        return ROLE_DASHBOARD_MAP.get(user.role, '/events/dashboard/')


class ProfileView(View):
    template_name = 'accounts/profile.html'

    @staticmethod
    def get(request):
        if not request.user.is_authenticated:
            return redirect('/accounts/login/')
        form = ProfileUpdateForm(instance=request.user)
        return render(request, 'accounts/profile.html', {'form': form})

    @staticmethod
    def post(request):
        if not request.user.is_authenticated:
            return redirect('/accounts/login/')
        form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('/accounts/profile/')
        return render(request, 'accounts/profile.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('/accounts/login/')
