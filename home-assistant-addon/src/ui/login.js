// Login page - server handles auth redirect

document.addEventListener('DOMContentLoaded', async () => {
    const form = document.getElementById('login-form');
    const errorBox = document.getElementById('login-error');
    const submitBtn = form?.querySelector('.auth-submit');

    if (!form) return;

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

