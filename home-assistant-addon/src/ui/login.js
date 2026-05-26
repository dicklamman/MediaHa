// Check if already authenticated - redirect to main app
async function checkAuthStatus() {
    try {
        const response = await fetch('/api/auth/status');
        if (response.ok) {
            const data = await response.json();
            if (data.authenticated) {
                window.location.href = '/';
                return false;
            }
        }
    } catch (e) {
        // Ignore errors, show login page
    }
    return true;
}

document.addEventListener('DOMContentLoaded', async () => {
    const form = document.getElementById('login-form');
    const errorBox = document.getElementById('login-error');
    const submitBtn = form?.querySelector('.auth-submit');

    if (!form) return;

    // If already authenticated, redirect to main app
    const canShowLogin = await checkAuthStatus();
    if (!canShowLogin) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!submitBtn) return;

        const username = form.username.value.trim();
        const password = form.password.value;

        errorBox.textContent = '';
        submitBtn.disabled = true;
        submitBtn.classList.add('loading');

        try {
            const res = await fetch('/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });

            if (res.ok) {
                // On success, go to main app
                window.location.href = '/';
                return;
            }

            const data = await res.json().catch(() => ({}));
            errorBox.textContent = data.error || 'Login failed. Please check your credentials.';
        } catch (err) {
            errorBox.textContent = 'Unable to reach server. Please try again.';
        } finally {
            submitBtn.disabled = false;
            submitBtn.classList.remove('loading');
        }
    });
});

