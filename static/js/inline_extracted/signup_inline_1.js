document.addEventListener('DOMContentLoaded', function() {
    const password = document.getElementById('password');
    const confirm = document.getElementById('confirm_password');
    const invite = document.getElementById('invite_code');
    const role = document.getElementById('role');

    // Browser-side hint only; the server enforces the real password rules.
    function checkMatch() {
        const same = password.value === confirm.value;
        confirm.setCustomValidity(same ? '' : 'Passwords do not match');
        confirm.classList.toggle('border-red-300', !same);
        confirm.classList.toggle('border-green-300', same && confirm.value !== '');
    }
    confirm.addEventListener('input', checkMatch);
    password.addEventListener('input', checkMatch);

    // Counselor sign-up: a non-empty invite code switches the role; the server still checks the code.
    const syncRole = () => { role.value = invite.value.trim() ? 'provider' : 'patient'; };
    invite.addEventListener('input', syncRole);
    invite.form.addEventListener('submit', syncRole);
});
