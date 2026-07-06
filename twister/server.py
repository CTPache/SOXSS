from aiohttp import web
import asyncio
from datetime import datetime, timedelta
import json
import os
import secrets
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

STATIC_DIR = os.path.join(os.path.dirname(__file__))
REGISTRY_DIR = os.path.join(STATIC_DIR, 'registry')
USERS_FILE = os.path.join(REGISTRY_DIR, 'user_registry.json')
POSTS_FILE = os.path.join(REGISTRY_DIR, 'posts_registry.json')
SESSIONS_FILE = os.path.join(REGISTRY_DIR, 'session_registry.json')
LOCK = asyncio.Lock()
USER_COOKIE_NAME = 'name'
SESSION_COOKIE_NAME = 'session_token'
DEFAULT_PAGE_SIZE = 6

DEFAULT_USERS = [
    {
        'username': 'alice',
        'password': 'alice123',
        'displayName': 'Alice Rivera',
        'bio': 'Frontend engineer who posts about product launches and UI details.',
        'avatarColor': '#1f7aec',
        'joinedAt': '2026-01-12T10:00:00',
    },
    {
        'username': 'bob',
        'password': 'bob123',
        'displayName': 'Bob Chen',
        'bio': 'Backend developer building APIs, queues, and observability dashboards.',
        'avatarColor': '#137333',
        'joinedAt': '2026-02-03T09:15:00',
    },
    {
        'username': 'carol',
        'password': 'carol123',
        'displayName': 'Carol Vega',
        'bio': 'Security analyst sharing notes about testing, hardening, and sessions.',
        'avatarColor': '#b54708',
        'joinedAt': '2026-03-22T16:20:00',
    },
]

DEFAULT_POSTS = [
    {
        'id': 1,
        'username': 'alice',
        'content': 'Shipped the new onboarding flow today. The retention bump looks promising.',
        'createdAt': '2026-05-20T18:10:00',
        'likes': 14,
    },
    {
        'id': 2,
        'username': 'bob',
        'content': 'API pagination is one of those things that seems simple until you need it to be correct.',
        'createdAt': '2026-05-20T19:05:00',
        'likes': 21,
    },
    {
        'id': 3,
        'username': 'carol',
        'content': 'Session handling is much easier to reason about when the server owns token issuance.',
        'createdAt': '2026-05-21T08:40:00',
        'likes': 33,
    },
    {
        'id': 4,
        'username': 'alice',
        'content': 'Dark mode? Yes. Also making the dashboard responsive for smaller screens.',
        'createdAt': '2026-05-21T13:25:00',
        'likes': 18,
    },
    {
        'id': 5,
        'username': 'bob',
        'content': 'Working on a feed endpoint that returns stable pages even while new posts arrive.',
        'createdAt': '2026-05-22T11:00:00',
        'likes': 9,
    },
    {
        'id': 6,
        'username': 'carol',
        'content': 'Test apps should still feel like real products. Tiny details help a lot.',
        'createdAt': '2026-05-22T14:50:00',
        'likes': 27,
    },
    {
        'id': 7,
        'username': 'alice',
        'content': 'Today I switched the home screen to use server-rendered session data on first load.',
        'createdAt': '2026-05-23T09:30:00',
        'likes': 24,
    },
    {
        'id': 8,
        'username': 'bob',
        'content': 'A small demo can still exercise auth, sessions, pagination, and state restoration.',
        'createdAt': '2026-05-24T15:45:00',
        'likes': 11,
    },
    {
        'id': 9,
        'username': 'carol',
        'content': 'Login/register endpoints are cleaner when they both return the same session payload shape.',
        'createdAt': '2026-05-25T07:20:00',
        'likes': 31,
    },
]


def load_json_file(path, fallback):
    if not os.path.isfile(path):
        return fallback
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            data = json.load(handle)
        return data if data is not None else fallback
    except Exception:
        return fallback



def save_json_file(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)



def load_users_sync():
    users = load_json_file(USERS_FILE, [])
    return users if isinstance(users, list) else []



