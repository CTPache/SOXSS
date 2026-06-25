(() => {
const state = {
    user: null,
    session: null,
    page: 1,
    totalPages: 1,
    pageSize: 6,
};

const dom = {
    headerSessionUser: document.getElementById('headerSessionUser'),
    headerLogoutButton: document.getElementById('headerLogoutButton'),
    homeNavLink: document.getElementById('homeNavLink'),
    composerCard: document.getElementById('composerCard'),
    postForm: document.getElementById('postForm'),
    postContentInput: document.getElementById('postContentInput'),
    characterCount: document.getElementById('characterCount'),
    postFeedback: document.getElementById('postFeedback'),
    feedList: document.getElementById('feedList'),
    pageBadge: document.getElementById('pageBadge'),
    pagerLabel: document.getElementById('pagerLabel'),
    prevPageButton: document.getElementById('prevPageButton'),
    nextPageButton: document.getElementById('nextPageButton'),
    postTemplate: document.getElementById('postTemplate'),
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
    fragment.querySelector('.post-content').innerHTML = post.content;
    decorateAvatar(avatar, post);
    return fragment;
}

function renderPosts(posts) {
    dom.feedList.innerHTML = '';
    if (!posts.length) {
        dom.feedList.innerHTML = '<article class="post-card"><p class="post-content">No hay posts.</p></article>';
        return;
    }
    for (const post of posts) {
        dom.feedList.appendChild(createPostNode(post));
    }
}

function renderSession() {
    if (!state.session || !state.user) {
        dom.composerCard.classList.add('hidden');
        if (dom.headerSessionUser) {
            dom.headerSessionUser.classList.add('hidden');
            dom.headerSessionUser.textContent = '@-';
        }
        if (dom.headerLogoutButton) {
            dom.headerLogoutButton.classList.add('hidden');
        }
        if (dom.homeNavLink) {
            dom.homeNavLink.href = '/';
        }
        setFeedback(dom.postFeedback, 'Inicia sesión para publicar.', false);
        return;
    }
    if (dom.headerSessionUser) {
        dom.headerSessionUser.textContent = `@${state.user.username}`;
        dom.headerSessionUser.classList.remove('hidden');
    }
    dom.composerCard.classList.remove('hidden');
    if (dom.headerLogoutButton) {
        dom.headerLogoutButton.classList.remove('hidden');
    }
    if (dom.homeNavLink) {
        dom.homeNavLink.href = '/feed';
    }
}

async function loadSession() {
    try {
        const result = await apiFetch('/api/session');
        state.session = result.session;
        state.user = result.user;
    } catch {
        window.location.href = '/';
        return false;
    }
    renderSession();
    return true;
}

async function loadFeed() {
    const feed = await apiFetch(`/api/feed?page=${state.page}&pageSize=${state.pageSize}`);
    state.totalPages = feed.totalPages || 1;
    dom.pageBadge.textContent = `${feed.page} / ${state.totalPages}`;
    dom.pagerLabel.textContent = `Página ${feed.page} de ${state.totalPages}`;
    dom.prevPageButton.disabled = !feed.hasPrev;
    dom.nextPageButton.disabled = !feed.hasNext;
    renderPosts(feed.items || []);
}

async function handlePostSubmit(event) {
    event.preventDefault();
    if (!state.user) {
        setFeedback(dom.postFeedback, 'Debes iniciar sesión.', true);
        return;
    }
    const content = dom.postContentInput.value.trim();
    if (!content) {
        setFeedback(dom.postFeedback, 'Escribe contenido antes de publicar.', true);
        return;
    }
    setFeedback(dom.postFeedback, 'Publicando...', false);
    try {
        await apiFetch('/api/posts', {
            method: 'POST',
            body: JSON.stringify({ content }),
        });
        dom.postContentInput.value = '';
        dom.characterCount.textContent = '0 / 280';
        state.page = 1;
        await loadFeed();
        setFeedback(dom.postFeedback, 'Post publicado.', false);
    } catch (error) {
        setFeedback(dom.postFeedback, error.message, true);
    }
}

async function handleLogout() {
    if (!state.session) {
        return;
    }
    try {
        await apiFetch('/api/auth/logout', { method: 'POST', body: '{}' });
    } finally {
        window.location.href = '/';
    }
}

function wireEvents() {
    dom.postForm.addEventListener('submit', handlePostSubmit);
    if (dom.headerLogoutButton) {
        dom.headerLogoutButton.addEventListener('click', handleLogout);
    }
    dom.prevPageButton.addEventListener('click', async () => {
        if (state.page > 1) {
            state.page -= 1;
            await loadFeed();
        }
    });
    dom.nextPageButton.addEventListener('click', async () => {
        if (state.page < state.totalPages) {
            state.page += 1;
            await loadFeed();
        }
    });
    dom.postContentInput.addEventListener('input', () => {
        dom.characterCount.textContent = `${dom.postContentInput.value.length} / 280`;
    });
}

async function main() {
    wireEvents();
    const hasSession = await loadSession();
    if (!hasSession) {
        return;
    }
    await loadFeed();
}

main().catch((error) => {
    console.error(error);
    setFeedback(dom.postFeedback, 'No se pudo cargar el feed.', true);
});

})();
