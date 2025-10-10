document.addEventListener('DOMContentLoaded', function() {
    const authWrapper = document.getElementById('authWrapper');
    const showRegisterBtn = document.getElementById('showRegister');
    const showLoginBtn = document.getElementById('showLogin');
    
    if (showRegisterBtn) {
        showRegisterBtn.addEventListener('click', function() {
            authWrapper.classList.add('register-active');
        });
    }
    
    if (showLoginBtn) {
        showLoginBtn.addEventListener('click', function() {
            authWrapper.classList.remove('register-active');
        });
    }
    
    const forms = document.querySelectorAll('form');
    
    forms.forEach(function(form) {
        form.addEventListener('submit', function(e) {
            const inputs = form.querySelectorAll('input[required]');
            let isValid = true;
            
            inputs.forEach(function(input) {
                if (!input.value.trim()) {
                    isValid = false;
                    input.style.borderColor = '#dc3545';
                } else {
                    input.style.borderColor = '#ddd';
                }
            });
            
            const password = form.querySelector('input[name="password"]');
            const passwordConfirm = form.querySelector('input[name="password_confirm"]');
            
            if (password && passwordConfirm) {
                if (password.value !== passwordConfirm.value) {
                    isValid = false;
                    passwordConfirm.style.borderColor = '#dc3545';
                    e.preventDefault();
                    alert('Passwords do not match!');
                    return;
                }
            }
            
            if (!isValid) {
                e.preventDefault();
            }
        });
    });
    
    const inputs = document.querySelectorAll('input');
    
    inputs.forEach(function(input) {
        input.addEventListener('input', function() {
            this.style.borderColor = '#ddd';
        });
        
        input.addEventListener('focus', function() {
            this.style.borderColor = '#4CAF50';
        });
        
        input.addEventListener('blur', function() {
            if (this.hasAttribute('required') && !this.value.trim()) {
                this.style.borderColor = '#dc3545';
            } else {
                this.style.borderColor = '#ddd';
            }
        });
    });
    
});