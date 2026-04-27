if ('serviceWorker' in navigator) navigator.serviceWorker.register("/sw.js");

let movieStack = [];
let swipeHistory = [];
let globalCurrentX = 0;
let plexServerId = null;
let currentGenre = "All";
let isHistoryView = false;
let isSoloMode = false;
let lastSeenMatchTs = null;

const mediaProvider = document.body.dataset.mediaProvider;

function providerToken() {
    return localStorage.getItem('provider_token') || localStorage.getItem('plex_token');
}

function providerUserId() {
    return localStorage.getItem('provider_user_id') || localStorage.getItem('plex_id');
}

function jellyfinAuthorizationHeader(token) {
    return `MediaBrowser Client="JellySwipe", Device="Browser", DeviceId="jelly-swipe-web-v1", Version="1.0.0", Token="${token}"`;
}

function providerIdentityHeaders(extra = {}) {
    const uid = providerUserId();
    const headers = { ...extra };
    if (uid) {
        headers['X-Plex-User-ID'] = uid;
        headers['X-Provider-User-Id'] = uid;
    }
    const tok = providerToken();
    if (mediaProvider === 'jellyfin' && tok) {
        headers['Authorization'] = jellyfinAuthorizationHeader(tok);
    }
    return headers;
}

async function bootstrapJellyfinDelegate() {
    const provRes = await fetch("/auth/provider");
    const provData = await provRes.json();
    if (provData.jellyfin_browser_auth !== "delegate") {
        return false;
    }
    const resp = await fetch("/auth/jellyfin-use-server-identity", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
        credentials: "same-origin",
    });
    const data = await resp.json();
    if (!resp.ok || !data.userId) {
        alert(
            data.error ||
                "Could not use server Jellyfin account. Check server logs and JELLYFIN_* environment variables."
        );
        return false;
    }
    localStorage.removeItem("provider_token");
    localStorage.removeItem("plex_token");
    localStorage.setItem("provider_user_id", data.userId);
    localStorage.setItem("plex_id", data.userId);
    document.getElementById("login-section").classList.add("hidden");
    document.getElementById("main-menu").classList.remove("hidden");
    loadGenres();
    if (localStorage.getItem("active_room")) loadMovies();
    return true;
}

async function fetchAndStoreProviderId() {
    const token = providerToken();
    if (!token) return;
    if (mediaProvider === 'plex') {
        try {
            const res = await fetch(`https://plex.tv/api/v2/user?X-Plex-Token=${token}`, { headers: { 'Accept': 'application/json' } });
            const data = await res.json();
            if (data.id) {
                localStorage.setItem('plex_id', data.id);
                localStorage.setItem('provider_user_id', data.id);
            }
        } catch (e) { console.error("Could not fetch Plex ID"); }
        return;
    }
    const uid = localStorage.getItem('provider_user_id');
    if (uid) localStorage.setItem('plex_id', uid);
}

async function fetchPlexServerId() {
    if (plexServerId) return plexServerId;
    const response = await fetch('/plex/server-info');
    if (response.ok) {
        const data = await response.json();
        plexServerId = data.machineIdentifier;
        return plexServerId;
    }
    return null;
}

async function loginWithPlex() {
    if (mediaProvider === 'jellyfin') {
        const provRes = await fetch("/auth/provider");
        const provData = await provRes.json();
        if (provData.jellyfin_browser_auth === "delegate") {
            await bootstrapJellyfinDelegate();
            return;
        }
        const username = prompt("Jellyfin account name", "");
        if (!username) return;
        const password = prompt("Jellyfin account password", "");
        if (!password) return;
        const resp = await fetch("/auth/jellyfin-login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password })
        });
        const data = await resp.json();
        if (!resp.ok || !data.authToken) {
            alert(data.error || "Jellyfin login failed");
            return;
        }
        localStorage.setItem("provider_token", data.authToken);
        localStorage.setItem("provider_user_id", data.userId);
        localStorage.setItem("plex_token", data.authToken);
        localStorage.setItem("plex_id", data.userId);
        document.getElementById("login-section").classList.add("hidden");
        document.getElementById("main-menu").classList.remove("hidden");
        loadGenres();
        return;
    }
    const resp = await fetch("/auth/plex-url");
    const data = await resp.json();
    window.location.href = data.auth_url;
}

