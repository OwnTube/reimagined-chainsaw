/* Experimental transport adapter. Run before all captured client scripts. */
(() => {
  'use strict';
  const local = value => {
    const url = new URL(value, location.href);
    if (url.hostname === 'www.youtube.com' || url.hostname === 'youtube.com') {
      if (url.pathname.startsWith('/youtubei/')) return location.origin + url.pathname + url.search;
    }
    if (url.origin !== location.origin) throw new TypeError('External request blocked by MewTube');
    return url.href;
  };
  const originalFetch = window.fetch.bind(window);
  window.fetch = async (input, init = {}) => {
    const request = new Request(input instanceof Request ? input : new URL(input, location.href), init);
    const url = local(request.url);
    const headers = new Headers(request.headers);
    headers.set('X-MewTube', '1');
    headers.delete('Authorization');
    headers.delete('X-Goog-Visitor-Id');
    // Request.body is a ReadableStream even for a string-backed Request. Passing
    // that stream as a new RequestInit body forces streaming uploads/HTTP2 and
    // Chromium reports ERR_ALPN_NEGOTIATION_FAILED against the HTTP/1 server.
    const body = ['GET', 'HEAD'].includes(request.method) ? undefined : await request.arrayBuffer();
    if (body && body.byteLength > 1024 * 1024) throw new TypeError('Client API request exceeds 1 MB');
    return originalFetch(url, {method:request.method, headers, body, credentials:'same-origin',
      mode:'same-origin', cache:request.cache, redirect:request.redirect, signal:request.signal,
      referrerPolicy:'same-origin', keepalive:request.keepalive});
  };
  const open = XMLHttpRequest.prototype.open;
  const send = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function(method, url, ...rest) {
    return open.call(this, method, local(url), ...rest);
  };
  XMLHttpRequest.prototype.send = function(body) {
    this.setRequestHeader('X-MewTube', '1');
    return send.call(this, body);
  };
  navigator.sendBeacon = () => false;
  if (navigator.serviceWorker) navigator.serviceWorker.register = () => Promise.reject(new Error('Disabled on local instance'));
  addEventListener('DOMContentLoaded', () => {
    if (window.ytcfg?.set) window.ytcfg.set({INNERTUBE_HOST_OVERRIDE: location.origin,
      INNERTUBE_API_KEY: 'local', LOGGED_IN: false, DELEGATED_SESSION_ID: '',
      VISITOR_DATA: '', SESSION_INDEX: '0'});
    document.addEventListener('click', event => {
      if(event.defaultPrevented || event.button!==0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      const anchor = event.target.closest?.('a');
      if (!anchor) return;
      const url = new URL(anchor.href, location.href);
      if (url.origin === location.origin && url.searchParams.get('signin') === '1') {
        event.preventDefault();event.stopImmediatePropagation();location.assign(url.pathname+url.search);
      } else if(url.origin===location.origin &&
        ((url.pathname==='/watch' && /^[A-Za-z0-9_-]{11}$/.test(url.searchParams.get('v') || '')) ||
         url.pathname==='/feed/subscriptions' || /^\/channel\/[A-Za-z0-9_-]{11}$/.test(url.pathname) ||
         (url.pathname==='/playlist' && url.searchParams.get('list')==='LL'))) {
        // The captured SPA's POST /watch envelope is not implemented. A full
        // local navigation loads the pinned watch shell and its local bootstrap,
        // while keeping the actual YouTube player instead of the independent UI.
        event.preventDefault();event.stopImmediatePropagation();location.assign(url.href);
      }
    }, true);
  });
})();
