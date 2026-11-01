// Untrack Show: adds "Untrack show" to the ⋮ menu of episodes, seasons and shows in jellyfin-web, and to the
// multi-select menu (long-press on phones).
// It marks the whole show unplayed for the signed-in user (DELETE /UserPlayedItems/{seriesId}), which
// clears every resume point and watched mark, so the show leaves Continue Watching and Next Up.
(function () {
    'use strict';

    if (window.__untrackShowLoaded) {
        return;
    }
    window.__untrackShowLoaded = true;

    const COMMAND_ID = 'untrackshow';
    const SUPPORTED_TYPES = ['Episode', 'Season', 'Series'];
    const MENU_BUTTONS = '[data-action="menu"], .btnCardOptions, .btnMoreCommands, .btnToggleContextMenu';
    // The ⋮ of the multi-select bar (long-press a card; this is how phones reach the menu).
    const SELECTION_MENU_BUTTON = '.btnSelectionPanelOptions';

    // The items whose menu is being opened: set by a card's ⋮ button, right-click or long-press (one item),
    // or by the multi-select bar's ⋮ (every checked card).
    let pending = null;

    function cardTarget(card) {
        return { id: card.getAttribute('data-id'), type: card.getAttribute('data-type') };
    }

    function remember(element) {
        if (!element || element.closest('.actionSheet')) {
            return;
        }
        const card = element.closest('[data-id]');
        if (card) {
            pending = { targets: [cardTarget(card)], at: Date.now() };
        } else if (element.closest('.btnMoreCommands')) {
            // Item details page: the item is in the URL, e.g. #/details?id=...
            const match = /[?&]id=([0-9a-f]{32})/i.exec(window.location.hash || window.location.search);
            pending = match ? { targets: [{ id: match[1], type: null }], at: Date.now() } : null;
        }
    }

    function rememberSelection() {
        const cards = Array.from(document.querySelectorAll('.chkItemSelect:checked'))
            .map(function (checkbox) {
                return checkbox.closest('[data-id]');
            })
            .filter(Boolean);
        pending = cards.length ? { targets: cards.map(cardTarget), at: Date.now() } : null;
    }

    document.addEventListener('click', function (e) {
        if (!e.target.closest) {
            return;
        }
        if (e.target.closest(SELECTION_MENU_BUTTON)) {
            rememberSelection();
            return;
        }
        const button = e.target.closest(MENU_BUTTONS);
        if (button) {
            remember(button);
        }
    }, true);
    document.addEventListener('contextmenu', function (e) {
        remember(e.target);
    }, true);
    document.addEventListener('touchstart', function (e) {
        remember(e.target);
    }, { capture: true, passive: true });

    function toast(text) {
        const el = document.createElement('div');
        el.textContent = text;
        el.style.cssText = 'position:fixed;left:50%;bottom:5em;transform:translateX(-50%);z-index:99999;padding:.8em 1.4em;'
            + 'border-radius:.4em;background:rgba(0,0,0,.85);color:#fff;font-size:1em;pointer-events:none';
        document.body.appendChild(el);
        setTimeout(function () {
            el.remove();
        }, 2500);
    }

    // jellyfin-web persists its query results in IndexedDB (idb-keyval) and restores them on reload without
    // refetching, so the home rows would still show the show. Drop that cache; the app rebuilds it on load.
    function clearPersistedQueries() {
        return new Promise(function (resolve) {
            let request;
            try {
                request = indexedDB.open('keyval-store');
            } catch (err) {
                resolve();
                return;
            }
            // Don't create the database if the app never made one.
            request.onupgradeneeded = function () {
                request.transaction.abort();
            };
            request.onerror = function () {
                resolve();
            };
            request.onsuccess = function () {
                const db = request.result;
                if (!db.objectStoreNames.contains('keyval')) {
                    db.close();
                    resolve();
                    return;
                }
                const tx = db.transaction('keyval', 'readwrite');
                tx.objectStore('keyval').delete('jellyfin-query-cache');
                tx.oncomplete = tx.onerror = tx.onabort = function () {
                    db.close();
                    resolve();
                };
            };
        });
    }

    // shows: Map of seriesId -> show name.
    async function untrack(api, userId, shows) {
        const names = Array.from(shows.values());
        const label = names.length === 1 ? names[0] : names.length + ' shows';
        try {
            await Promise.all(Array.from(shows.keys()).map(function (seriesId) {
                return api.ajax({ type: 'DELETE', url: api.getUrl('UserPlayedItems/' + seriesId, { userId: userId }) });
            }));
            toast('Untracked ' + label);
            // Home rows don't drop cards on their own; reload with a fresh cache so Continue Watching / Next Up refresh.
            setTimeout(async function () {
                await clearPersistedQueries();
                window.location.reload();
            }, 700);
        } catch (err) {
            console.error('UntrackShow: failed', err);
            toast('Could not untrack ' + label);
        }
    }

    function buildOption(template, label) {
        const option = template.cloneNode(true);
        option.setAttribute('data-id', COMMAND_ID);
        option.querySelectorAll('.listItemBodyText-secondary, .actionSheetItemAsideText, .actionSheetItemSelectedIcon').forEach(function (n) {
            n.remove();
        });
        const text = option.querySelector('.actionSheetItemText') || option.querySelector('.listItemBodyText');
        if (text) {
            text.textContent = label;
        } else {
            option.textContent = label;
        }
        const icon = option.querySelector('.actionsheetMenuItemIcon');
        if (icon) {
            icon.className = 'actionsheetMenuItemIcon listItemIcon listItemIcon-transparent material-icons visibility_off';
        }
        return option;
    }

    async function addOption(sheet) {
        const request = pending;
        if (!request || Date.now() - request.at > 3000) {
            return;
        }
        const targets = request.targets.filter(function (t) {
            return !t.type || SUPPORTED_TYPES.indexOf(t.type) !== -1;
        });
        const api = window.ApiClient;
        const scroller = sheet.querySelector('.actionSheetScroller');
        const template = scroller && scroller.querySelector('.actionSheetMenuItem');
        if (!targets.length || !api || !template || scroller.querySelector('[data-id="' + COMMAND_ID + '"]')) {
            return;
        }

        // Resolve each item to its show; several selected episodes of one show count once.
        const userId = api.getCurrentUserId();
        const shows = new Map();
        await Promise.all(targets.slice(0, 100).map(async function (target) {
            try {
                const item = await api.getItem(userId, target.id);
                if (item.Type === 'Series') {
                    shows.set(item.Id, item.Name);
                } else if (item.SeriesId && SUPPORTED_TYPES.indexOf(item.Type) !== -1) {
                    shows.set(item.SeriesId, item.SeriesName);
                }
            } catch (err) {
                // Not resolvable (deleted, no access): leave it out.
            }
        }));
        if (!shows.size || !sheet.isConnected || scroller.querySelector('[data-id="' + COMMAND_ID + '"]')) {
            return;
        }

        const option = buildOption(template, shows.size === 1 ? 'Untrack show' : 'Untrack ' + shows.size + ' shows');
        // The action sheet closes itself on any menu-item click; this listener does the actual work.
        option.addEventListener('click', function () {
            untrack(api, userId, shows);
        });
        scroller.appendChild(option);
    }

    new MutationObserver(function (mutations) {
        mutations.forEach(function (mutation) {
            mutation.addedNodes.forEach(function (node) {
                if (node.nodeType !== 1) {
                    return;
                }
                const sheet = node.classList.contains('actionSheet') ? node : node.querySelector('.actionSheet');
                if (sheet) {
                    addOption(sheet);
                }
            });
        });
    }).observe(document.body, { childList: true, subtree: true });
})();
