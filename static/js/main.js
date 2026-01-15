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
    const toggles = document.querySelectorAll('#themeToggle, #themeToggleDesktop, #themeToggleMobile');
    if (toggles.length === 0) return;

    const html = document.documentElement;
    const savedTheme = localStorage.getItem('theme') || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');

    html.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);

    toggles.forEach(toggle => {
        toggle.addEventListener('click', function () {
            const current = html.getAttribute('data-theme');
            const next = current === 'dark' ? 'light' : 'dark';
            html.setAttribute('data-theme', next);
            localStorage.setItem('theme', next);
            updateThemeIcon(next);
        });
    });
}

function updateThemeIcon(theme) {
    const toggles = document.querySelectorAll('#themeToggle, #themeToggleDesktop, #themeToggleMobile');
    toggles.forEach(toggle => {
        const icon = toggle.querySelector('i');
        if (icon) {
            icon.className = theme === 'dark' ? 'bi bi-sun-fill' : 'bi bi-moon-stars';
        }
    });
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
    const forms = document.querySelectorAll('form[data-loading]');
    forms.forEach(form => {
        form.addEventListener('submit', function (e) {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                if (!navigator.onLine) {
                    e.preventDefault();
                    alert('You appear to be offline. Please check your connection and try again.');
                    return;
                }
                submitBtn.disabled = true;
                const originalText = submitBtn.innerHTML;
                submitBtn.setAttribute('data-original-text', originalText);
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Analyzing...';
            }
        });
    });
}
