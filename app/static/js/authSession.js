(function () {
    const TOKEN_KEY = 'rro.tabAuthToken';

    function getTokenFromUrl() {
        const url = new URL(window.location.href);
        return url.searchParams.get('auth_token');
    }

    function getStoredToken() {
        try {
            return window.sessionStorage.getItem(TOKEN_KEY);
        } catch (error) {
            return null;
        }
    }

    function storeToken(token) {
        if (!token) return;
        try {
            window.sessionStorage.setItem(TOKEN_KEY, token);
        } catch (error) {
            // Ignore storage errors and continue with URL-based auth only.
        }
    }

    function clearToken() {
        try {
            window.sessionStorage.removeItem(TOKEN_KEY);
        } catch (error) {
            // Ignore storage errors.
        }
    }

    function getToken() {
        const urlToken = getTokenFromUrl();
        if (urlToken) {
            storeToken(urlToken);
            return urlToken;
        }
        return getStoredToken();
    }

    function appendAuthToken(pathOrUrl) {
        const token = getToken();
        if (!token || !pathOrUrl) return pathOrUrl;

        if (pathOrUrl.startsWith('#') || pathOrUrl.startsWith('mailto:') || pathOrUrl.startsWith('tel:') || pathOrUrl.startsWith('javascript:')) {
            return pathOrUrl;
        }

        const url = new URL(pathOrUrl, window.location.origin);
        if (url.origin !== window.location.origin) {
            return pathOrUrl;
        }

        url.searchParams.set('auth_token', token);
        return `${url.pathname}${url.search}${url.hash}`;
    }

    function getAuthHeaders(existingHeaders) {
        const token = getToken();
        return token ? { ...existingHeaders, 'X-RRO-Auth-Token': token } : existingHeaders;
    }

    function decorateInternalLinks() {
        document.querySelectorAll('a[href]').forEach((link) => {
            const href = link.getAttribute('href');
            if (!href) return;
            link.setAttribute('href', appendAuthToken(href));
        });
    }

    window.RROAuth = {
        appendAuthToken,
        clearToken,
        decorateInternalLinks,
        getAuthHeaders,
        getToken,
    };

    getToken();
    document.addEventListener('DOMContentLoaded', decorateInternalLinks);
})();