def save_users_sync(users):
    save_json_file(USERS_FILE, users)



def load_posts_sync():
    posts = load_json_file(POSTS_FILE, [])
    return posts if isinstance(posts, list) else []



def save_posts_sync(posts):
    save_json_file(POSTS_FILE, posts)



def load_sessions_sync():
    sessions = load_json_file(SESSIONS_FILE, {'byToken': {}, 'byUser': {}})
    if not isinstance(sessions, dict):
        return {'byToken': {}, 'byUser': {}}
    by_token = sessions.get('byToken', {})
    by_user = sessions.get('byUser', {})
    return {
        'byToken': by_token if isinstance(by_token, dict) else {},
        'byUser': by_user if isinstance(by_user, dict) else {},
    }



def save_sessions_sync(sessions):
    save_json_file(SESSIONS_FILE, sessions)



def seed_if_needed():
    users = load_users_sync()
    if not users:
        save_users_sync(DEFAULT_USERS)
        users = load_users_sync()

    posts = load_posts_sync()
    if not posts:
        save_posts_sync(DEFAULT_POSTS)

    sessions_file_exists = os.path.isfile(SESSIONS_FILE)
    sessions = load_sessions_sync()
    if (not sessions_file_exists) or 'byToken' not in sessions or 'byUser' not in sessions:
        save_sessions_sync({'byToken': {}, 'byUser': {}})



def now_iso():
    return datetime.now().isoformat(timespec='seconds')



def issue_token():
    return secrets.token_urlsafe(32)



def token_max_age(remember):
    return 60 * 60 * 24 * 30 if remember else 60 * 60 * 12



def session_expires_at(remember):
    return (datetime.now() + (timedelta(days=30) if remember else timedelta(hours=12))).isoformat(timespec='seconds')



def public_user(user):
    return {
        'username': user['username'],
        'displayName': user.get('displayName', user['username']),
        'bio': user.get('bio', ''),
        'avatarColor': user.get('avatarColor', '#1f7aec'),
        'joinedAt': user.get('joinedAt', now_iso()),
    }



def public_post(post, users_index):
    user = users_index.get(post['username'], {})
    return {
        'id': post['id'],
        'username': post['username'],
        'displayName': user.get('displayName', post['username']),
        'avatarColor': user.get('avatarColor', '#64748b'),
        'content': post['content'],
        'createdAt': post['createdAt'],
        'likes': post.get('likes', 0),
    }



def users_index_by_username(users):
    return {user['username'].lower(): user for user in users}



def public_users_list(users):
    return [public_user(user) for user in users]



def current_session_from_request(request):
    return request.cookies.get(SESSION_COOKIE_NAME, '')


def parse_positive_int(raw_value, fallback):
    try:
        value = int(raw_value)
        return value if value > 0 else fallback
    except Exception:
        return fallback


@web.middleware
async def cors_middleware(request, handler):
    # Reply directly to preflight checks so every endpoint is CORS-accessible.
    if request.method == 'OPTIONS':
        response = web.Response(status=200)
    else:
        response = await handler(request)

    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'
    response.headers['Access-Control-Max-Age'] = '86400'
    return response


async def read_state():
    async with LOCK:
        return {
            'users': load_users_sync(),
            'posts': load_posts_sync(),
            'sessions': load_sessions_sync(),
        }


async def write_state(users=None, posts=None, sessions=None):
    async with LOCK:
        if users is not None:
            save_users_sync(users)
        if posts is not None:
            save_posts_sync(posts)
        if sessions is not None:
            save_sessions_sync(sessions)


async def issue_session(user, remember, metadata=None):
    state = await read_state()
    sessions = state['sessions']
    token = issue_token()
    user_key = user['username'].lower()

    previous_token = sessions['byUser'].get(user_key)
    if previous_token:
        sessions['byToken'].pop(previous_token, None)

    payload = {
        'user': user['username'],
        'displayName': user.get('displayName', user['username']),
        'token': token,
        'remember': remember,
        'createdAt': now_iso(),
        'lastSeen': now_iso(),
        'expiresAt': session_expires_at(remember),
    }
    if metadata:
        payload.update(metadata)

    sessions['byToken'][token] = payload
    sessions['byUser'][user_key] = token
    await write_state(sessions=sessions)
    return payload


async def invalidate_session(token):
    state = await read_state()
    sessions = state['sessions']
    session = sessions['byToken'].pop(token, None)
    if session:
        sessions['byUser'].pop(str(session.get('user', '')).lower(), None)
        await write_state(sessions=sessions)
    return session


async def get_active_session(request):
    token = current_session_from_request(request)
    if not token:
        return None

    state = await read_state()
    sessions = state['sessions']
    session = sessions['byToken'].get(token)
    if not session:
        return None

    expires_at = session.get('expiresAt')
    if expires_at:
        try:
            if datetime.fromisoformat(expires_at) < datetime.now():
                await invalidate_session(token)
                return None
        except Exception:
            pass

    session['lastSeen'] = now_iso()
    sessions['byToken'][token] = session
    await write_state(sessions=sessions)
    return session


async def set_session_cookies(response, user, token, remember):
    response.set_cookie(
        USER_COOKIE_NAME,
        user,
        path='/',
        max_age=token_max_age(remember),
        samesite='Lax',
    )
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        path='/',
        max_age=token_max_age(remember),
        samesite='Lax',
        httponly=True,
    )


async def handle_auth_register(request):
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({'error': 'Invalid JSON body'}, status=400)

    username = str(payload.get('username', '')).strip().lower()
    password = str(payload.get('password', '')).strip()
    display_name = str(payload.get('displayName', '')).strip() or username.title()
    bio = str(payload.get('bio', '')).strip()
    remember = bool(payload.get('remember', False))

    if not username or not password:
        return web.json_response({'error': 'Username and password are required'}, status=400)

    state = await read_state()
    users = state['users']
    if any(user['username'].lower() == username for user in users):
        return web.json_response({'error': 'Username already exists'}, status=409)

    user = {
        'username': username,
        'password': password,
        'displayName': display_name,
        'bio': bio,
        'avatarColor': payload.get('avatarColor') or '#1f7aec',
        'joinedAt': now_iso(),
    }
    users.insert(0, user)
    await write_state(users=users)

    session = await issue_session(user, remember, {'action': 'register'})
    response = web.json_response({'user': public_user(user), 'session': session})
    await set_session_cookies(response, user['username'], session['token'], remember)
    response.headers['X-Session-Token'] = session['token']
    return response


async def handle_auth_login(request):
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({'error': 'Invalid JSON body'}, status=400)

    username = str(payload.get('username', '')).strip().lower()
    password = str(payload.get('password', '')).strip()
    remember = bool(payload.get('remember', False))

    state = await read_state()
    users = state['users']
    user = next((item for item in users if item['username'].lower() == username), None)
    if not user or user.get('password', '') != password:
        return web.json_response({'error': 'Invalid credentials'}, status=401)

    session = await issue_session(user, remember, {'action': 'login'})
    response = web.json_response({'user': public_user(user), 'session': session})
    await set_session_cookies(response, user['username'], session['token'], remember)
    response.headers['X-Session-Token'] = session['token']
    return response


async def handle_auth_logout(request):
    token = current_session_from_request(request)
    if token:
        await invalidate_session(token)
    response = web.json_response({'ok': True})
    response.del_cookie(USER_COOKIE_NAME, path='/')
    response.del_cookie(SESSION_COOKIE_NAME, path='/')
    return response


async def handle_session(request):
    session = await get_active_session(request)
    if not session:
        return web.json_response({'active': False}, status=404)

    state = await read_state()
    user = next((item for item in state['users'] if item['username'].lower() == str(session.get('user', '')).lower()), None)
    return web.json_response({
        'active': True,
        'session': session,
        'user': public_user(user) if user else None,
    })


