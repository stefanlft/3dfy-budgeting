import streamlit as st
import pandas as pd
import sqlite3
import plotly.graph_objects as go
import random
import time
import hashlib
from datetime import datetime, timedelta
import os
from streamlit_cookies_controller import CookieController
import jwt
from supabase import create_client, Client

# Fetch variables with defaults as fallbacks
ADMIN_HASH = st.secrets["ADMIN_PASSWORD_HASH"]
DEBUG = st.secrets.get("DEBUG_MODE", False) # .get provides a fallback
SECRET_KEY = st.secrets["JWT_SECRET"]

# --- DATABASE SETUP ---
DB_FILE = "biz_vault.db"
if not DEBUG:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

controller = CookieController()

# --- DATABASE SETUP UPDATED ---
def init_db():
    if DEBUG:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS ledger
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT, type TEXT, category TEXT, description TEXT, amount REAL)''')
        c.execute('''CREATE TABLE IF NOT EXISTS users
                    (username TEXT PRIMARY KEY, password TEXT)''')

        # Default User: uses the hash from your .env file
        c.execute("SELECT * FROM users WHERE username='admin'")
        if not c.fetchone():
            # Fallback to a safe string if environment variable is missing
            stored_hash = ADMIN_HASH if ADMIN_HASH else "fallback_secure_hash"
            c.execute("INSERT INTO users VALUES (?, ?)", ("admin", stored_hash))

        conn.commit()
        conn.close()
    else:
        # 2. Check if admin exists
        response = supabase.table("users").select("username").eq("username", "admin").execute()


        # 3. If no admin found, create one
        if not response.data:
            stored_hash = ADMIN_HASH if ADMIN_HASH else "fallback_secure_hash"
            supabase.table("users").insert({
                "username": "admin",
                "password": stored_hash
            }).execute()


def add_user(username, password):
    hashed_pw = hashlib.sha256(password.encode()).hexdigest()
    if DEBUG:
        conn = sqlite3.connect(DB_FILE)
        try:
            conn.execute("INSERT INTO users VALUES (?, ?)", (username, hashed_pw))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()
    else:
        # Supabase Logic
        response = supabase.table("users").insert({"username": username, "password": hashed_pw}).execute()
        return len(response.data) > 0

def delete_user(username):
    if DEBUG:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("DELETE FROM users WHERE username=?", (username,))
        conn.commit()
        conn.close()
    else:
        supabase.table("users").delete().eq("username", username).execute()

def check_login(user, pw):
    hashed_pw = hashlib.sha256(pw.encode()).hexdigest()
    if DEBUG:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (user, hashed_pw))
        result = c.fetchone()
        conn.close()
        return result
    else:
        # Supabase Logic
        response = supabase.table("users").select("*").eq("username", user).eq("password", hashed_pw).execute()
        return response.data[0] if response.data else None

def update_user_password(username, new_password):
    hashed_pw = hashlib.sha256(new_password.encode()).hexdigest()
    if DEBUG:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("UPDATE users SET password=? WHERE username=?", (hashed_pw, username))
        conn.commit()
        conn.close()
    else:
        supabase.table("users").update({"password": hashed_pw}).eq("username", username).execute()

def get_ledger_data():
    """Centralized fetch for all ledger entries."""
    if DEBUG:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query("SELECT * FROM ledger", conn)
        conn.close()
    else:
        response = supabase.table("ledger").select("*").execute()
        df = pd.DataFrame(response.data)

    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
    return df

def get_ledger_summary(df):
    """Calculates high-level metrics for the Overview tab."""
    if df.empty:
        return 0.0, 0.0, 0.0, 0.0

    inbound = df[df['type'] == 'Inbound']['amount'].sum()
    outbound = df[df['type'] == 'Outbound']['amount'].sum()
    net = inbound - outbound
    margin = (net / inbound * 100) if inbound > 0 else 0
    return inbound, outbound, net, margin

def add_ledger_entry(date, t_type, category, description, amount):
    """Inserts a new transaction into the ledger."""
    if DEBUG:
        conn = sqlite3.connect(DB_FILE)
        conn.execute(
            "INSERT INTO ledger (date, type, category, description, amount) VALUES (?,?,?,?,?)",
            (date, t_type, category, description, amount)
        )
        conn.commit()
        conn.close()
    else:
        supabase.table("ledger").insert({
            "date": date,
            "type": t_type,
            "category": category,
            "description": description,
            "amount": amount
        }).execute()

def delete_ledger_entry(entry_id):
    """Deletes a transaction by its ID."""
    if DEBUG:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("DELETE FROM ledger WHERE id=?", (entry_id,))
        conn.commit()
        conn.close()
    else:
        supabase.table("ledger").delete().eq("id", entry_id).execute()

def delete_ledger_entry(entry_id):
    """
    Deletes a transaction from the ledger by its unique ID.
    Supports both Local SQLite (Debug) and Supabase (Production).
    """
    if DEBUG:
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM ledger WHERE id = ?", (entry_id,))
            conn.commit()

            # Check if a row was actually deleted
            if cursor.rowcount == 0:
                st.error(f"Entry ID {entry_id} not found in local database.")
                return False

            conn.close()
            return True
        except Exception as e:
            st.error(f"Local Delete Error: {e}")
            return False
    else:
        # Supabase Logic
        try:
            # eq("id", entry_id) targets the specific row
            response = supabase.table("ledger").delete().eq("id", entry_id).execute()

            # Supabase returns the deleted data in response.data
            if not response.data:
                st.error(f"Entry ID {entry_id} not found in Supabase.")
                return False

            return True
        except Exception as e:
            st.error(f"Production Delete Error: {e}")
            return False

def get_user_list():
    """Fetches all registered usernames for the Directory."""
    if DEBUG:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query("SELECT username FROM users", conn)
        conn.close()
    else:
        response = supabase.table("users").select("username").execute()
        df = pd.DataFrame(response.data)
    return df

init_db()

# --- JWT ZONE ---
def create_access_token(username):
    payload = {
        "sub": username,
        "exp": datetime.utcnow() + timedelta(days=30),  # Token expires in 30 days
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def decode_access_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload["sub"]
    except:
        return None

# --- UI CONFIG WITH DEBUG ---
st.set_page_config(
    page_title="3dfy Budget" + (" (DEBUG)" if DEBUG else ""),
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- OPTIONAL DEBUG OVERLAY ---
if DEBUG:
    with st.sidebar:
        st.write("Debug Cookies:", controller.getAll())
        st.info(f"Current User: {st.session_state.get('current_user')} | Auth: {st.session_state.get('authenticated')}")

# --- BRANDED CSS ---
# --- BRANDED CSS ---
brand_css = """
<style>
    /* Hide the Streamlit header bar */
    [data-testid="stHeader"] {
        display: none !important;
    }

    /* Hide the main menu and 'Made with Streamlit' footer (optional but recommended for a clean look) */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Adjust top padding so your content isn't cut off */
    .block-container {
        padding-top: 2rem !important;
    }

    /* Global Background and Text */
    .stApp { background-color: #122023 !important; color: #FFFFFF !important; }

    /* Hide the sidebar */
    [data-testid="stSidebar"] {display: none;}

    /* Center the title */
    h1 { color: #2ECC40 !important; text-align: center; }

    /* Primary Action Buttons */
    button[kind="primary"] { background-color: #2ECC40 !important; color: #122023 !important; border: none; font-weight: bold; }

    /* Secondary Danger Buttons */
    button[kind="secondary"] { border: 1px solid #E01B24 !important; color: #E01B24 !important; background-color: transparent; }

    /* Secure input boxes */
    .login-container { max-width: 400px; margin: auto; padding: 2rem; border: 1px solid #2ECC40; border-radius: 10px; background-color: rgba(46, 204, 64, 0.05); }

    /* Input focus border and shadow */
    input:focus {
        border-color: #2ECC40 !important;
        box-shadow: 0 0 10px rgba(46, 204, 64, 0.4) !important;
    }

    /* --- GLOBAL TABS CONTAINER --- */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: rgba(255, 255, 255, 0.03);
        padding: 10px 10px 0px 10px;
        border-radius: 10px 10px 0 0;
    }

    /* --- INACTIVE TAB STYLING --- */
    .stTabs [data-baseweb="tab"] {
        height: auto;
        padding: 12px 20px;
        color: #888888 !important;
        transition: all 0.3s ease;
        background-color: transparent !important;
        border-radius: 5px 5px 0 0;
    }

    /* --- HOVER EFFECT FOR INACTIVE TABS --- */
    .stTabs [data-baseweb="tab"]:hover {
        color: #FFFFFF !important;
        background-color: rgba(46, 204, 64, 0.05) !important;
    }

    /* --- GLOWING SELECTED TAB STYLING (Desktop) --- */
    .stTabs [aria-selected="true"] {
        background-color: rgba(46, 204, 64, 0.12) !important; /* Subtle background hint */
        color: #2ECC40 !important;
        font-weight: bold !important;
        border-bottom: 3px solid #2ECC40 !important;

        /* The Glow Effect: Multiple shadows layered for depth */
        box-shadow:
            0 4px 15px rgba(46, 204, 64, 0.4),  /* Primary green spread */
            0 0 30px rgba(46, 204, 64, 0.2);  /* Secondary softer spread */
    }

    /* Force inner paragraph text to be the correct green and glowing */
    .stTabs [aria-selected="true"] p {
        color: #2ECC40 !important;
        text-shadow: 0 0 5px rgba(46, 204, 64, 0.5); /* Subtle text glow */
    }

    /* --- MOBILE OPTIMIZATION --- */
    @media (max-width: 640px) {
        .stTabs [data-baseweb="tab-list"] {
            display: flex;
            flex-wrap: wrap; /* Allows tabs to wrap on very small screens */
            justify-content: center;
            padding: 5px;
            gap: 5px;
        }

        .stTabs [data-baseweb="tab"] {
            flex-grow: 1; /* Tabs expand to fill the row */
            text-align: center;
            font-size: 0.8rem;
            padding: 10px 5px;
            margin: 2px;
            background-color: rgba(255, 255, 255, 0.05) !important; /* Subtle box look */
            border-radius: 5px !important;
            border-bottom: none !important; /* Remove line on mobile */
        }

        /* The Glowing Tab on Mobile: Full block glow */
        .stTabs [aria-selected="true"] {
            background-color: rgba(46, 204, 64, 0.2) !important; /* Brighter hint on mobile */
            color: #2ECC40 !important;
            box-shadow:
                0 0 20px rgba(46, 204, 64, 0.5), /* Stronger glow spread */
                0 0 40px rgba(46, 204, 64, 0.2);
        }

        .stTabs [aria-selected="true"] p {
            color: #2ECC40 !important;
            font-weight: bold !important;
        }
    }
</style>
"""
st.markdown(brand_css, unsafe_allow_html=True)
st.markdown(brand_css, unsafe_allow_html=True)

# --- AUTH LOGIC ---
if DEBUG:
    st.session_state.authenticated = True
    st.session_state.current_user = "admin"

# --- PERSISTENT AUTH LOGIC ---
if 'authenticated' not in st.session_state:
    # Get all cookies to check if the component has finished initializing
    all_cookies = controller.getAll()

    # If the component hasn't sent data yet, it often returns an empty dict or None
    # We use a placeholder in session_state to prevent infinite loops
    if not all_cookies and 'init_checked' not in st.session_state:
        st.session_state.init_checked = True
        time.sleep(0.1) # Tiny bridge for JS-Python sync
        st.rerun()

    if not all_cookies:
        st.session_state.authenticated = False
        st.rerun()

    token = controller.get('remember_me')

    if token:
        user_from_token = decode_access_token(token)
        if user_from_token:
            st.session_state.authenticated = True
            st.session_state.current_user = user_from_token
        else:
            controller.remove('remember_me')
            st.session_state.authenticated = False
    else:
        st.session_state.authenticated = False


if not st.session_state.authenticated:
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("<h1>3dfy | Secure Access</h1>", unsafe_allow_html=True)

    _, center_col, _ = st.columns([1, 1, 1])
    with center_col:
        user = st.text_input("Username")
        password = st.text_input("Password", type="password")
        remember_me = st.checkbox("Stay signed in for 30 days") # NEW CHECKBOX

        if st.button("Login", type="primary", width='stretch'):
            if check_login(user, password):
                st.session_state.authenticated = True
                st.session_state.current_user = user

                if remember_me:
                    # Create a signed token instead of raw username
                    token = create_access_token(user)

                    controller.set('remember_me', token, max_age=2592000)

                    time.sleep(0.2)
                st.rerun()
            else:
                st.error("Invalid credentials")
    st.stop()

# --- HEADER & LOGOUT ---
col_title, col_logout = st.columns([9, 1])
with col_title: st.markdown("<h1>3dfy | Command Center</h1>", unsafe_allow_html=True)
with col_logout:
    if st.button("Log Out"):
        # 3. Clear the cookie on logout
        controller.remove('remember_me')
        st.session_state.authenticated = False
        st.session_state.current_user = None
        st.rerun()

# --- CALLBACKS ---
def set_extra_presets(pack=None, margin=None):
    if pack is not None: st.session_state.pack_cost_input = float(pack)
    if margin is not None: st.session_state.p_margin_input = float(margin)

# --- DIALOGS ---
@st.dialog("Finalize Transaction")
def push_to_ledger_dialog(weight, p_time, final_price):
    st.write(f"Recording sale for **{final_price:.2f} RON**")
    print_name = st.text_input("Name of the print:", placeholder="e.g. Articulated Dragon")

    if st.button("Confirm & Save", type="primary", use_container_width=True):
        if print_name:
            # The specific description format you requested
            desc = f"Print: {print_name} ({weight}g / {p_time}h)"

            add_ledger_entry(datetime.now().strftime("%Y-%m-%d"), "Inbound", "Product Sale", desc, round(final_price, 2))


            st.toast("Transaction recorded!", icon="✅")
            time.sleep(1)
            st.rerun()
        else:
            st.error("Please enter a name.")

@st.dialog("⚠️ Permanent Deletion")
def confirm_delete_dialog(transaction_id):
    st.write(f"Confirming deletion for **ID: {transaction_id}**.")
    if 'temp_word' not in st.session_state:
        st.session_state.temp_word = random.choice(["3DFY", "CONFIRM", "SECURE", "VOID", "DELETE"])
    word = st.session_state.temp_word
    user_input = st.text_input(f"Type **{word}** to authorize:")
    if st.button("Delete", type="primary", width='stretch', disabled=(user_input != word)):
        delete_ledger_entry(transaction_id)
        if 'temp_word' in st.session_state: del st.session_state.temp_word
        st.rerun()


@st.dialog("🛠️ User Security Control")
def user_management_dialog(username):
    # Use session state to toggle between "Edit Mode" and "Delete Confirmation"
    if f"confirm_delete_{username}" not in st.session_state:
        st.session_state[f"confirm_delete_{username}"] = False

    if st.session_state[f"confirm_delete_{username}"]:
        # --- DELETE CONFIRMATION VIEW ---
        st.error(f"🚨 PURGE WARNING: {username}")
        st.write("This action is permanent. All access will be revoked.")

        confirm_text = st.text_input(f"Type **{username}** to verify:")

        c1, c2 = st.columns(2)
        if c1.button("Abort", width='stretch'):
            st.session_state[f"confirm_delete_{username}"] = False
            st.rerun()

        if c2.button("Confirm Purge", type="primary", width='stretch', disabled=(confirm_text != username)):
            delete_user(username)
            # Clean up session state
            del st.session_state[f"confirm_delete_{username}"]
            st.toast(f"{username} purged.", icon="🗑️")
            time.sleep(1)
            st.rerun()

    else:
        # --- STANDARD EDIT VIEW ---
        st.markdown(f"Managing account: **{username}**")
        tab_pw, tab_danger = st.tabs(["🔐 Password Reset", "⚠️ Danger Zone"])

        with tab_pw:
            new_pw = st.text_input("New Security Key", type="password")
            if st.button("Update Password", type="primary", width='stretch'):
                if new_pw:
                    update_user_password(username, new_pw)
                    st.toast("Security updated!", icon="✅")
                    time.sleep(1)
                    st.rerun()

        with tab_danger:
            if username == "admin":
                st.info("Master Admin cannot be deleted.")
            else:
                st.write("Remove this user from the system?")
                if st.button(f"Purge", type="secondary", width='stretch'):
                    st.session_state[f"confirm_delete_{username}"] = True
                    st.rerun()

    if st.button("Exit", width='stretch'):
        st.session_state.active_manage_user = None # CLEAR TRIGGER
        if f"confirm_delete_{username}" in st.session_state:
            del st.session_state[f"confirm_delete_{username}"]

        # THIS IS THE KEY: Clear the trigger so the dialog doesn't loop
        st.session_state.active_manage_user = None
        st.rerun()

@st.dialog("🚀 Provision New Access")
def add_user_dialog():
    st.markdown("Enter credentials to authorize a new staff member.")

    new_un = st.text_input("IDENTIFIER", placeholder="username")
    new_pw = st.text_input("ACCESS KEY", type="password", placeholder="password")

    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("🎲 Gen Key", width='stretch'):
            random_pw = ''.join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=12))
            st.code(random_pw, width="stretch")

    with c2:
        if st.button("AUTHORIZE", type="primary", width='stretch'):
            if new_un and new_pw:
                if add_user(new_un, new_pw):
                    st.toast(f"Access granted: {new_un}", icon="🚀")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("ID collision: User exists.")

    if st.button("Close", width="stretch"):
        st.session_state.show_add_user = False # CLEAR TRIGGER
        st.rerun()

# --- DASHBOARD ---
# Dynamic tab creation based on user role
tabs_to_show = ["📊 Overview", "📑 All Transactions", "➕ Quick Entry", "🖨️ Cost Calculator"]
if st.session_state.current_user == "admin":
    tabs_to_show.append("👤 User Management")

all_tabs = st.tabs(tabs_to_show)

with all_tabs[0]: # Overview
    df = get_ledger_data()

    if df.empty:
        st.info("No data yet. Head over to the Calculator to log your first print!")
    else:
        # 1. Get Metrics
        rev, exp, net, margin = get_ledger_summary(df)

        # 2. Display Metrics Row
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Revenue", f"{rev:,.2f} RON")
        m2.metric("Expenses", f"{exp:,.2f} RON")

        m3.metric("Net Profit", f"{net:,.2f} RON",
                  delta="Positive" if net >= 0 else "Negative",
                  delta_color="normal" if net >= 0 else "inverse")

        m4.metric("Profit Margin", f"{margin:.1f}%",
                  delta="Healthy" if margin > 20 else "Low",
                  delta_color="normal" if margin > 20 else "inverse")

        # 3. Charting Logic
        df_sorted = df.sort_values('date')
        df_sorted['adj'] = df_sorted.apply(lambda x: x['amount'] if x['type'] == 'Inbound' else -x['amount'], axis=1)
        df_sorted['balance'] = df_sorted['adj'].cumsum()

        # Dynamic brand colors
        trend_color = "#2ECC40" if net >= 0 else "#E01B24"
        fill_color = "rgba(46, 204, 64, 0.2)" if net >= 0 else "rgba(224, 27, 36, 0.2)"

        fig = go.Figure(go.Scatter(
            x=df_sorted['date'], y=df_sorted['balance'],
            fill='tozeroy', line=dict(color=trend_color, width=3),
            fillcolor=fill_color
        ))

        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            height=350, margin=dict(l=0, r=0, t=10, b=0),
            xaxis=dict(showgrid=False, color="#FFFFFF"),
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", color="#FFFFFF"),
            hovermode="x unified"
        )
        st.plotly_chart(fig, use_container_width=True)

        # 4. Branded Forecast
        st.markdown(f"""
        <div style="padding:15px; border-radius:10px; border-left: 5px solid #2ECC40; background-color: rgba(46, 204, 64, 0.05);">
            <h3 style="margin:0; color:#2ECC40;">📈 Performance Insight</h3>
            <p style="margin:5px 0 0 0;">Maintain your <b>{margin:.1f}%</b> margin by targeting
            <b>{(rev * 1.1):,.2f} RON</b> in sales next month.</p>
        </div>
        """, unsafe_allow_html=True)

with all_tabs[1]: # Transactions
    df = get_ledger_data()
    if not df.empty:
        def color_t(v): return "background-color: rgba(46,204,64,0.12); color: #2ECC40;" if v=="Inbound" else "background-color: rgba(224,27,36,0.12); color: #E01B24;"
        st.dataframe(df.sort_values('id', ascending=False).style.map(color_t, subset=['type']), width='stretch', hide_index=True)
        st.divider()
        c_id, c_btn = st.columns([3, 1])
        with c_id: id_in = st.number_input("Enter ID:", step=1, min_value=0)
        with c_btn:
            st.write(" ")
            if st.button("Delete", type="secondary", width='stretch'): confirm_delete_dialog(id_in)

with all_tabs[2]: # Quick Entry
    in_cats, out_cats = ["Product Sale", "Custom Print", "Donation", "Subscription", "Other"], ["Filament", "Product Part", "Transport", "Software", "Marketing", "Rent", "Cash Out", "Salary", "Misc"]
    c1, c2 = st.columns(2); t_type = c1.radio("Direction", ["Inbound", "Outbound"], horizontal=True); t_date = c2.date_input("Date", datetime.now())
    c3, c4, c5 = st.columns(3); cat = c3.selectbox("Category", options=in_cats if t_type=="Inbound" else out_cats); desc = c4.text_input("Description"); amt = c5.number_input("Amount (RON)", min_value=0.0)
    if st.button("Confirm & Save", type="primary", width='stretch'):
        if desc and amt > 0:
            add_ledger_entry(t_date.strftime("%Y-%m-%d"), t_type, cat, desc, amt)
            st.toast("Saved!", icon="🚀"); time.sleep(1); st.rerun()

with all_tabs[3]: # 🖨️ Cost Calculator
    st.markdown("### 🖨️ 3D Print Price Calculator")

    # --- CALLBACKS ---
    def set_material(cost, label):
        st.session_state.f_cost_input = float(cost)
        st.toast(f"Switched to {label}", icon="🧵")

    def set_time_preset(hours, labor_min):
        st.session_state.p_time_input = float(hours)
        st.session_state.l_time_input = int(labor_min)

    # --- MATERIAL SECTION ---
    with st.container(border=True):
        st.caption("MATERIAL PRESETS")
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)

        m_col1.button("Eryone PLA (70 RON)", on_click=set_material, args=(70.0, "Eryone PLA"), use_container_width=True)
        m_col2.button("Prusa/Fillam. PLA (100 RON)", on_click=set_material, args=(100.0, "Prusament"), use_container_width=True)
        m_col3.button("Eryone/The Filam. PETG (60 RON)", on_click=set_material, args=(60.0, "Eryone/The Filament"), use_container_width=True)
        m_col4.button("Eryone TPU (100 RON)", on_click=set_material, args=(100.0, "Eryone TPU"), use_container_width=True)

        c1, c2, c3 = st.columns(3)
        f_weight = c1.number_input("Filament weight used (g)", min_value=0.0, value=20.0, step=1.0)

        if 'f_cost_input' not in st.session_state:
            st.session_state.f_cost_input = 70.0
        f_cost = c2.number_input("Spool cost (RON)", min_value=0.0, key="f_cost_input", step=5.0)

        s_weight = c3.number_input("Spool weight (g)", min_value=1.0, value=1000.0, step=250.0)

    # --- TIME & LABOR SECTION ---
    with st.container(border=True):
        st.caption("TIME & LABOR")

        # Quick Time Presets
        t_col1, t_col2, t_col3, _ = st.columns([1,1,1,2])
        t_col1.button("Quick Print (0.5h/5m)", on_click=set_time_preset, args=(0.5, 5), use_container_width=True)
        t_col2.button("Standard (2h/10m)", on_click=set_time_preset, args=(2.0, 10), use_container_width=True)
        t_col3.button("Long/Overnight (12h/20m)", on_click=set_time_preset, args=(12.0, 20), use_container_width=True)

        c4, c5, c6 = st.columns(3)
        if 'p_time_input' not in st.session_state: st.session_state.p_time_input = 0.7
        if 'l_time_input' not in st.session_state: st.session_state.l_time_input = 10

        p_time = c4.number_input("Print time (h)", min_value=0.1, key="p_time_input", step=0.5)
        p_draw = c5.number_input("Printer power draw (W)", min_value=0, value=120, step=10)
        e_cost = c6.number_input("Electricity cost (RON/kWh)", min_value=0.0, value=1.20, step=0.1)

        c7, c8 = st.columns(2)
        l_time = c7.number_input("Labour time (min)", min_value=0, key="l_time_input", step=5)
        h_rate = c8.number_input("Your hourly rate (RON/h)", min_value=0, value=30, step=5)

    # --- EXTRAS SECTION ---
    with st.container(border=True):
        st.caption("EXTRAS PRESETS")

        ex_col1, ex_col2 = st.columns(2)
        with ex_col1:
            st.write("Packaging:")
            e_c1, e_c2 = st.columns(2)
            e_c1.button("Env./Small (2 RON)", on_click=set_extra_presets, kwargs={'pack': 2.0}, use_container_width=True)
            e_c2.button("Box/Large (7 RON)", on_click=set_extra_presets, kwargs={'pack': 7.0}, use_container_width=True)

        with ex_col2:
            st.write("Profit Margin:")
            m_c1, m_c2 = st.columns(2)
            m_c1.button("Standard (60%)", on_click=set_extra_presets, kwargs={'margin': 60}, use_container_width=True)
            m_c2.button("High/Gift (150%)", on_click=set_extra_presets, kwargs={'margin': 150}, use_container_width=True)

        st.divider()
        c9, c10 = st.columns(2)
        if 'pack_cost_input' not in st.session_state: st.session_state.pack_cost_input = 2.0
        if 'p_margin_input' not in st.session_state: st.session_state.p_margin_input = 60.0

        pack_cost = c9.number_input("Packaging cost (RON)", min_value=0.0, key="pack_cost_input", step=0.5)
        p_margin = c10.number_input("Profit margin (%)", min_value=0, key="p_margin_input", step=5)

    # --- MATH ENGINE ---
    cost_material = (f_weight / s_weight) * f_cost
    cost_electricity = (p_draw / 1000) * p_time * e_cost
    cost_labor = (l_time / 60) * h_rate
    total_cost = cost_material + cost_electricity + cost_labor + pack_cost
    suggested_price = total_cost * (1 + (p_margin / 100))
    profit = suggested_price - total_cost

    # --- RESULTS ---
    st.markdown("---")
    res1, res2, res3 = st.columns(3)
    res1.metric("Total Cost", f"{total_cost:.2f} RON")
    with res2:
        st.markdown(f"""
            <div style="text-align: center; background: rgba(46,204,64,0.15); padding: 15px; border-radius: 10px; border: 1px solid #2ECC40;">
                <p style="margin:0; font-size: 0.8rem; opacity: 0.7; color: #FFFFFF;">SUGGESTED PRICE</p>
                <h2 style="margin:0; color: #2ECC40;">{suggested_price:.2f} RON</h2>
            </div>
        """, unsafe_allow_html=True)
    res3.metric("Your Profit", f"{profit:.2f} RON")

    # Trigger the dialog instead of a direct save
    if st.button("🚀 Push to Ledger", use_container_width=True, type="primary"):
        push_to_ledger_dialog(f_weight, p_time, suggested_price)

# --- USER MANAGEMENT TAB (ADMIN ONLY) ---
if st.session_state.current_user == "admin":
    with all_tabs[4]:
        # --- 1. DIALOG ORCHESTRATOR ---
        if st.session_state.get("active_manage_user"):
            user_management_dialog(st.session_state.active_manage_user)

        if st.session_state.get("show_add_user"):
            add_user_dialog()

        # --- 2. HEADER & ADD BUTTON ---
        col_head, col_add_btn = st.columns([3, 1])
        with col_head:
            st.subheader("👥 System Directory")
        with col_add_btn:
            st.write("<br>", unsafe_allow_html=True)
            if st.button("➕ New User", type="primary", use_container_width=True):
                st.session_state.show_add_user = True
                st.rerun()

        # --- 3. DIRECTORY LIST ---
        users_df = get_user_list()
        st.markdown('<hr style="margin-top:0; border: 1px solid rgba(46, 204, 64, 0.2)">', unsafe_allow_html=True)

        if users_df.empty:
            st.warning("No users found. This shouldn't happen if admin exists!")
        else:
            for _, row in users_df.iterrows():
                uname = row['username']
                is_admin = (uname == "admin")

                with st.container():
                    c_icon, c_name, c_role, c_action = st.columns([0.5, 3, 2, 1.5])

                    # Visual Identity
                    c_icon.write("⚡" if is_admin else "👤")
                    c_name.write(f"**{uname}**")

                    role_label = "MASTER" if is_admin else "STAFF"
                    c_role.markdown(
                        f"<span style='color: #2ECC40; opacity: 0.6; font-size: 0.8rem; letter-spacing: 1px;'>{role_label}</span>",
                        unsafe_allow_html=True
                    )

                    # Edit Action
                    if c_action.button("Edit", key=f"btn_{uname}", use_container_width=True):
                        st.session_state.active_manage_user = uname
                        st.rerun()

                    st.markdown('<hr style="margin:0.2rem 0; opacity:0.05">', unsafe_allow_html=True)

    # --- DATABASE BACKUP (ONLY VISIBLE IN DEBUG/LOCAL) ---
    if DEBUG:
        with st.expander("💾 Local Database Management"):
            st.info("Direct DB access is disabled in Production (Supabase).")
            # ... keep your existing Download/Upload code here ...
    with st.expander("💾 Database Management (Backup/Restore)"):
        st.warning("Handling the database file directly can corrupt your ledger if interrupted.")

        col_dl, col_ul = st.columns(2)

        with col_dl:
            st.markdown("#### Export Data")
            st.write("Download the current `biz_vault.db` file.")
            if os.path.exists(DB_FILE):
                with open(DB_FILE, "rb") as f:
                    st.download_button(
                        label="📥 Download Database",
                        data=f,
                        file_name=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
                        mime="application/octet-stream",
                        use_container_width=True
                    )
            else:
                st.error("Database file not found.")

        with col_ul:
            st.markdown("#### Import Data")
            st.write("Replace the current database with a backup file.")
            uploaded_db = st.file_uploader("Upload .db file", type=["db"])

            if uploaded_db is not None:
                if st.button("🔥 Overwrite Current DB", type="secondary", use_container_width=True):
                    # Save the uploaded file as the new DB_FILE
                    with open(DB_FILE, "wb") as f:
                        f.write(uploaded_db.getbuffer())
                    st.success("Database restored successfully!")
                    time.sleep(1)
                    st.rerun()