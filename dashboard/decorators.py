from functools import wraps
from django.core.exceptions import PermissionDenied


def role_required(allowed_roles):
    """
    Simple role-based guard.
    Expects the authenticated user to have a `role` attribute.
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            user = getattr(request, "user", None)
            if not user or not getattr(user, "role", None):
                raise PermissionDenied

            if user.role not in allowed_roles:
                raise PermissionDenied

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator

