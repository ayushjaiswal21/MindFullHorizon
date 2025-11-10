
// Enhanced interactions
document.addEventListener('DOMContentLoaded', function() {
    // Password confirmation validation
    document.getElementById('confirm_password').addEventListener('input', function() {
        const password = document.getElementById('password').value;
        const confirmPassword = this.value;

        if (password !== confirmPassword) {
            this.setCustomValidity('Passwords do not match');
            this.classList.add('border-red-300');
            this.classList.remove('border-green-300');
        } else {
            this.setCustomValidity('');
            this.classList.remove('border-red-300');
            this.classList.add('border-green-300');
        }
    });

    // Password strength indicator
    document.getElementById('password').addEventListener('input', function() {
        const password = this.value;
        const strength = getPasswordStrength(password);

        if (password.length > 0 && password.length < 6) {
            this.setCustomValidity('Password must be at least 6 characters long');
            this.classList.add('border-red-300');
        } else {
            this.setCustomValidity('');
            this.classList.remove('border-red-300');
            this.classList.add('border-green-300');
        }

        // Update form sections on role change
        document.getElementById('role').addEventListener('change', function() {
            const roleCards = document.querySelectorAll('.group');
            roleCards.forEach(card => {
                card.classList.add('animate-pulse');
                setTimeout(() => card.classList.remove('animate-pulse'), 500);
            });
        });
    });

    // Add smooth scroll behavior for internal links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
});

function getPasswordStrength(password) {
    let strength = 0;
    if (password.length >= 6) strength++;
    if (password.match(/[a-z]/)) strength++;
    if (password.match(/[A-Z]/)) strength++;
    if (password.match(/[0-9]/)) strength++;
    if (password.match(/[^a-zA-Z0-9]/)) strength++;
    return strength;
}
