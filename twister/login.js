(() => {
const state = {
    mode: 'login',
};

const dom = {
    authCard: document.getElementById('authCard'),
    authForm: document.getElementById('authForm'),
    usernameInput: document.getElementById('usernameInput'),
    passwordInput: document.getElementById('passwordInput'),
    displayNameInput: document.getElementById('displayNameInput'),
    bioInput: document.getElementById('bioInput'),
    displayNameField: document.getElementById('displayNameField'),
    rememberInput: document.getElementById('rememberInput'),
    authFeedback: document.getElementById('authFeedback'),
    authSubmitButton: document.getElementById('authSubmitButton'),
    registerModeButton: document.getElementById('registerModeButton'),
    loginModeButton: document.getElementById('loginModeButton'),
    sessionBanner: document.getElementById('sessionBanner'),
    homeNavLink: document.getElementById('homeNavLink')
};

function apiFetch(url, options = {}) {
    const settings = {
        credentials: 'include',
        headers: {
            'Content-Type': 'application/json',
            ...(options.headers || {}),
        },
        ...options,
    };
    return fetch(url, settings).then(async (response) => {
        const contentType = response.headers.get('content-type') || '';
        const payload = contentType.includes('application/json') ? await response.json() : await response.text();
        if (!response.ok) {
            const message = payload && typeof payload === 'object' && payload.error ? payload.error : 'Request failed';
            throw new Error(message);
        }
        return payload;
    });
}

function setFeedback(node, message, isError = false) {
    node.textContent = message;
    node.style.color = isError ? '#b42318' : '#60728a';
}

function setMode(mode) {
    state.mode = mode;
    const isRegister = mode === 'register';
    dom.registerModeButton.classList.toggle('active', isRegister);
    dom.loginModeButton.classList.toggle('active', !isRegister);
    dom.displayNameField.classList.toggle('hidden', !isRegister);
    dom.bioInput.parentElement.classList.toggle('hidden', !isRegister);
    dom.authSubmitButton.textContent = isRegister ? 'Crear cuenta' : 'Entrar';
    setFeedback(dom.authFeedback, isRegister ? 'Crea un usuario para empezar.' : 'Inicia sesión con tu cuenta.', false);
}

async function handleAuthSubmit(event) {
    event.preventDefault();
    setFeedback(dom.authFeedback, 'Procesando...', false);

    const payload = {
        username: dom.usernameInput.value.trim(),
        password: dom.passwordInput.value,
        remember: dom.rememberInput.checked,
    };

    if (state.mode === 'register') {
        payload.displayName = dom.displayNameInput.value.trim();
        payload.bio = dom.bioInput.value.trim();
    }

    const endpoint = state.mode === 'register' ? '/api/auth/register' : '/api/auth/login';
    try {
        const result = await apiFetch(endpoint, {
            method: 'POST',
            body: JSON.stringify(payload),
        });
        const username = result.user?.username || payload.username;
        dom.authForm.reset();
        dom.rememberInput.checked = true;
        setMode('login');
        setFeedback(dom.authFeedback, `Sesión iniciada como @${username}. Redirigiendo al feed...`, false);
        setTimeout(() => {
            window.location.href = '/feed';
        }, 500);
    } catch (error) {
        setFeedback(dom.authFeedback, error.message, true);
    }
}

function wireEvents() {
    dom.registerModeButton.addEventListener('click', () => setMode('register'));
    dom.loginModeButton.addEventListener('click', () => setMode('login'));
    dom.authForm.addEventListener('submit', handleAuthSubmit);
}

async function main() {
    wireEvents();
    setMode('login');
    dom.rememberInput.checked = true;
}

main().catch((error) => {
    console.error(error);
    setFeedback(dom.authFeedback, 'No se pudo iniciar la página.', true);
});

})();
