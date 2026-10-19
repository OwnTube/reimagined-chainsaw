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
  window.fetch = (input, init = {}) => {
    try {
      const request = new Request(local(input instanceof Request ? input.url : input), input instanceof Request ? input : undefined);
      const headers = new Headers(init.headers || request.headers);
      headers.set('X-MewTube', '1');
      headers.delete('Authorization');
      headers.delete('X-Goog-Visitor-Id');
      return originalFetch(request, {...init, headers, credentials: 'same-origin'});
    } catch (error) { return Promise.reject(error); }
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
    const banner = document.createElement('div');
    banner.style.cssText = 'position:fixed;bottom:12px;left:12px;z-index:2147483647;background:#151515;color:#fff;padding:12px;border-radius:8px;font:14px system-ui';
    const link = document.createElement('a');
    link.href = '/'; link.textContent = 'MewTube · Experimental captured client · Open independent UI';
    link.addEventListener('click', event => {event.preventDefault();event.stopImmediatePropagation();location.assign('/');});
    link.style.color = '#fff'; banner.append(link); document.body.append(banner);
    document.addEventListener('click', event => {
      const anchor = event.target.closest?.('a');
      if (!anchor) return;
      const url = new URL(anchor.href, location.href);
      if (url.origin === location.origin && url.searchParams.get('signin') === '1') {
        event.preventDefault();event.stopImmediatePropagation();location.assign('/?signin=1');
      }
    }, true);
  });
})();
