// Lets a phone add the Dungeon to its home screen. It caches nothing: every page and answer comes fresh from the
// Dungeon on your PC.
self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()))
