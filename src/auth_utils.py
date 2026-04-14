import jwt
import streamlit as st
from datetime import datetime, timedelta
import config

SECRET_KEY = config.JWT_SECRET

def create_access_token(username):
    payload = {
        "sub": username,
        "exp": datetime.utcnow() + timedelta(days=30),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def decode_access_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload["sub"]
    except:
        return None

def logout(controller):
    controller.remove('remember_me')
    st.session_state.authenticated = False
    st.session_state.current_user = None