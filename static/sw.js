// Sunucudan (Flask) yeni bir bildirim geldiğinde tetiklenir
self.addEventListener('push', function(event) {
    if (event.data) {
        try {
            // Veriyi bir kez alıyoruz
            const rawData = event.data.text();
            console.log('Push sinyali geldi!', rawData);
            
            const data = JSON.parse(rawData);
            
            const title = data.title || "Kampüs Kayıp Eşya";
            const options = {
                body: data.body || "Yeni bir ilan eklendi!",
                icon: '/static/icon.png', // İkon dosyanın varlığından emin ol
                badge: '/static/badge.png',
                vibrate: [100, 50, 100],
                data: {
                    url: data.url || '/' 
                }
            };

            // Bildirimi ekrana bas
            event.waitUntil(self.registration.showNotification(title, options));
        } catch (e) {
            console.error("Bildirim işleme hatası:", e);
        }
    }
});

// Bildirime tıklanma olayı
self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    const targetUrl = event.notification.data.url;

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(clientList) {
            // Eğer site zaten açıksa oraya odaklan
            for (let client of clientList) {
                if (client.url.includes(targetUrl) && 'focus' in client) {
                    return client.focus();
                }
            }
            // Açık değilse yeni sekme aç
            if (clients.openWindow) {
                return clients.openWindow(targetUrl);
            }
        })
    );
});