async def handle_me(request):
    session = await get_active_session(request)
    if not session:
        return web.json_response({'error': 'Not authenticated'}, status=401)

    state = await read_state()
    users = state['users']
    posts = state['posts']
    username = str(session.get('user', '')).lower()
    user = next((item for item in users if item['username'].lower() == username), None)
    if not user:
        return web.json_response({'error': 'User not found'}, status=404)

    user_posts = [post for post in posts if post['username'].lower() == username]
    user_posts.sort(key=lambda item: item['createdAt'], reverse=True)

    return web.json_response({
        'user': public_user(user),
        'session': session,
        'stats': {
            'postsCount': len(user_posts),
            'followers': 42,
            'following': 18,
        },
        'posts': [public_post(post, users_index_by_username(users)) for post in user_posts],
    })


async def handle_update_me(request):
    session = await get_active_session(request)
    if not session:
        return web.json_response({'error': 'Not authenticated'}, status=401)

    try:
        payload = await request.json()
    except Exception:
        return web.json_response({'error': 'Invalid JSON body'}, status=400)

    state = await read_state()
    users = state['users']
    username = str(session.get('user', '')).lower()
    user = next((item for item in users if item['username'].lower() == username), None)
    if not user:
        return web.json_response({'error': 'User not found'}, status=404)

    display_name = str(payload.get('displayName', user.get('displayName', user['username']))).strip()
    bio = str(payload.get('bio', user.get('bio', ''))).strip()
    avatar_color = str(payload.get('avatarColor', user.get('avatarColor', '#1f7aec'))).strip()

    user['displayName'] = display_name or user['username']
    user['bio'] = bio[:240]
    user['avatarColor'] = avatar_color if avatar_color.startswith('#') and len(avatar_color) in (4, 7) else user.get('avatarColor', '#1f7aec')
    await write_state(users=users)

    refreshed_session = await issue_session(user, bool(session.get('remember', False)), {'action': 'profile-update'})
    response = web.json_response({'user': public_user(user), 'session': refreshed_session})
    await set_session_cookies(response, user['username'], refreshed_session['token'], bool(refreshed_session.get('remember', False)))
    response.headers['X-Session-Token'] = refreshed_session['token']
    return response


async def handle_users(request):
    state = await read_state()
    users = state['users']
    if request.method == 'GET':
        return web.json_response(public_users_list(users))

    return web.Response(status=405, text='Method not allowed')


async def handle_user_detail(request):
    username = str(request.match_info.get('username', '')).strip().lower()
    state = await read_state()
    users = state['users']
    posts = state['posts']
    user = next((item for item in users if item['username'].lower() == username), None)
    if not user:
        return web.json_response({'error': 'User not found'}, status=404)

    user_posts = [post for post in posts if post['username'].lower() == username]
    user_posts.sort(key=lambda item: item['createdAt'], reverse=True)
    return web.json_response({
        'user': public_user(user),
        'posts': [public_post(post, users_index_by_username(users)) for post in user_posts],
    })


async def handle_user_posts(request):
    username = str(request.match_info.get('username', '')).strip().lower()
    state = await read_state()
    users = state['users']
    posts = state['posts']
    user = next((item for item in users if item['username'].lower() == username), None)
    if not user:
        return web.json_response({'error': 'User not found'}, status=404)

    user_posts = [post for post in posts if post['username'].lower() == username]
    user_posts.sort(key=lambda item: item['createdAt'], reverse=True)
    return web.json_response({
        'user': public_user(user),
        'items': [public_post(post, users_index_by_username(users)) for post in user_posts],
        'total': len(user_posts),
    })