function confirmQuit() {
    document.getElementById('quit-modal').classList.remove('hidden');
}

async function doQuit() {
    await fetch('/room/quit', { method: 'POST' });
    localStorage.removeItem('active_room');
    isSoloMode = false;
    if (sseSource) { sseSource.close(); sseSource = null; }
    location.reload();
}

function toggleGenreModal() { document.getElementById('genre-modal').classList.toggle('hidden'); }

async function selectGenre(genre) {
    document.querySelectorAll('.genre-item').forEach(el => {
        if(el.innerText === genre || (genre === 'All' && el.innerText === 'All Movies')) el.classList.add('active');
        else el.classList.remove('active');
    });
    toggleGenreModal();
    const url = genre === 'All' ? '/movies?genre=All' : `/movies?genre=${encodeURIComponent(genre)}`;
    const res = await fetch(url);
    movieStack = await res.json();
    currentGenre = genre;
    document.getElementById('genre-pill').innerText = genre === 'All' ? 'Genres ▾' : genre + ' ▾';
    swipeHistory = [];
    renderInitialDeck();
}

async function addToWatchlist(event, id) {
    event.stopPropagation();
    const btn = event.currentTarget;
    const originalText = btn.innerText;
    btn.innerText = "ADDING...";
    btn.disabled = true;
    try {
        const res = await fetch("/watchlist/add", {
            method: "POST",
            headers: mediaProvider === 'jellyfin'
                ? providerIdentityHeaders({ "Content-Type": "application/json" })
                : { "Content-Type": "application/json", "X-Plex-Token": providerToken() },
            body: JSON.stringify({ movie_id: id })
        });
        if (res.ok) {
            btn.innerText = "IN WATCHLIST";
            btn.style.borderColor = "#4CAF50"; btn.style.color = "#4CAF50";
        } else {
            btn.innerText = "FAILED";
            setTimeout(() => { btn.innerText = originalText; btn.disabled = false; }, 2000);
        }
    } catch (err) { btn.innerText = "ERROR"; }
}

async function activateSoloMode() {
    const res = await fetch('/room/go-solo', { method: 'POST' });
    if (res.ok) {
        isSoloMode = true;
        loadMovies(true);
    }
}

async function handleSoloToggle(checkbox) {
    const container = checkbox.closest('.session-info-container') || document.getElementById('session-info');
    if (checkbox.checked) {
        container.classList.add('solo-toggle-active');
        await activateSoloMode();
    } else {
        container.classList.remove('solo-toggle-active');
    }
}

const loadMovies = async (solo = false) => {
    isSoloMode = solo;
    lastSeenMatchTs = Date.now() / 1000;
    const res = await fetch('/movies');
    movieStack = await res.json();
    document.getElementById('branding').classList.add('hidden');
    document.getElementById('controls-area').classList.add('hidden');
    document.getElementById('game-area').classList.remove('hidden');
    document.getElementById('matches-pill').classList.remove('hidden');
    document.getElementById('quit-pill').classList.remove('hidden');
    document.getElementById('undo-btn').classList.remove('hidden');

    if (isSoloMode) {
        document.getElementById('matches-pill').innerText = 'Shortlist';
        document.getElementById('solo-badge').classList.remove('hidden');
    } else {
        document.getElementById('matches-pill').innerText = 'Matches';
        document.getElementById('solo-badge').classList.add('hidden');
    }

    renderInitialDeck();
    startPolling();
};

