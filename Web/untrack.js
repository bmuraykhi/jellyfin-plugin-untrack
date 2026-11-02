(function () {
    'use strict';

    if (window.__untrackShowLoaded) {
        return;
    }
    window.__untrackShowLoaded = true;

    const COMMAND_ID = 'untrackshow';
    const SUPPORTED_TYPES = ['Episode', 'Season', 'Series'];
    const MENU_BUTTONS = '[data-action="menu"], .btnCardOptions, .btnMoreCommands, .btnToggleContextMenu';
    const SELECTION_MENU_BUTTON = '.btnSelectionPanelOptions';

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

    function clearPersistedQueries() {
        return new Promise(function (resolve) {
            let request;
            try {
                request = indexedDB.open('keyval-store');
            } catch (err) {
                resolve();
                return;
            }
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

    function showsLabel(shows) {
        return shows.size === 1 ? shows.values().next().value : shows.size + ' shows';
    }

    function whenClosed(sheet) {
        const started = Date.now();
        return new Promise(function (resolve) {
            (function check() {
                if (!sheet.isConnected || Date.now() - started > 2000) {
                    resolve();
                } else {
                    setTimeout(check, 50);
                }
            })();
        });
    }

    function confirmUntrack(shows) {
        const one = shows.size === 1;
        const title = 'Untrack ' + showsLabel(shows) + '?';
        const text = 'Every episode' + (one ? '' : ' of these shows')
            + ' will be marked unwatched for you, including the ones you\'ve finished. '
            + (one ? 'It leaves' : 'They leave') + ' Continue Watching and Next Up until you play '
            + (one ? 'it' : 'them') + ' again. This can\'t be undone.';
        const dashboard = window.Dashboard;
        if (!dashboard || typeof dashboard.confirm !== 'function') {
            return Promise.resolve(window.confirm(title + '\n\n' + text));
        }
        return new Promise(function (resolve) {
            dashboard.confirm({ title: title, text: text, confirmText: 'Untrack', primary: 'delete' }, null, resolve);
        });
    }

    async function untrack(api, userId, shows) {
        try {
            await Promise.all(Array.from(shows.keys()).map(function (seriesId) {
                return api.ajax({ type: 'DELETE', url: api.getUrl('UserPlayedItems/' + seriesId, { userId: userId }) });
            }));
            toast('Untracked ' + showsLabel(shows));
            setTimeout(async function () {
                await clearPersistedQueries();
                window.location.reload();
            }, 700);
        } catch (err) {
            console.error('UntrackShow: failed', err);
            toast('Could not untrack ' + showsLabel(shows));
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
            }
        }));
        if (!shows.size || !sheet.isConnected || scroller.querySelector('[data-id="' + COMMAND_ID + '"]')) {
            return;
        }

        const option = buildOption(template, shows.size === 1 ? 'Untrack show' : 'Untrack ' + shows.size + ' shows');
        option.addEventListener('click', async function () {
            await whenClosed(sheet);
            if (await confirmUntrack(shows)) {
                untrack(api, userId, shows);
            }
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