async def handle_posts(request):
    state = await read_state()
    users = state['users']
    posts = state['posts']
    users_index = users_index_by_username(users)

    if request.method == 'GET':
        username = str(request.query.get('username', '')).strip().lower()
        filtered = posts
        if username:
            filtered = [post for post in posts if post['username'].lower() == username]
        filtered = sorted(filtered, key=lambda item: item['createdAt'], reverse=True)
        return web.json_response({'items': [public_post(post, users_index) for post in filtered]})

    if request.method == 'POST':
        session = await get_active_session(request)
        if not session:
            return web.json_response({'error': 'Not authenticated'}, status=401)
        try:
            payload = await request.json()
        except Exception:
            return web.json_response({'error': 'Invalid JSON body'}, status=400)

        content = str(payload.get('content', '')).strip()
        if not content:
            return web.json_response({'error': 'Content is required'}, status=400)

        next_id = (max((post['id'] for post in posts), default=0) + 1)
        post = {
            'id': next_id,
            'username': str(session.get('user', '')).lower(),
            'content': content[:280],
            'createdAt': now_iso(),
            'likes': 0,
        }
        posts.insert(0, post)
        await write_state(posts=posts)
        return web.json_response({'post': public_post(post, users_index)})

    return web.Response(status=405, text='Method not allowed')


async def handle_feed(request):
    state = await read_state()
    users = state['users']
    posts = state['posts']
    users_index = users_index_by_username(users)

    page = parse_positive_int(request.query.get('page', '1') or '1', 1)
    page_size = parse_positive_int(request.query.get('pageSize', str(DEFAULT_PAGE_SIZE)) or str(DEFAULT_PAGE_SIZE), DEFAULT_PAGE_SIZE)
    ordered_posts = sorted(posts, key=lambda item: item['createdAt'], reverse=True)
    total = len(ordered_posts)
    total_pages = max((total + page_size - 1) // page_size, 1) if total else 1
    start = (page - 1) * page_size
    end = start + page_size
    page_items = ordered_posts[start:end]

    return web.json_response({
        'items': [public_post(post, users_index) for post in page_items],
        'page': page,
        'pageSize': page_size,
        'total': total,
        'totalPages': total_pages,
        'hasNext': page < total_pages,
        'hasPrev': page > 1,
    })


async def handle_static(request):
    rel_path = request.match_info.get('filename', '')
    file_path = os.path.join(STATIC_DIR, rel_path)
    if rel_path == '':
        file_path = os.path.join(STATIC_DIR, 'index.html')
    if not os.path.isfile(file_path):
        return web.Response(status=404, text='Not found')
    return web.FileResponse(file_path, headers={'Access-Control-Allow-Origin': '*'})


async def handle_login_page(request):
    return web.FileResponse(os.path.join(STATIC_DIR, 'index.html'))


async def handle_feed_page(request):
    return web.FileResponse(os.path.join(STATIC_DIR, 'feed.html'))


async def handle_profile_page(request):
    return web.FileResponse(os.path.join(STATIC_DIR, 'profile.html'))


def setup_routes(app):
    app.router.add_post('/api/auth/register', handle_auth_register)
    app.router.add_post('/api/auth/login', handle_auth_login)
    app.router.add_post('/api/auth/logout', handle_auth_logout)
    app.router.add_get('/api/session', handle_session)
    app.router.add_get('/api/me', handle_me)
    app.router.add_put('/api/me', handle_update_me)
    app.router.add_get('/api/users', handle_users)
    app.router.add_get('/api/users/{username}', handle_user_detail)
    app.router.add_get('/api/users/{username}/posts', handle_user_posts)
    app.router.add_get('/api/posts', handle_posts)
    app.router.add_post('/api/posts', handle_posts)
    app.router.add_get('/api/feed', handle_feed)
    app.router.add_get('/', handle_login_page)
    app.router.add_get('/feed', handle_feed_page)
    app.router.add_get('/profile', handle_profile_page)
    app.router.add_get('/profile/{username}', handle_profile_page)
    app.router.add_get('/{filename:.*}', handle_static)


async def start_async_server():
    seed_if_needed()
    app = web.Application(middlewares=[cors_middleware])
    setup_routes(app)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 7070)
    await site.start()
    print('HTTP server running at http://0.0.0.0:7070/')
    while True:
        await asyncio.sleep(3600)


if __name__ == '__main__':
    asyncio.run(start_async_server())