async function openMatches(asHistory) {
    isHistoryView = asHistory;
    const serverId = await fetchPlexServerId();
    if (!serverId) return;
    const label = isSoloMode && !asHistory ? "Your Shortlist" : asHistory ? "Match History" : "Your Matches";
    document.getElementById('modal-title').innerText = label;
    const url = asHistory ? '/matches?view=history' : '/matches';
    const res = await fetch(url, { headers: providerIdentityHeaders() });
    const data = await res.json();
    const list = document.getElementById('matches-list');
    const emptyLabel = asHistory ? 'history' : isSoloMode ? 'shortlist' : 'matches';
    list.innerHTML = data.length ? '' : `<p class="empty-matches-text">No ${emptyLabel} yet</p>`;
    data.forEach(m => {
        const card = document.createElement('div');
        card.className = 'mini-poster';
        const plexLink = `https://app.plex.tv/desktop/#!/server/${serverId}/details?key=%2Flibrary%2Fmetadata%2F${m.movie_id}`;
        const openLabel = mediaProvider === 'jellyfin' ? 'OPEN IN JELLYFIN' : 'OPEN IN PLEX';
        card.innerHTML = `
            <div class="mini-inner">
                <div class="mini-front">
                    <img src="${m.thumb}" alt="${m.title}">
                    <div class="poster-title-overlay">
                       ${m.title}
                   </div>
                </div>
                <div class="mini-back">
                    <div class="mini-title-text">${m.title}</div>
                    <div class="stats-row stats-row-centered">
                        ${m.rating ? `<span class="stat-badge">IMDb ${m.rating}</span>` : ''}
                        ${m.duration ? `<span class="stat-badge">${m.duration}</span>` : ''}
                        ${m.year ? `<span class="stat-badge">${m.year}</span>` : ''}
                    </div>
                    <a href="${plexLink}" class="plex-open-btn" target="_blank" rel="noopener noreferrer">${openLabel}</a>
                    <button class="menu-btn watchlist-btn" data-movie-id="${m.movie_id}">SAVE TO WATCHLIST</button>
                    <button class="menu-btn delete-match-btn" data-movie-id="${m.movie_id}">DELETE</button>
                </div>
            </div>
        `;
        card.onclick = (e) => { if (!e.target.closest('a') && !e.target.closest('button')) card.classList.toggle('flipped'); };
        list.appendChild(card);
    });
    document.getElementById('matches-modal').classList.remove('hidden');
}

let pendingDeleteId = null;

function closeDeleteModal() {
    document.getElementById('delete-modal').classList.add('hidden');
    document.getElementById('delete-modal-overlay').classList.add('hidden');
    pendingDeleteId = null;
}

async function deleteMatch(event, id) {
    event.stopPropagation();
    pendingDeleteId = id;
    document.getElementById('delete-modal-overlay').classList.remove('hidden');
    document.getElementById('delete-modal').classList.remove('hidden');
    document.getElementById('delete-confirm-btn').onclick = async () => {
        await fetch("/matches/delete", { 
            method: "POST", 
            headers: providerIdentityHeaders({"Content-Type": "application/json"}), 
            body: JSON.stringify({ movie_id: pendingDeleteId }) 
        });
        closeDeleteModal();
        openMatches(isHistoryView);
    };
}

function _bindStaticHandlers() {
    const undoBtn = document.getElementById('undo-btn');
    if (undoBtn) undoBtn.onclick = async () => {
        if (swipeHistory.length === 0) return;
        const lastMovie = swipeHistory.pop();
        await fetch('/undo', { 
            method: 'POST', 
            headers: providerIdentityHeaders({'Content-Type': 'application/json'}), 
            body: JSON.stringify({ movie_id: lastMovie.id }) 
        });
        movieStack.unshift(lastMovie);
        renderInitialDeck();
    };
    const matchesPill = document.getElementById('matches-pill');
    if (matchesPill) matchesPill.onclick = () => openMatches(false);
}

function renderInitialDeck() {
    const deck = document.getElementById('swipe-deck');
    deck.innerHTML = '';
    movieStack.slice(0, 5).reverse().forEach(m => deck.appendChild(createCard(m)));
    initDrag(deck.lastElementChild);
}

