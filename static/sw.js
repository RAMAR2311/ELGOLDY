const CACHE_NAME = 'el-goldy-cache-v2';

self.addEventListener('install', event => {
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  // Limpiar cualquier caché viejo que esté rompiendo la app
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          return caches.delete(cacheName);
        })
      );
    }).then(() => {
      return clients.claim();
    })
  );
});

// EVENTO FETCH ELIMINADO POR COMPLETO
// No interceptaremos ninguna petición de red para evitar que la aplicación 
// muestre datos viejos o bloquee los formularios del CRM/POS.

self.addEventListener('push', event => {
  const data = event.data ? event.data.json() : {};
  const title = data.title || 'EL GOLDY Notificación';
  
  const options = {
    body: data.body || 'Tienes una nueva notificación.',
    icon: '/static/img/icon-192.png',
    badge: '/static/img/icon-192.png',
    data: {
      url: data.url || '/'
    }
  };

  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const urlToOpen = event.notification.data.url || '/';
  
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(windowClients => {
      for (let i = 0; i < windowClients.length; i++) {
        const client = windowClients[i];
        if (client.url === urlToOpen && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(urlToOpen);
      }
    })
  );
});
