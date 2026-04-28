        if ('serviceWorker' in navigator) navigator.serviceWorker.register("/sw.js");

        let movieStack = [];
        let swipeHistory = [];
        let globalCurrentX = 0;
        let currentGenre = "All";
        let isHistoryView = false;
        let isSoloMode = false;
        let currentRoomCode = null;

        // apiFetch: wraps fetch with credentials and 401 handling
        async function apiFetch(url, options = {}) {
            options.credentials = 'same-origin';
            const res = await fetch(url, options);
            if (res.status === 401) {
                document.getElementById('session-expired-banner').classList.remove('hidden');
            }
            return res;
        }

        async function bootstrapJellyfinDelegate() {
            const provRes = await fetch("/auth/provider", { credentials: "same-origin" });
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
            document.getElementById("login-section").classList.add("hidden");
            document.getElementById("main-menu").classList.remove("hidden");
            loadGenres();
            checkActiveRoom();
            return true;
        }

        async function login() {
            const provRes = await fetch("/auth/provider", { credentials: "same-origin" });
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
                body: JSON.stringify({ username, password }),
                credentials: "same-origin",
            });
            const data = await resp.json();
            if (!resp.ok || !data.userId) {
                alert(data.error || "Jellyfin login failed");
                return;
            }
            document.getElementById("login-section").classList.add("hidden");
            document.getElementById("main-menu").classList.remove("hidden");
            loadGenres();
            checkActiveRoom();
        }

        async function checkActiveRoom() {
            try {
                const res = await fetch('/me', { credentials: 'same-origin' });
                if (!res.ok) return;
                const data = await res.json();
                if (data.activeRoom) {
                    currentRoomCode = data.activeRoom;
                    loadMovies();
                }
            } catch(e) { console.error('Room check failed', e); }
        }

        async function doLogout() {
            await fetch('/auth/logout', { method: 'POST', credentials: 'same-origin' });
            currentRoomCode = null;
            location.reload();
        }

        function confirmQuit() {
            document.getElementById('quit-modal').classList.remove('hidden');
        }

        async function doQuit() {
            await apiFetch(`/room/${currentRoomCode}/quit`, { method: 'POST' });
            currentRoomCode = null;
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
            const res = await apiFetch(`/room/${currentRoomCode}/genre`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ genre })
            });
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
                const res = await apiFetch("/watchlist/add", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
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
            const res = await fetch('/room/solo', { method: 'POST', credentials: 'same-origin' });
            if (res.ok) {
                const data = await res.json();
                currentRoomCode = data.pairing_code;
                isSoloMode = true;
                loadMovies(true);
            }
        }

        async function handleSoloToggle(checkbox) {
            const track = document.getElementById('solo-toggle-track');
            const thumb = document.getElementById('solo-toggle-thumb');
            if (checkbox.checked) {
                track.style.background = '#e5a00d';
                thumb.style.transform = 'translateX(18px)';
                thumb.style.background = '#000';
                await activateSoloMode();
            } else {
                track.style.background = '#333';
                thumb.style.transform = 'translateX(0)';
                thumb.style.background = '#888';
            }
        }

        const loadMovies = async (solo = false) => {
            isSoloMode = solo;
            const res = await apiFetch(`/room/${currentRoomCode}/deck`);
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

        function showMatchMetadata(match) {
            const container = document.getElementById('match-metadata');
            container.innerHTML = '';
            if (match.rating) {
                const badge = document.createElement('span');
                badge.className = 'stat-badge';
                badge.textContent = 'IMDb ' + match.rating;
                container.appendChild(badge);
            }
            if (match.duration) {
                const badge = document.createElement('span');
                badge.className = 'stat-badge';
                badge.textContent = match.duration;
                container.appendChild(badge);
            }
            if (match.year) {
                const badge = document.createElement('span');
                badge.className = 'stat-badge';
                badge.textContent = match.year;
                container.appendChild(badge);
            }
            const link = document.getElementById('match-deep-link');
            if (match.deep_link) {
                link.href = match.deep_link;
                link.classList.remove('hidden');
            } else {
                link.classList.add('hidden');
            }
        }

        async function openMatches(asHistory) {
            isHistoryView = asHistory;
            const label = isSoloMode && !asHistory ? "Your Shortlist" : asHistory ? "Match History" : "Your Matches";
            document.getElementById('modal-title').innerText = label;
            const url = asHistory ? '/matches?view=history' : '/matches';
            const res = await apiFetch(url);
            const data = await res.json();
            const list = document.getElementById('matches-list');
            const emptyLabel = asHistory ? 'history' : isSoloMode ? 'shortlist' : 'matches';
            list.innerHTML = data.length ? '' : `<p style="grid-column: span 2; color:#666;">No ${emptyLabel} yet</p>`;
            data.forEach(m => {
                const card = document.createElement('div');
                card.className = 'mini-poster';

                // Create mini-inner container
                const miniInner = document.createElement('div');
                miniInner.className = 'mini-inner';

                // Create mini-front
                const miniFront = document.createElement('div');
                miniFront.className = 'mini-front';

                // Create image with safe src assignment
                const img = document.createElement('img');
                img.src = m.thumb;
                img.alt = 'Movie poster';
                miniFront.appendChild(img);

                // Create title overlay div
                const titleOverlay = document.createElement('div');
                titleOverlay.style.position = 'absolute';
                titleOverlay.style.bottom = '0';
                titleOverlay.style.width = '100%';
                titleOverlay.style.background = 'linear-gradient(transparent, black)';
                titleOverlay.style.fontSize = '12px';
                titleOverlay.style.padding = '8px 4px';
                titleOverlay.style.fontWeight = 'bold';
                titleOverlay.style.color = '#e5a00d';
                titleOverlay.textContent = m.title;
                miniFront.appendChild(titleOverlay);

                miniInner.appendChild(miniFront);

                // Create mini-back
                const miniBack = document.createElement('div');
                miniBack.className = 'mini-back';

                // Title text
                const titleText = document.createElement('div');
                titleText.className = 'mini-title-text';
                titleText.textContent = m.title;
                miniBack.appendChild(titleText);

                // Stats row
                const statsRow = document.createElement('div');
                statsRow.className = 'stats-row';
                statsRow.style.justifyContent = 'center';

                if (m.rating) {
                    const ratingBadge = document.createElement('span');
                    ratingBadge.className = 'stat-badge';
                    ratingBadge.textContent = `IMDb ${m.rating}`;
                    statsRow.appendChild(ratingBadge);
                }
                if (m.duration) {
                    const durationBadge = document.createElement('span');
                    durationBadge.className = 'stat-badge';
                    durationBadge.textContent = m.duration;
                    statsRow.appendChild(durationBadge);
                }
                if (m.year) {
                    const yearBadge = document.createElement('span');
                    yearBadge.className = 'stat-badge';
                    yearBadge.textContent = m.year;
                    statsRow.appendChild(yearBadge);
                }
                miniBack.appendChild(statsRow);

                // Open in Jellyfin button (using server deep_link)
                const openBtn = document.createElement('a');
                openBtn.href = m.deep_link || '#';
                openBtn.className = 'plex-open-btn';
                openBtn.target = '_blank';
                openBtn.rel = 'noopener noreferrer';
                openBtn.textContent = 'OPEN IN JELLYFIN';
                miniBack.appendChild(openBtn);

                // Watchlist button
                const watchlistBtn = document.createElement('button');
                watchlistBtn.className = 'menu-btn';
                watchlistBtn.style.width = '90%';
                watchlistBtn.style.padding = '8px';
                watchlistBtn.style.fontSize = '0.7rem';
                watchlistBtn.style.background = '#333';
                watchlistBtn.style.color = '#e5a00d';
                watchlistBtn.style.border = '1px solid #e5a00d';
                watchlistBtn.style.marginTop = '5px';
                watchlistBtn.textContent = 'SAVE TO WATCHLIST';
                watchlistBtn.onclick = (event) => addToWatchlist(event, m.movie_id);
                miniBack.appendChild(watchlistBtn);

                // Delete button
                const deleteBtn = document.createElement('button');
                deleteBtn.className = 'menu-btn';
                deleteBtn.style.width = '90%';
                deleteBtn.style.padding = '8px';
                deleteBtn.style.fontSize = '0.7rem';
                deleteBtn.style.background = '#d32f2f';
                deleteBtn.style.marginTop = '5px';
                deleteBtn.style.color = 'black';
                deleteBtn.textContent = 'DELETE';
                deleteBtn.onclick = (event) => deleteMatch(event, m.movie_id);
                miniBack.appendChild(deleteBtn);

                miniInner.appendChild(miniBack);
                card.appendChild(miniInner);

                // Click handler for flip
                card.onclick = (e) => {
                    if (!e.target.closest('a') && !e.target.closest('button')) {
                        card.classList.toggle('flipped');
                    }
                };

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
                await apiFetch("/matches/delete", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
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
                await apiFetch(`/room/${currentRoomCode}/undo`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ movie_id: lastMovie.id })
                });
                movieStack.unshift(lastMovie);
                renderInitialDeck();
            };
            const matchesPill = document.getElementById('matches-pill');
            if (matchesPill) matchesPill.onclick = () => openMatches(false);

            const joinBtn = document.getElementById('join-btn');
            if (joinBtn) joinBtn.onclick = () => joinRoom();

            const quitPill = document.getElementById('quit-pill');
            if (quitPill) quitPill.onclick = () => confirmQuit();

            const historyBtn = document.getElementById('history-btn');
            if (historyBtn) historyBtn.onclick = () => openMatches(true);

            const genrePill = document.getElementById('genre-pill');
            if (genrePill) genrePill.onclick = () => toggleGenreModal();

            const soloToggle = document.getElementById('solo-toggle');
            if (soloToggle) soloToggle.addEventListener('change', function() { handleSoloToggle(this); });

            const genreCancelBtn = document.querySelector('.genre-cancel-btn');
            if (genreCancelBtn) genreCancelBtn.addEventListener('click', () => toggleGenreModal());

            const quitConfirmBtn = document.getElementById('quit-confirm-btn');
            if (quitConfirmBtn) quitConfirmBtn.addEventListener('click', () => doQuit());

            const quitCancelBtn = document.getElementById('quit-cancel-btn');
            if (quitCancelBtn) quitCancelBtn.addEventListener('click', () => {
                document.getElementById('quit-modal').classList.add('hidden');
            });

            const deleteOverlay = document.getElementById('delete-modal-overlay');
            if (deleteOverlay) deleteOverlay.addEventListener('click', () => closeDeleteModal());

            const deleteCancelBtn = document.getElementById('delete-cancel-btn');
            if (deleteCancelBtn) deleteCancelBtn.addEventListener('click', () => closeDeleteModal());

            const closeMatchesBtn = document.getElementById('close-matches-btn');
            if (closeMatchesBtn) closeMatchesBtn.addEventListener('click', () => {
                document.getElementById('matches-modal').classList.add('hidden');
            });

            const reloginBtn = document.getElementById('relogin-btn');
            if (reloginBtn) reloginBtn.addEventListener('click', () => {
                document.getElementById('session-expired-banner').classList.add('hidden');
                location.reload();
            });
            const dismissBtn = document.getElementById('dismiss-btn');
            if (dismissBtn) dismissBtn.addEventListener('click', () => {
                document.getElementById('session-expired-banner').classList.add('hidden');
            });
            const keepSwipingBtn = document.getElementById('keep-swiping-btn');
            if (keepSwipingBtn) keepSwipingBtn.addEventListener('click', () => {
                document.getElementById('match-overlay').classList.add('hidden');
            });
            const logoutBtn = document.getElementById('logout-btn');
            if (logoutBtn) logoutBtn.addEventListener('click', () => doLogout());
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

            // Create card-inner
            const cardInner = document.createElement('div');
            cardInner.className = 'card-inner';

            // Create card-front
            const cardFront = document.createElement('div');
            cardFront.className = 'card-front';
            const frontImg = document.createElement('img');
            frontImg.src = m.thumb;
            frontImg.alt = 'Movie poster';
            cardFront.appendChild(frontImg);
            cardInner.appendChild(cardFront);

            // Create card-back
            const cardBack = document.createElement('div');
            cardBack.className = 'card-back';

            // Movie title
            const movieTitle = document.createElement('div');
            movieTitle.className = 'movie-title';
            movieTitle.textContent = m.title;
            cardBack.appendChild(movieTitle);

            // Stats row
            const statsRow = document.createElement('div');
            statsRow.className = 'stats-row';

            if (m.rating) {
                const ratingBadge = document.createElement('span');
                ratingBadge.className = 'stat-badge';
                ratingBadge.textContent = `IMDb ${m.rating}`;
                statsRow.appendChild(ratingBadge);
            }
            if (m.duration) {
                const durationBadge = document.createElement('span');
                durationBadge.className = 'stat-badge';
                durationBadge.textContent = m.duration;
                statsRow.appendChild(durationBadge);
            }
            if (m.year) {
                const yearBadge = document.createElement('span');
                yearBadge.className = 'stat-badge';
                yearBadge.textContent = m.year;
                statsRow.appendChild(yearBadge);
            }
            cardBack.appendChild(statsRow);

            // Trailer box (empty container)
            const trailerBox = document.createElement('div');
            trailerBox.id = `vid-${m.id}`;
            trailerBox.className = 'trailer-box';
            cardBack.appendChild(trailerBox);

            // Trailer button
            const trailerBtn = document.createElement('button');
            trailerBtn.className = 'trailer-btn';
            trailerBtn.textContent = 'WATCH TRAILER';
            trailerBtn.onclick = (event) => watchTrailer(event, m.id, trailerBtn);
            cardBack.appendChild(trailerBtn);

            // Back content with summary
            const backContent = document.createElement('div');
            backContent.className = 'back-content';
            const summaryP = document.createElement('p');
            summaryP.textContent = m.summary || 'No description available.';
            backContent.appendChild(summaryP);
            cardBack.appendChild(backContent);

            // Cast row (empty container, populated later)
            const castRow = document.createElement('div');
            castRow.id = `cast-${m.id}`;
            castRow.className = 'cast-row';
            cardBack.appendChild(castRow);

            // Tap to flip instruction
            const flipHint = document.createElement('div');
            flipHint.style.fontSize = '0.75rem';
            flipHint.style.color = '#e5a00d';
            flipHint.style.textAlign = 'center';
            flipHint.style.marginTop = 'auto';
            flipHint.style.paddingBottom = '10px';
            flipHint.textContent = 'Tap to flip back';
            cardBack.appendChild(flipHint);

            cardInner.appendChild(cardBack);
            c.appendChild(cardInner);

            c.addEventListener('click', async (e) => {
                if (!e.target.classList.contains('trailer-btn') && Math.abs(globalCurrentX) < 5) {
                    c.classList.toggle('flipped');
                    if (c.classList.contains('flipped')) {
                        const castEl = document.getElementById(`cast-${m.id}`);
                        if (castEl && castEl.dataset.loaded !== 'true') {
                            castEl.dataset.loaded = 'true';
                            castEl.textContent = 'Loading cast...';
                            try {
                                const res = await fetch(`/cast/${m.id}`);
                                const data = await res.json();
                                if (data.cast && data.cast.length > 0) {
                                    // Clear loading text
                                    castEl.textContent = '';

                                    data.cast.forEach(actor => {
                                        const castMember = document.createElement('div');
                                        castMember.className = 'cast-member';

                                        if (actor.profile_path) {
                                            const actorImg = document.createElement('img');
                                            actorImg.src = actor.profile_path;
                                            actorImg.alt = actor.name;
                                            actorImg.loading = 'lazy';
                                            castMember.appendChild(actorImg);
                                        } else {
                                            const noPhoto = document.createElement('div');
                                            noPhoto.className = 'no-photo';
                                            noPhoto.textContent = '🎬';
                                            castMember.appendChild(noPhoto);
                                        }

                                        const actorName = document.createElement('span');
                                        actorName.textContent = actor.name;
                                        castMember.appendChild(actorName);

                                        castEl.appendChild(castMember);
                                    });
                                } else {
                                    castEl.textContent = '';
                                }
                            } catch(err) {
                                castEl.textContent = '';
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
                container.style.display = 'none';
                while (container.firstChild) {
                    container.removeChild(container.firstChild);
                }
                btn.innerText = 'WATCH TRAILER';
                backContent.style.display = '';
            } else {
                btn.innerText = 'LOADING...';
                const res = await fetch(`/get-trailer/${id}`);
                const data = await res.json();
                if (data.youtube_key) {
                    backContent.style.display = 'none';
                    container.style.display = 'block';
                    const iframe = document.createElement('iframe');
                    iframe.src = `https://www.youtube.com/embed/${data.youtube_key}?autoplay=1&playsinline=1`;
                    iframe.allow = 'autoplay; encrypted-media';
                    iframe.allowFullscreen = true;
                    container.appendChild(iframe);
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
                    apiFetch(`/room/${currentRoomCode}/swipe`, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ movie_id: card.dataset.id, direction: dir })
                    });
                    // Match popup comes from SSE only — no match detection in HTTP response
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

        document.getElementById('host-btn').onclick = async () => {
            const res = await apiFetch('/room', { method: 'POST' });
            const data = await res.json();
            currentRoomCode = data.pairing_code;
            document.getElementById('session-display').innerText = data.pairing_code;
            document.getElementById('host-btn').classList.add('hidden');
            document.getElementById('session-info').classList.remove('hidden');
            startPolling();
        };

        async function joinRoom() {
            const code = document.getElementById('join-code').value;
            const res = await fetch(`/room/${code}/join`, { method: 'POST', credentials: 'same-origin' });
            if (res.ok) { currentRoomCode = code; loadMovies(false); } else alert("Invalid Code");
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
            sseSource = new EventSource(`/room/${currentRoomCode}/stream`);
            sseSource.onmessage = async (event) => {
                const d = JSON.parse(event.data);
                if (d.closed) {
                    sseSource.close();
                    sseSource = null;
                    currentRoomCode = null;
                    document.getElementById('game-area').classList.add('hidden');
                    document.getElementById('branding').classList.remove('hidden');
                    document.getElementById('controls-area').classList.remove('hidden');
                    document.getElementById('quit-pill').classList.add('hidden');
                    document.getElementById('matches-pill').classList.add('hidden');
                    document.getElementById('undo-btn').classList.add('hidden');
                    return;
                }
                if (d.genre && d.genre !== currentGenre) {
                    currentGenre = d.genre;
                    document.getElementById('genre-pill').innerText = currentGenre === 'All' ? 'Genres ▾' : currentGenre + ' ▾';
                    const movieRes = await apiFetch(`/room/${currentRoomCode}/deck`);
                    movieStack = await movieRes.json(); swipeHistory = []; renderInitialDeck();
                }
                if (d.ready && document.getElementById('game-area').classList.contains('hidden')) {
                    loadMovies(d.solo || false);
                }
                if (d.last_match) {
                    document.getElementById('matched-movie-title').innerText = d.last_match.title;
                    document.getElementById('match-popup-poster').src = d.last_match.thumb || '';
                    const heading = document.getElementById('match-heading');
                    heading.innerText = "IT'S A MATCH!";
                    document.getElementById('match-solo-label').classList.add('hidden');
                    showMatchMetadata(d.last_match);
                    document.getElementById('match-overlay').classList.remove('hidden');
                }
            };
            sseSource.onerror = () => {
                sseSource.close();
                sseSource = null;
                setTimeout(() => { if (currentRoomCode) startPolling(); }, 3000);
            };
        };

        window.onload = async () => {
            _bindStaticHandlers();
            try {
                const res = await fetch('/me', { credentials: 'same-origin' });
                if (res.ok) {
                    const data = await res.json();
                    document.getElementById('login-section').classList.add('hidden');
                    document.getElementById('main-menu').classList.remove('hidden');
                    loadGenres();
                    if (data.activeRoom) {
                        currentRoomCode = data.activeRoom;
                        loadMovies();
                    }
                } else {
                    // Not authenticated — set up login flow
                    try {
                        const provRes = await fetch('/auth/provider', { credentials: 'same-origin' });
                        const provData = await provRes.json();
                        if (provData.jellyfin_browser_auth === 'delegate') {
                            document.getElementById('login-btn').innerText = 'Continue';
                            document.getElementById('login-btn').onclick = () => bootstrapJellyfinDelegate();
                            const booted = await bootstrapJellyfinDelegate();
                            if (booted) {
                                // After delegate bootstrap, check for active room
                                try {
                                    const meRes = await fetch('/me', { credentials: 'same-origin' });
                                    if (meRes.ok) {
                                        const meData = await meRes.json();
                                        if (meData.activeRoom) {
                                            currentRoomCode = meData.activeRoom;
                                            loadMovies();
                                        }
                                    }
                                } catch(e) {}
                            }
                            return;
                        }
                    } catch(e) { console.error('Provider probe failed', e); }
                    // Show login form
                    document.getElementById('login-btn').innerText = 'Login with Jellyfin';
                    document.getElementById('login-btn').onclick = login;
                }
            } catch(e) { console.error('Auth check failed', e); }
        };
