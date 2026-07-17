/* FrameForge service worker - web push */
self.addEventListener("push", function (event) {
  let data = {};
  try { data = event.data.json(); } catch (e) { data = { title: "FrameForge", body: event.data ? event.data.text() : "" }; }
  const title = data.title || "FrameForge";
  const options = {
    body: data.body || "",
    icon: "/logo192.png",
    badge: "/logo192.png",
    data: { url: data.url || "/app/tracker" },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", function (event) {
  event.notification.close();
  const url = event.notification.data && event.notification.data.url ? event.notification.data.url : "/app";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (list) {
      for (const client of list) {
        if ("focus" in client) { client.navigate(url); return client.focus(); }
      }
      if (self.clients.openWindow) return self.clients.openWindow(url);
    })
  );
});
