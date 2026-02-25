# app/auth/__init__.py
# Makes 'auth' a Python package.
# Auth logic is split across three modules:
#   security.py     — bcrypt password hashing
#   auth.py         — JWT creation and verification
#   dependencies.py — FastAPI dependency functions (get_current_user, etc.)
