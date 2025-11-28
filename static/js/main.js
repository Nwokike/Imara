document.addEventListener('DOMContentLoaded', function() {
    initFormSubmit();
});

function initFormSubmit() {
    const reportForm = document.getElementById('reportForm');
    const submitBtn = document.getElementById('submitBtn');
    
    if (reportForm && submitBtn) {
        reportForm.addEventListener('submit', function() {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="loading-spinner"></span>Analyzing...';
        });
    }
}
