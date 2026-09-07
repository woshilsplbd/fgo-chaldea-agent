"""Anonymous identity helpers for the production Agent provider boundary."""

import re
import uuid
from dataclasses import dataclass

from django.conf import settings
from django.core import signing


ANONYMOUS_COOKIE_NAME = "chaldea_anon_id"
ANONYMOUS_COOKIE_SALT = "agent.anonymous-user.v1"
ANONYMOUS_COOKIE_MAX_AGE = 365 * 24 * 60 * 60
_OPAQUE_ID_RE = re.compile(r"\A[0-9a-f]{32}\Z")


@dataclass(frozen=True)
class AnonymousIdentity:
    """Validated provider identity and the signed cookie value, when needed."""

    opaque_id: str
    provider_user_id: str
    cookie_value: str | None = None

    @property
    def needs_cookie(self):
        return self.cookie_value is not None


def _new_identity():
    opaque_id = uuid.uuid4().hex
    return AnonymousIdentity(
        opaque_id=opaque_id,
        provider_user_id=f"chaldea-web:{opaque_id}",
        cookie_value=signing.dumps(opaque_id, salt=ANONYMOUS_COOKIE_SALT),
    )


def resolve_identity(request):
    """Return a validated identity, silently replacing invalid cookie values."""
    raw_cookie = request.COOKIES.get(ANONYMOUS_COOKIE_NAME)
    if raw_cookie:
        try:
            opaque_id = signing.loads(
                raw_cookie,
                salt=ANONYMOUS_COOKIE_SALT,
                max_age=ANONYMOUS_COOKIE_MAX_AGE,
            )
        except (signing.BadSignature, signing.SignatureExpired, TypeError, ValueError):
            opaque_id = None
        if isinstance(opaque_id, str) and _OPAQUE_ID_RE.fullmatch(opaque_id):
            return AnonymousIdentity(
                opaque_id=opaque_id,
                provider_user_id=f"chaldea-web:{opaque_id}",
            )
    return _new_identity()


def attach_identity_cookie(response, identity):
    """Set a replacement cookie before a response (including SSE) is streamed."""
    if not identity.needs_cookie:
        return response
    response.set_cookie(
        ANONYMOUS_COOKIE_NAME,
        identity.cookie_value,
        max_age=ANONYMOUS_COOKIE_MAX_AGE,
        httponly=True,
        samesite="Lax",
        secure=not settings.DEBUG,
        path="/",
    )
    return response