function createCard(m) {
    const c = document.createElement('div');
    c.className = 'movie-card';
    c.dataset.id = m.id; c.dataset.title = m.title; c.dataset.thumb = m.thumb;
    c.innerHTML = `
        <div class="card-inner">
            <div class="card-front"><img src="${m.thumb}"></div>
            <div class="card-back">
                <div class="movie-title">${m.title}</div>
                <div class="stats-row">
                    ${m.rating ? `<span class="stat-badge">IMDb ${m.rating}</span>` : ''}
                    ${m.duration ? `<span class="stat-badge">${m.duration}</span>` : ''}
                    ${m.year ? `<span class="stat-badge">${m.year}</span>` : ''}
                </div>
                <div id="vid-${m.id}" class="trailer-box"></div>
                <button class="trailer-btn" data-movie-id="${m.id}">WATCH TRAILER</button>
                <div class="back-content"><p>${m.summary || 'No description available.'}</p></div>
                <div id="cast-${m.id}" class="cast-row"></div>
                <div class="flip-back-hint">Tap to flip back</div>
            </div>
        </div>
    `;
    c.addEventListener('click', async (e) => {
        if (!e.target.classList.contains('trailer-btn') && Math.abs(globalCurrentX) < 5) {
            c.classList.toggle('flipped');
            if (c.classList.contains('flipped')) {
                const castEl = document.getElementById(`cast-${m.id}`);
                if (castEl && castEl.dataset.loaded !== 'true') {
                    castEl.dataset.loaded = 'true';
                    castEl.innerHTML = '<span class="cast-loading-text">Loading cast...</span>';
                    try {
                        const res = await fetch(`/cast/${m.id}`);
                        const data = await res.json();
                        if (data.cast && data.cast.length > 0) {
                            castEl.innerHTML = data.cast.map(actor => `
                                <div class="cast-member">
                                    ${actor.profile_path
                                        ? `<img src="${actor.profile_path}" alt="${actor.name}" loading="lazy">`
                                        : `<div class="no-photo">🎬</div>`}
                                    <span>${actor.name}</span>
                                </div>
                            `).join('');
                        } else {
                            castEl.innerHTML = '';
                        }
                    } catch(err) {
                        castEl.innerHTML = '';
                    }
                }
            }
        }
    });
    return c;
}

async function watchTrailer(event, id, btn) {
    event.stopPropagation();
    const container = document.getElementById(`vid-${id}`);
    const backContent = container.closest('.card-back').querySelector('.back-content');
    if (container.style.display === 'block') {
        container.style.display = 'none'; container.innerHTML = ''; btn.innerText = 'WATCH TRAILER';
        backContent.style.display = '';
    } else {
        btn.innerText = 'LOADING...';
        const res = await fetch(`/get-trailer/${id}`);
        const data = await res.json();
        if (data.youtube_key) {
            backContent.style.display = 'none';
            container.style.display = 'block';
            container.innerHTML = `<iframe src="https://www.youtube.com/embed/${data.youtube_key}?autoplay=1&playsinline=1" allow="autoplay; encrypted-media" allowfullscreen></iframe>`;
            btn.innerText = 'CLOSE TRAILER';
        } else btn.innerText = 'TRAILER NOT FOUND';
    }
}

