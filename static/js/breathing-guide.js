/* Breathing timing engine. Pure timing, no DOM: the page script draws what it reports.
   Time comes from performance.now() on every animation frame (no interval timers, so no drift); paused time is not counted. */
(function () {
  'use strict';

  var PATTERNS = {
    box: { name: 'Box Breathing', phases: [['inhale', 4], ['hold', 4], ['exhale', 4], ['hold', 4]] },
    '478': { name: '4-7-8 Breathing', phases: [['inhale', 4], ['hold', 7], ['exhale', 8]] },
    diaphragmatic: { name: 'Diaphragmatic Breathing', phases: [['inhale', 4], ['exhale', 6]] },
    pursed: { name: 'Pursed-lip Breathing', phases: [['inhale', 2], ['exhale', 4]] }
  };

  function cycleSeconds(p) { return p.phases.reduce(function (a, ph) { return a + ph[1]; }, 0); }

  // handlers: onPhase(loc) at each phase change, onTick(info) every frame, onDone(completed) once at the end.
  function create(handlers) {
    var s = { pattern: null, totalMs: 0, active: 0, last: 0, raf: 0, running: false, paused: false, key: '' };

    function locate(ms) {
      var ph = s.pattern.phases, cycleMs = cycleSeconds(s.pattern) * 1000;
      var cycle = Math.floor(ms / cycleMs), rest = ms - cycle * cycleMs;
      for (var i = 0; i < ph.length; i++) {
        var d = ph[i][1] * 1000;
        if (rest < d || i === ph.length - 1) {
          return { idx: i, cycle: cycle, name: ph[i][0], secs: ph[i][1], intoMs: Math.min(rest, d),
                   left: Math.max(1, Math.ceil((d - rest) / 1000)),
                   cycles: Math.ceil(s.totalMs / cycleMs) };
        }
        rest -= d;
      }
    }
    function info(loc) {
      loc.remaining = Math.ceil((s.totalMs - s.active) / 1000);
      loc.progress = s.active / s.totalMs;
      return loc;
    }
    function frame() {
      if (!s.running || s.paused) return;
      var now = performance.now();
      s.active += now - s.last;
      s.last = now;
      if (s.active >= s.totalMs) {
        s.active = s.totalMs;
        s.running = false;
        var end = info(locate(s.totalMs - 1));
        end.remaining = 0;
        handlers.onTick(end);
        handlers.onDone(true);
        return;
      }
      var loc = info(locate(s.active)), key = loc.cycle + ':' + loc.idx;
      if (key !== s.key) { s.key = key; handlers.onPhase(loc); }
      handlers.onTick(loc);
      s.raf = requestAnimationFrame(frame);
    }

    return {
      start: function (key, minutes) {
        cancelAnimationFrame(s.raf);
        s.pattern = PATTERNS[key];
        s.totalMs = minutes * 60000;
        s.active = 0; s.key = ''; s.running = true; s.paused = false;
        s.last = performance.now();
        s.raf = requestAnimationFrame(frame);
      },
      pause: function () { if (s.running && !s.paused) { s.paused = true; cancelAnimationFrame(s.raf); } },
      resume: function () {
        if (!s.running || !s.paused) return;
        s.paused = false;
        s.last = performance.now();
        s.raf = requestAnimationFrame(frame);
      },
      stop: function () {
        if (!s.running) return;
        s.running = false;
        cancelAnimationFrame(s.raf);
        handlers.onDone(false);
      },
      // Silent teardown (page unload, restarting): no onDone.
      cancel: function () { s.running = false; cancelAnimationFrame(s.raf); },
      current: function () { return s.running ? info(locate(s.active)) : null; },
      elapsedSeconds: function () { return s.active / 1000; },
      isRunning: function () { return s.running; },
      isPaused: function () { return s.paused; }
    };
  }

  window.MFHBreath = { PATTERNS: PATTERNS, create: create, cycleSeconds: cycleSeconds };
})();
