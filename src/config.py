import streamlit as st

# Centralized secret management and configuration
ADMIN_PASSWORD_HASH = st.secrets.get("ADMIN_PASSWORD_HASH")
DEBUG_MODE = st.secrets.get("DEBUG_MODE", False)
JWT_SECRET = st.secrets.get("JWT_SECRET")
SUPABASE_URL = st.secrets.get("SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY")
DEFAULT_PREDICTION_DAYS = st.secrets.get("DEFAULT_PREDICTION_DAYS")
VERSION = "1.1.2-stable"