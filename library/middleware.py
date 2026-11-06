class ReaderPolicyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        panel = getattr(response, "editor_panel", False)
        editor = request.resolver_match and request.resolver_match.url_name == "document-editor"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; style-src 'self'; script-src 'self'; "
            "img-src 'self'; font-src 'self'; connect-src 'self'; form-action 'self'; "
            "base-uri 'none'; "
            + ("frame-src 'self'; " if editor else "")
            + ("frame-ancestors 'self'" if panel else "frame-ancestors 'none'")
        )
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "SAMEORIGIN" if panel else "DENY"
        response.headers["Cache-Control"] = "no-store"
        return response
