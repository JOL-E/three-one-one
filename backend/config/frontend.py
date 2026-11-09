"""The React app's screens, served as one page (DECISIONS #52).

WhiteNoise serves the built files themselves (/assets/…, /sw.js, and "/" as
index.html). A screen's URL like /inbox/3F9A is no file, so this view answers
it with index.html and the app's router takes over in the browser.
"""

from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse


def app_shell(request: HttpRequest) -> HttpResponse:
    index = settings.FRONTEND_DIR / "index.html"
    if not index.is_file():
        # In development the app runs on Vite's server (:5173), not here.
        raise Http404("The app isn't built. Run `npm run dev` in frontend/, or `npm run build`.")
    response = HttpResponse(index.read_bytes(), content_type="text/html; charset=utf-8")
    response["Cache-Control"] = "no-cache"  # a new release must show on the next visit
    return response
