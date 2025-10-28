document.addEventListener('DOMContentLoaded', function() {
    const authWrapper = document.getElementById('authWrapper');
    const showRegisterBtn = document.getElementById('showRegister');
    const showLoginBtn = document.getElementById('showLogin');
    
    // Function to clear messages and reset form inputs for the opposite form
    function clearOppositeForm(isGoingToRegister) {
        if (isGoingToRegister) {
            // Going to register, clear login form
            const loginForm = document.querySelector('.form-panel:first-child form');
            const loginMessages = document.querySelector('.form-panel:first-child .form-messages');
            if (loginForm) loginForm.reset();
            if (loginMessages) loginMessages.innerHTML = '';
        } else {
            // Going to login, clear register form
            const registerForm = document.querySelector('.form-panel:nth-child(2) form');
            const registerMessages = document.querySelector('.form-panel:nth-child(2) .form-messages');
            if (registerForm) registerForm.reset();
            if (registerMessages) registerMessages.innerHTML = '';
        }
        
        // Reset all input borders
        const inputs = document.querySelectorAll('input');
        inputs.forEach(input => {
            input.style.borderColor = '#ddd';
        });
    }
    
    if (showRegisterBtn) {
        showRegisterBtn.addEventListener('click', function() {
            clearOppositeForm(true); // true = going to register
            authWrapper.classList.add('register-active');
        });
    }
    
    if (showLoginBtn) {
        showLoginBtn.addEventListener('click', function() {
            clearOppositeForm(false); // false = going to login
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