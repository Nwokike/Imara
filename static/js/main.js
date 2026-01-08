/**
 * Project Imara - Theme and UI functionality
 * Externalized from base.html inline scripts
 */

document.addEventListener('DOMContentLoaded', function () {
    initThemeToggle();
    registerServiceWorker();
    initSmoothScroll();
    initFormSubmit();
});

/**
 * Theme toggle functionality (dark/light mode)
 */
function initThemeToggle() {
    const toggle = document.getElementById('themeToggle');
    if (!toggle) return;

    const html = document.documentElement;
    const savedTheme = localStorage.getItem('theme') || 'light';

    html.setAttribute('data-bs-theme', savedTheme);
    updateThemeIcon(savedTheme);

    toggle.addEventListener('click', function () {
        const current = html.getAttribute('data-bs-theme');
        const next = current === 'dark' ? 'light' : 'dark';
        html.setAttribute('data-bs-theme', next);
        localStorage.setItem('theme', next);
        updateThemeIcon(next);
    });
}

function updateThemeIcon(theme) {
    const toggle = document.getElementById('themeToggle');
    if (!toggle) return;
    const icon = toggle.querySelector('i');
    if (icon) {
        icon.className = theme === 'dark' ? 'bi bi-sun-fill' : 'bi bi-moon-fill';
    }
}

/**
 * Service worker registration for PWA
 */
function registerServiceWorker() {
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/serviceworker.js', { scope: '/' })
            .catch(function (err) {
                // Silently fail in production or send to Sentry
            });
    }
}

/**
 * Smooth scroll for anchor links
 */
function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            if (href.startsWith('#') && href.length > 1) {
                e.preventDefault();
                const target = document.querySelector(href);
                if (target) {
                    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            }
        });
    });
}

/**
 * Form submit handling with loading state
 */
function initFormSubmit() {
    const reportForm = document.getElementById('reportForm');
    const submitBtn = document.getElementById('submitBtn');

    if (reportForm && submitBtn) {
        reportForm.addEventListener('submit', function (e) {
            // Check for offline status
            if (!navigator.onLine) {
                e.preventDefault();
                alert('You appear to be offline. Please check your connection and try again.');
                return;
            }
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="loading-spinner"></span>Analyzing...';
        });
    }
}