function initDrag(card) {
    if (!card) return;
    let startX, isDragging = false;
    globalCurrentX = 0;
    const glowLeft = document.getElementById('glow-left');
    const glowRight = document.getElementById('glow-right');
    const onMove = (e) => {
        if (!isDragging) return;
        const x = e.clientX || (e.touches && e.touches[0].clientX);
        globalCurrentX = x - startX;
        if (card.classList.contains('flipped')) return;
        card.style.transition = 'none';
        card.style.transform = `translate(${globalCurrentX}px, ${Math.abs(globalCurrentX)/10}px) rotate(${globalCurrentX / 10}deg)`;
        glowRight.style.opacity = globalCurrentX > 20 ? Math.min(Math.abs(globalCurrentX) / 200, 1) : 0;
        glowLeft.style.opacity = globalCurrentX < -20 ? Math.min(Math.abs(globalCurrentX) / 200, 1) : 0;
    };
    const onEnd = async () => {
        if (!isDragging) return; isDragging = false;
        glowLeft.style.opacity = 0; glowRight.style.opacity = 0;
        if (card.classList.contains('flipped')) { globalCurrentX = 0; return; }
        card.style.transition = 'transform 0.4s ease, opacity 0.3s ease';
        if (Math.abs(globalCurrentX) > 120) {
            const dir = globalCurrentX > 0 ? 'right' : 'left';
            card.style.transform = `translate(${globalCurrentX > 0 ? 1000 : -1000}px, 0px) rotate(${globalCurrentX / 5}deg)`;
            card.style.opacity = '0';
            const movieData = movieStack[0]; swipeHistory.push(movieData);
            fetch('/room/swipe', { 
                method: 'POST', 
                headers: providerIdentityHeaders({'Content-Type': 'application/json'}), 
                body: JSON.stringify({ 
                    movie_id: card.dataset.id, title: card.dataset.title, thumb: card.dataset.thumb, direction: dir,
                    plex_id: providerUserId()
                }) 
            })
            .then(r => r.json()).then(data => { 
                if (data.match) { 
                    document.getElementById('matched-movie-title').innerText = data.title;
                    document.getElementById('match-popup-poster').src = data.thumb || '';
                    const heading = document.getElementById('match-heading');
                    const soloLabel = document.getElementById('match-solo-label');
                    if (data.solo) {
                        heading.innerText = 'NICE ONE!';
                        soloLabel.classList.remove('hidden');
                    } else {
                        heading.innerText = "IT'S A MATCH!";
                        soloLabel.classList.add('hidden');
                    }
                    document.getElementById('match-overlay').classList.remove('hidden');
                } 
            });
            setTimeout(() => { card.remove(); movieStack.shift(); if (movieStack[4]) document.getElementById('swipe-deck').prepend(createCard(movieStack[4])); initDrag(document.getElementById('swipe-deck').lastElementChild); globalCurrentX = 0; }, 300);
        } else { card.style.transform = ''; setTimeout(() => globalCurrentX = 0, 50); }
    };
    card.onpointerdown = (e) => {
        if (e.target.tagName === 'BUTTON') return;
        isDragging = true; startX = e.clientX || (e.touches && e.touches[0].clientX);
        card.setPointerCapture(e.pointerId);
        window.addEventListener('pointermove', onMove); window.addEventListener('pointerup', onEnd);
    };
}

async function joinRoom() {
    const code = document.getElementById('join-code').value;
    const res = await fetch('/room/join', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ code }) });
    if (res.ok) { localStorage.setItem('active_room', 'joined'); loadMovies(false); } else alert("Invalid Code");
}

async function loadGenres() {
    try {
        const res = await fetch('/genres');
        const genres = await res.json();
        const list = document.getElementById('genre-list');
        list.querySelectorAll('.genre-dynamic').forEach(el => el.remove());
        genres.forEach(g => {
            const el = document.createElement('div');
            el.className = 'genre-item genre-dynamic';
            el.textContent = g;
            el.onclick = () => selectGenre(g);
            list.appendChild(el);
        });
    } catch (e) { console.error('Could not load genres', e); }
}

let sseSource = null;

const startPolling = () => {
    if (sseSource) { sseSource.close(); sseSource = null; }
    sseSource = new EventSource('/room/stream');
    sseSource.onmessage = async (event) => {
        const d = JSON.parse(event.data);
        if (d.closed) {
            sseSource.close();
            localStorage.removeItem('active_room');
            location.reload();
            return;
        }
        if (d.genre && d.genre !== currentGenre) {
            currentGenre = d.genre;
            document.getElementById('genre-pill').innerText = currentGenre === 'All' ? 'Genres ▾' : currentGenre + ' ▾';
            const movieRes = await fetch('/movies');
            movieStack = await movieRes.json(); swipeHistory = []; renderInitialDeck();
        }
        if (d.ready && document.getElementById('game-area').classList.contains('hidden')) {
            loadMovies(d.solo || false);
        }
        if (d.last_match && !isSoloMode) {
            const matchTs = d.last_match.ts;
            if (matchTs > lastSeenMatchTs) {
                lastSeenMatchTs = matchTs;
                document.getElementById('matched-movie-title').innerText = d.last_match.title;
                document.getElementById('match-popup-poster').src = d.last_match.thumb || '';
                document.getElementById('match-heading').innerText = "IT'S A MATCH!";
                document.getElementById('match-solo-label').classList.add('hidden');
                document.getElementById('match-overlay').classList.remove('hidden');
            }
        }
    };
};

// Event delegation for dynamically created elements
document.getElementById('matches-list').addEventListener('click', (e) => {
    const watchlistBtn = e.target.closest('.watchlist-btn');
    if (watchlistBtn) { addToWatchlist(e, watchlistBtn.dataset.movieId); return; }
    const deleteBtn = e.target.closest('.delete-match-btn');
    if (deleteBtn) { deleteMatch(e, deleteBtn.dataset.movieId); return; }
});

