(function () {
  if (window.PianovaPracticeTracker) {
    return;
  }

  function normalizeGameType(value) {
    const raw = String(value || window.location.pathname || 'practice').trim();
    const withoutSlashes = raw.replace(/^\/+|\/+$/g, '');
    const compact = withoutSlashes.replace(/[^a-zA-Z0-9_-]+/g, '_');
    return (compact || 'practice').slice(0, 32);
  }

  function attach(options) {
    const startedAt = Date.now();
    const gameType = normalizeGameType(options && options.gameType);
    let sent = false;

    function send() {
      if (sent) {
        return;
      }

      sent = true;
      const durationSeconds = Math.max(1, Math.round((Date.now() - startedAt) / 1000));
      const payload = JSON.stringify({
        game_type: gameType,
        duration_seconds: durationSeconds,
      });

      if (navigator.sendBeacon) {
        navigator.sendBeacon('/api/log-practice-session', new Blob([payload], { type: 'application/json' }));
        return;
      }

      fetch('/api/log-practice-session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: payload,
        keepalive: true,
      }).catch(() => {});
    }

    window.addEventListener('pagehide', send);
    window.addEventListener('beforeunload', send);

    return { send };
  }

  window.PianovaPracticeTracker = { attach };
})();