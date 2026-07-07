(() => {
const state = {
    session: null,
    currentUser: null,
    viewedUser: null,
    isOwnProfile: false,
};

const dom = {
    headerSessionUser: document.getElementById('headerSessionUser'),
    profileTitle: document.getElementById('profileTitle'),
    profileAvatar: document.getElementById('profileAvatar'),
    profileName: document.getElementById('profileName'),
    profileHandle: document.getElementById('profileHandle'),
    profileBio: document.getElementById('profileBio'),
    profileJoined: document.getElementById('profileJoined'),
    profilePostsCount: document.getElementById('profilePostsCount'),
    profileMode: document.getElementById('profileMode'),
    profileFeedback: document.getElementById('profileFeedback'),
    editCard: document.getElementById('editCard'),
    editForm: document.getElementById('editForm'),
    editDisplayName: document.getElementById('editDisplayName'),
    editBio: document.getElementById('editBio'),
    editAvatarColor: document.getElementById('editAvatarColor'),
    editFeedback: document.getElementById('editFeedback'),
    passwordForm: document.getElementById('passwordForm'),
    currentPassword: document.getElementById('currentPassword'),
    newPassword: document.getElementById('newPassword'),
    confirmPassword: document.getElementById('confirmPassword'),
    passwordFeedback: document.getElementById('passwordFeedback'),
    userPostsList: document.getElementById('userPostsList'),
    postTemplate: document.getElementById('postTemplate'),
    headerLogoutButton: document.getElementById('headerLogoutButton'),
    homeNavLink: document.getElementById('homeNavLink'),
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

function formatDate(value) {
    if (!value) return '-';
    return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
}

function initialsFromUser(user) {
    const source = user?.displayName || user?.username || 'U';
    return source
        .split(/\s+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((part) => part[0])
        .join('')
        .toUpperCase();
}

function decorateAvatar(node, user) {
    node.textContent = initialsFromUser(user);
    node.style.background = user.avatarColor || '#2563eb';
}

function createPostNode(post) {
    const fragment = dom.postTemplate.content.cloneNode(true);
    const avatar = fragment.querySelector('.avatar');
    const timeNode = fragment.querySelector('.post-time');
    const nameLink = fragment.querySelector('.post-name');
    nameLink.textContent = post.displayName || post.username;
    nameLink.href = `/profile/${encodeURIComponent(post.username)}`;
    fragment.querySelector('.post-handle').textContent = `@${post.username}`;
    timeNode.setAttribute('datetime', post.createdAt || '2000-01-01T00:00:00Z');
    timeNode.textContent = formatDate(post.createdAt);
    fragment.querySelector('.post-content').textContent = post.content;
    fragment.querySelector('.post-likes').textContent = `${post.likes || 0} likes`;
    decorateAvatar(avatar, post);
    return fragment;
}

function renderPosts(posts) {
    dom.userPostsList.innerHTML = '';
    if (!posts.length) {
        dom.userPostsList.innerHTML = '<article class="post-card"><p class="post-content">Este usuario aún no tiene posts.</p></article>';
        return;
    }
    for (const post of posts) {
        dom.userPostsList.appendChild(createPostNode(post));
    }
}

function resolveViewedUsername() {
    const pathParts = window.location.pathname.split('/').filter(Boolean);
    if (pathParts.length >= 2 && pathParts[0] === 'profile') {
        return decodeURIComponent(pathParts[1]).toLowerCase();
    }
    const queryUsername = new URLSearchParams(window.location.search).get('u');
    return queryUsername ? queryUsername.toLowerCase() : '';
}

async function loadSession() {
    try {
        const sessionState = await apiFetch('/api/session');
        state.session = sessionState.session;
        state.currentUser = sessionState.user;
        if (dom.headerSessionUser) {
            dom.headerSessionUser.textContent = `@${state.currentUser.username}`;
            dom.headerSessionUser.classList.remove('hidden');
        }
        dom.headerLogoutButton.classList.remove('hidden');
        dom.homeNavLink.href = '/feed';
    } catch {
        window.location.href = '/';
        return false;
    }
    return true;
}

async function handleLogout() {
    try {
        await apiFetch('/api/auth/logout', { method: 'POST', body: '{}' });
    } finally {
        window.location.href = '/';
    }
}

function renderProfileBasics(user, postsTotal) {
    dom.profileTitle.textContent = `Perfil de @${user.username}`;
    dom.profileName.textContent = user.displayName || user.username;
    dom.profileHandle.textContent = `@${user.username}`;
    dom.profileBio.textContent = user.bio || 'Sin bio';
    dom.profileJoined.textContent = formatDate(user.joinedAt);
    dom.profilePostsCount.textContent = String(postsTotal || 0);
    dom.profileMode.textContent = state.isOwnProfile ? 'Edición' : 'Lectura';
    decorateAvatar(dom.profileAvatar, user);
}

function renderEditMode() {
    if (!state.isOwnProfile) {
        dom.editCard.classList.add('hidden');
        setFeedback(dom.profileFeedback, 'Perfil en modo lectura. Solo el propietario puede editar.', false);
        return;
    }
    dom.editCard.classList.remove('hidden');
    dom.editDisplayName.value = state.viewedUser.displayName || '';
    dom.editBio.value = state.viewedUser.bio || '';
    dom.editAvatarColor.value = state.viewedUser.avatarColor || '#1f7aec';
    setFeedback(dom.profileFeedback, 'Puedes editar este perfil porque es tuyo.', false);
}

async function loadProfile() {
    const requestedUsername = resolveViewedUsername();
    let targetUsername = requestedUsername;

    if (!targetUsername && state.currentUser?.username) {
        targetUsername = state.currentUser.username.toLowerCase();
    }

    if (!targetUsername) {
        state.viewedUser = null;
        dom.editCard.classList.add('hidden');
        renderPosts([]);
        setFeedback(dom.profileFeedback, 'Inicia sesión para ver tu perfil o usa /profile/{usuario}.', true);
        return;
    }

    const data = await apiFetch(`/api/users/${encodeURIComponent(targetUsername)}`);
    state.viewedUser = data.user;
    state.isOwnProfile = Boolean(state.currentUser && state.currentUser.username.toLowerCase() === data.user.username.toLowerCase());
    renderProfileBasics(data.user, (data.posts || []).length);
    renderPosts(data.posts || []);
    renderEditMode();
}

async function handleEditSubmit(event) {
    event.preventDefault();
    if (!state.isOwnProfile) {
        setFeedback(dom.editFeedback, 'No tienes permisos para editar este perfil.', true);
        return;
    }

    const payload = {
        displayName: dom.editDisplayName.value.trim(),
        bio: dom.editBio.value.trim(),
        avatarColor: dom.editAvatarColor.value.trim(),
    };

    setFeedback(dom.editFeedback, 'Guardando...', false);
    try {
        const updated = await apiFetch('/api/me', {
            method: 'PUT',
            body: JSON.stringify(payload),
        });
        state.currentUser = updated.user;
        setFeedback(dom.editFeedback, 'Perfil actualizado.', false);
        await loadProfile();
    } catch (error) {
        setFeedback(dom.editFeedback, error.message, true);
    }
}

async function handlePasswordSubmit(event) {
    event.preventDefault();
    if (!state.isOwnProfile) {
        setFeedback(dom.passwordFeedback, 'No tienes permisos para cambiar esta contraseña.', true);
        return;
    }

    const currentPassword = dom.currentPassword.value.trim();
    const newPassword = dom.newPassword.value.trim();
    const confirmPassword = dom.confirmPassword.value.trim();

    if (!currentPassword || !newPassword || !confirmPassword) {
        setFeedback(dom.passwordFeedback, 'Completa todos los campos de contraseña.', true);
        return;
    }
    if (newPassword.length < 6) {
        setFeedback(dom.passwordFeedback, 'La nueva contraseña debe tener al menos 6 caracteres.', true);
        return;
    }
    if (newPassword !== confirmPassword) {
        setFeedback(dom.passwordFeedback, 'La confirmación no coincide con la nueva contraseña.', true);
        return;
    }

    setFeedback(dom.passwordFeedback, 'Actualizando contraseña...', false);
    try {
        const updated = await apiFetch('/api/me/password', {
            method: 'PUT',
            body: JSON.stringify({
                currentPassword,
                newPassword,
                confirmPassword,
            }),
        });
        if (updated.session) {
            state.session = updated.session;
        }
        dom.passwordForm.reset();
        setFeedback(dom.passwordFeedback, 'Contraseña actualizada correctamente.', false);
    } catch (error) {
        setFeedback(dom.passwordFeedback, error.message, true);
    }
}

function wireEvents() {
    dom.editForm.addEventListener('submit', handleEditSubmit);
    dom.passwordForm.addEventListener('submit', handlePasswordSubmit);
    dom.headerLogoutButton.addEventListener('click', handleLogout);
}

async function main() {
    wireEvents();
    const hasSession = await loadSession();
    if (!hasSession) {
        return;
    }
    await loadProfile();
}

main().catch((error) => {
    console.error(error);
    setFeedback(dom.profileFeedback, 'No se pudo cargar el perfil.', true);
});

})();
