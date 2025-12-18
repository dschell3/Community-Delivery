// Form validation and utilities

document.addEventListener('DOMContentLoaded', function() {
    // Password confirmation validation
    const passwordFields = document.querySelectorAll('input[name="password"]');
    const confirmFields = document.querySelectorAll('input[name="confirm_password"]');
    
    confirmFields.forEach(function(confirmField) {
        confirmField.addEventListener('input', function() {
            const form = this.closest('form');
            const passwordField = form.querySelector('input[name="password"]');
            
            if (passwordField && this.value !== passwordField.value) {
                this.setCustomValidity('Passwords do not match');
            } else {
                this.setCustomValidity('');
            }
        });
    });
    
    // File input preview
    const fileInputs = document.querySelectorAll('input[type="file"]');
    fileInputs.forEach(function(input) {
        input.addEventListener('change', function() {
            const fileName = this.files[0]?.name;
            if (fileName) {
                const label = this.parentElement.querySelector('.file-name');
                if (label) {
                    label.textContent = fileName;
                }
            }
        });
    });
    
    // Confirmation dialogs for destructive actions
    const confirmForms = document.querySelectorAll('form[data-confirm]');
    confirmForms.forEach(function(form) {
        form.addEventListener('submit', function(e) {
            const message = this.dataset.confirm || 'Are you sure?';
            if (!confirm(message)) {
                e.preventDefault();
            }
        });
    });
    
    // Auto-dismiss flash messages after 5 seconds
    const flashMessages = document.querySelectorAll('.flash');
    flashMessages.forEach(function(flash) {
        setTimeout(function() {
            flash.style.opacity = '0';
            flash.style.transition = 'opacity 0.3s';
            setTimeout(function() {
                flash.remove();
            }, 300);
        }, 5000);
    });
});

// Utility function for AJAX requests
function apiRequest(url, method, data) {
    const options = {
        method: method,
        headers: {
            'Content-Type': 'application/json',
        },
        credentials: 'same-origin'
    };
    
    if (data) {
        options.body = JSON.stringify(data);
    }
    
    // Add CSRF token if available
    const csrfToken = document.querySelector('input[name="csrf_token"]')?.value;
    if (csrfToken) {
        options.headers['X-CSRFToken'] = csrfToken;
    }
    
    return fetch(url, options).then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    });
}