document.getElementById('swipe-deck').addEventListener('click', (e) => {
    const trailerBtn = e.target.closest('.trailer-btn');
    if (trailerBtn) { watchTrailer(e, trailerBtn.dataset.movieId, trailerBtn); }
});

window.onload = async () => {
    _bindStaticHandlers();

    // Static element event listeners (replacing inline onclick handlers)
    document.getElementById('quit-pill').addEventListener('click', confirmQuit);
    document.getElementById('host-btn').addEventListener('click', async () => {
        const res = await fetch('/room/create', { method: 'POST' });
        const data = await res.json();
        localStorage.setItem('active_room', 'hosting'); 
        document.getElementById('session-display').innerText = data.pairing_code;
        document.getElementById('host-btn').classList.add('hidden');
        document.getElementById('session-info').classList.remove('hidden');
        startPolling();
    });
    document.getElementById('join-btn').addEventListener('click', joinRoom);
    document.getElementById('history-btn').addEventListener('click', () => openMatches(true));
    document.getElementById('genre-pill').addEventListener('click', toggleGenreModal);
    document.getElementById('keep-swiping-btn').addEventListener('click', () => {
        document.getElementById('match-overlay').classList.add('hidden');
    });
    document.getElementById('close-matches-btn').addEventListener('click', () => {
        document.getElementById('matches-modal').classList.add('hidden');
    });
    document.getElementById('quit-confirm-btn').addEventListener('click', doQuit);
    document.getElementById('quit-cancel-btn').addEventListener('click', () => {
        document.getElementById('quit-modal').classList.add('hidden');
    });
    document.getElementById('delete-modal-overlay').addEventListener('click', closeDeleteModal);
    document.getElementById('delete-cancel-btn').addEventListener('click', closeDeleteModal);

    // Logout button
    document.querySelector('.logout-btn').addEventListener('click', () => {
        localStorage.clear();
        location.reload();
    });

    // Solo toggle
    document.getElementById('solo-toggle').addEventListener('change', function() {
        handleSoloToggle(this);
    });

    // Genre list event delegation (for static genre items)
    document.getElementById('genre-list').addEventListener('click', (e) => {
        const item = e.target.closest('.genre-item');
        if (item && item.dataset.genre) selectGenre(item.dataset.genre);
    });

    // Genre cancel button
    document.querySelector('.genre-cancel-btn').addEventListener('click', toggleGenreModal);

    const params = new URLSearchParams(window.location.search);
    const pinId = params.get('pin_id');
    if (mediaProvider === 'plex') {
        const pinUrl = pinId ? `/auth/check-returned-pin?pin_id=${pinId}` : '/auth/check-returned-pin';
        const pendingPin = await fetch(pinUrl);
        const result = await pendingPin.json();
        if (result.authToken) {
            localStorage.setItem("plex_token", result.authToken);
            localStorage.setItem("provider_token", result.authToken);
            window.history.replaceState({}, '', '/');
        }
    }
    if (mediaProvider === 'jellyfin') {
        try {
            const provRes = await fetch('/auth/provider');
            const provData = await provRes.json();
            if (provData.jellyfin_browser_auth === 'delegate') {
                document.getElementById('login-btn').innerText = 'Continue';
                document.getElementById('login-btn').onclick = () => bootstrapJellyfinDelegate();
                const booted = await bootstrapJellyfinDelegate();
                if (booted) {
                    await fetchAndStoreProviderId();
                    return;
                }
            }
        } catch (e) {
            console.error('Jellyfin provider probe failed', e);
        }
    }
    document.getElementById('login-btn').innerText = mediaProvider === 'jellyfin' ? 'Login with Jellyfin' : 'Login with Plex';
    document.getElementById('login-btn').onclick = loginWithPlex;
    if (providerToken()) {
        await fetchAndStoreProviderId();
        document.getElementById('login-section').classList.add('hidden');
        document.getElementById('main-menu').classList.remove('hidden');
        loadGenres();
        if (localStorage.getItem('active_room')) loadMovies();
    }
};
