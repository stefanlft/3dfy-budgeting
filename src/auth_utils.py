import jwt
import streamlit as st
from datetime import datetime, timedelta, timezone
import config

SECRET_KEY = config.JWT_SECRET or "3dfy-secure-fallback-key-change-me"

def create_access_token(username):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(username),
        "exp": now + timedelta(days=30),
        "iat": now
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    # Ensure token is a string (PyJWT < 2.0 returns bytes)
    return token.decode('utf-8') if isinstance(token, bytes) else token

def decode_access_token(token):
    if not token:
        return None
    try:
        # Added leeway to handle slight clock desync between sessions
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"], leeway=10)
        return payload["sub"]
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, Exception):
        return None

def logout(controller):
    if controller.get('remember_me'):
        controller.remove('remember_me')
    st.session_state.authenticated = False
    st.session_state.current_user = None