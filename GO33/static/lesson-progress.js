(function () {
  const pendingSaves = new Map();

  function normalizePath(path) {
    const rawPath = String(path || window.location.pathname || '').trim();
    if (!rawPath) {
      return window.location.pathname;
    }

    try {
      const url = new URL(rawPath, window.location.origin);
      return url.pathname;
    } catch (error) {
      return rawPath.startsWith('/') ? rawPath : `/${rawPath}`;
    }
  }

  async function loadState(levelId, lessonPath) {
    const params = new URLSearchParams({
      level_id: String(levelId),
      lesson_path: normalizePath(lessonPath),
    });

    const response = await fetch(`/api/lesson-progress?${params.toString()}`, {
      method: 'GET',
      credentials: 'same-origin',
      headers: { 'Accept': 'application/json' },
    });

    if (!response.ok) {
      throw new Error(`Failed to load lesson progress (${response.status})`);
    }

    const payload = await response.json();
    return payload && payload.status === 'ok' ? payload.state : null;
  }

  async function saveState(levelId, lessonPath, state) {
    const response = await fetch('/api/lesson-progress', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({
        level_id: levelId,
        lesson_path: normalizePath(lessonPath),
        state,
      }),
      keepalive: true,
    });

    if (!response.ok) {
      throw new Error(`Failed to save lesson progress (${response.status})`);
    }
  }

  function debounceSave(key, callback, delay) {
    const existing = pendingSaves.get(key);
    if (existing) {
      clearTimeout(existing);
    }

    const timer = setTimeout(() => {
      pendingSaves.delete(key);
      callback();
    }, delay);

    pendingSaves.set(key, timer);
  }

  function attach(config) {
    const levelId = Number(config.levelId || 0);
    const lessonPath = normalizePath(config.lessonPath || window.location.pathname);
    const autosaveDelay = Number(config.autosaveDelay || 700);
    const saveKey = `${levelId}:${lessonPath}`;

    if (!levelId || typeof config.getState !== 'function') {
      return;
    }

    let restoring = true;
    let destroyed = false;

    const persist = async (isImmediate) => {
      if (destroyed || restoring) {
        return;
      }

      let state;
      try {
        state = config.getState();
      } catch (error) {
        return;
      }

      if (!state || typeof state !== 'object') {
        return;
      }

      const runner = () => {
        saveState(levelId, lessonPath, state).catch(() => {});
      };

      if (isImmediate) {
        runner();
        return;
      }

      debounceSave(saveKey, runner, autosaveDelay);
    };

    const scheduleSave = () => persist(false);
    const immediateSave = () => persist(true);

    Promise.resolve()
      .then(() => (typeof config.beforeLoad === 'function' ? config.beforeLoad() : null))
      .then(() => loadState(levelId, lessonPath))
      .then((state) => {
        if (destroyed) {
          return;
        }

        if (state && typeof config.applyState === 'function') {
          config.applyState(state);
        }
      })
      .catch(() => {})
      .finally(() => {
        restoring = false;
        if (typeof config.afterLoad === 'function') {
          config.afterLoad();
        }
      });

    window.addEventListener('pagehide', immediateSave);
    window.addEventListener('beforeunload', immediateSave);
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') {
        immediateSave();
      }
    });

    const intervalMs = Number(config.intervalMs || 5000);
    const intervalId = window.setInterval(scheduleSave, intervalMs);

    return {
      save: immediateSave,
      scheduleSave,
      destroy() {
        destroyed = true;
        window.clearInterval(intervalId);
      },
    };
  }

  window.PianovaLessonProgress = {
    attach,
  };
})();