import streamlit as st
import pandas as pd
import sqlite3
import plotly.graph_objects as go
import random
import time
import hashlib
from datetime import datetime

# --- DATABASE SETUP ---
DB_FILE = "biz_vault.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS ledger
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  date TEXT, type TEXT, category TEXT, description TEXT, amount REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY, password TEXT)''')

    # Default User: admin | Pass: 3dfy2024
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        hashed_pw = '3da5bcfb6ca55e01da6fc4c0019a5cae338564bd6e42f0b8ad582cb2570dc3b2'
        c.execute("INSERT INTO users VALUES (?, ?)", ("admin", hashed_pw))

    conn.commit()
    conn.close()

def add_user(username, password):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    hashed_pw = hashlib.sha256(password.encode()).hexdigest()
    try:
        c.execute("INSERT INTO users VALUES (?, ?)", (username, hashed_pw))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def delete_user(username):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE username=?", (username,))
    conn.commit()
    conn.close()

def check_login(user, pw):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    hashed_pw = hashlib.sha256(pw.encode()).hexdigest()
    c.execute("SELECT * FROM users WHERE username=? AND password=?", (user, hashed_pw))
    result = c.fetchone()
    conn.close()
    return result

init_db()

# --- UI CONFIG ---
st.set_page_config(page_title="3dfy Budget", layout="wide", initial_sidebar_state="collapsed")

# --- BRANDED CSS ---
brand_css = """
<style>
    .stApp { background-color: #122023 !important; color: #FFFFFF !important; }
    [data-testid="stSidebar"] {display: none;}
    h1 { color: #2ECC40 !important; text-align: center; }
    .stTabs [aria-selected="true"] { background-color: #2ECC40 !important; color: #122023 !important; }
    button[kind="primary"] { background-color: #2ECC40 !important; color: #122023 !important; border: none; }
    button[kind="secondary"] { border: 1px solid #E01B24 !important; color: #E01B24 !important; background-color: transparent; }
    .login-container { max-width: 400px; margin: auto; padding: 2rem; border: 1px solid #2ECC40; border-radius: 10px; background-color: rgba(46, 204, 64, 0.05); }
</style>
"""
st.markdown(brand_css, unsafe_allow_html=True)

# --- AUTH LOGIC ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.current_user = None

if not st.session_state.authenticated:
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("<h1>3dfy | Secure Access</h1>", unsafe_allow_html=True)
    _, center_col, _ = st.columns([1, 1, 1])
    with center_col:
        user = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login", type="primary", width='stretch'):
            if check_login(user, password):
                st.session_state.authenticated = True
                st.session_state.current_user = user
                st.rerun()
            else:
                st.error("Invalid credentials")
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# --- HEADER & LOGOUT ---
col_title, col_logout = st.columns([9, 1])
with col_title: st.markdown("<h1>3dfy | Command Center</h1>", unsafe_allow_html=True)
with col_logout:
    if st.button("Log Out"):
        st.session_state.authenticated = False
        st.session_state.current_user = None
        st.rerun()

# --- DIALOGS ---
@st.dialog("⚠️ Permanent Deletion")
def confirm_delete_dialog(transaction_id):
    st.write(f"Confirming deletion for **ID: {transaction_id}**.")
    if 'temp_word' not in st.session_state:
        st.session_state.temp_word = random.choice(["3DFY", "CONFIRM", "SECURE", "VOID", "DELETE"])
    word = st.session_state.temp_word
    user_input = st.text_input(f"Type **{word}** to authorize:")
    if st.button("Delete", type="primary", width='stretch', disabled=(user_input != word)):
        conn = sqlite3.connect(DB_FILE); conn.execute("DELETE FROM ledger WHERE id=?", (int(transaction_id),)); conn.commit(); conn.close()
        if 'temp_word' in st.session_state: del st.session_state.temp_word
        st.rerun()

# --- DASHBOARD ---
# Dynamic tab creation based on user role
tabs_to_show = ["📊 Overview", "📑 All Transactions", "➕ Quick Entry"]
if st.session_state.current_user == "admin":
    tabs_to_show.append("👤 User Management")

all_tabs = st.tabs(tabs_to_show)

# Standard Tabs Logic
with all_tabs[0]: # Overview
    conn = sqlite3.connect(DB_FILE); df = pd.read_sql_query("SELECT * FROM ledger", conn); conn.close()
    if df.empty: st.info("No data yet.")
    else:
        df['date'] = pd.to_datetime(df['date'])
        inbound = df[df['type'] == 'Inbound']['amount'].sum(); outbound = df[df['type'] == 'Outbound']['amount'].sum(); net = inbound - outbound
        m1, m2, m3 = st.columns(3)
        m1.metric("Revenue", f"{inbound:,.2f} RON"); m2.metric("Expenses", f"{outbound:,.2f} RON"); m3.metric("Net Profit", f"{net:,.2f} RON")
        df_sorted = df.sort_values('date'); df_sorted['adj'] = df_sorted.apply(lambda x: x['amount'] if x['type'] == 'Inbound' else -x['amount'], axis=1); df_sorted['balance'] = df_sorted['adj'].cumsum()
        trend_color = '#2ECC40' if net >= 0 else '#E01B24'
        fig = go.Figure(go.Scatter(x=df_sorted['date'], y=df_sorted['balance'], fill='tozeroy', line=dict(color=trend_color)))
        fig.update_layout(paper_bgcolor='#122023', plot_bgcolor='#122023', height=350, margin=dict(l=0,r=0,t=10,b=0))
        st.plotly_chart(fig, width='stretch')

with all_tabs[1]: # Transactions
    conn = sqlite3.connect(DB_FILE); df = pd.read_sql_query("SELECT * FROM ledger", conn); conn.close()
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
            conn = sqlite3.connect(DB_FILE); conn.execute("INSERT INTO ledger (date, type, category, description, amount) VALUES (?,?,?,?,?)", (t_date.strftime("%Y-%m-%d"), t_type, cat, desc, amt)); conn.commit(); conn.close()
            st.toast("Saved!", icon="🚀"); time.sleep(1); st.rerun()

# --- USER MANAGEMENT TAB (ADMIN ONLY) ---
if st.session_state.current_user == "admin":
    with all_tabs[3]:
        st.subheader("3dfy User Registry")

        # Display Current Users
        conn = sqlite3.connect(DB_FILE)
        users_df = pd.read_sql_query("SELECT username FROM users", conn)
        conn.close()

        col_list, col_add = st.columns([1, 1])

        with col_list:
            st.markdown("**Existing Users**")
            st.dataframe(users_df, width='stretch', hide_index=True)

            # Delete User Logic
            user_to_del = st.selectbox("Select User to Remove", users_df['username'])
            if st.button("Delete User", type="secondary"):
                if user_to_del == "admin":
                    st.error("The master admin account cannot be deleted.")
                elif user_to_del == st.session_state.current_user:
                    st.error("You cannot delete the account you are currently using.")
                else:
                    delete_user(user_to_del)
                    st.success(f"User {user_to_del} removed.")
                    time.sleep(1)
                    st.rerun()

        with col_add:
            st.markdown("**Add New User**")
            new_un = st.text_input("New Username", key="new_un")
            new_pw = st.text_input("New Password", type="password", key="new_pw")
            if st.button("Register User", type="primary"):
                if new_un and new_pw:
                    if add_user(new_un, new_pw):
                        st.success(f"User {new_un} added successfully.")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Username already exists.")
                else:
                    st.error("Please fill in both fields.")