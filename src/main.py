import streamlit as st
import pandas as pd
import sqlite3
import plotly.graph_objects as go
import random
import numpy as np
import time
from sklearn.linear_model import Ridge
from prophet import Prophet
from sklearn.preprocessing import PolynomialFeatures
from sklearn.pipeline import make_pipeline
import hashlib
from datetime import datetime, timedelta
import os
from streamlit_cookies_controller import CookieController
import db
import ui_styles
import auth_utils
import config

controller = CookieController()
db.init_db(config.DEBUG_MODE)
ui_styles.init_page(config.DEBUG_MODE)
ui_styles.apply_custom_css()

if config.DEBUG_MODE:
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
        user_from_token = auth_utils.decode_access_token(token)
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
            if db.user_check_login(user, password):
                st.session_state.authenticated = True
                st.session_state.current_user = user

                if remember_me:
                    token = auth_utils.create_access_token(user)

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
        auth_utils.logout(controller)
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

    if st.button("Confirm & Save", type="primary", width="stretch"):
        if print_name:
            # The specific description format you requested
            desc = f"Print: {print_name} ({weight}g / {p_time}h)"

            db.ledger_add_entry(datetime.now().strftime("%Y-%m-%d"), "Inbound", "Product Sale", desc, round(final_price, 2))


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
        db.ledger_delete_entry(transaction_id)
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
            db.user_delete(username)
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
                    db.user_update_password(username, new_pw)
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
                if db.user_add(new_un, new_pw):
                    st.toast(f"Access granted: {new_un}", icon="🚀")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("ID collision: User exists.")

    if st.button("Close", width="stretch"):
        st.session_state.show_add_user = False # CLEAR TRIGGER
        st.rerun()

@st.dialog("Fulfill Order")
def fulfill_order_dialog(order_id, product, price):
    st.write(f"Complete order for **{product}**?")
    st.write(f"This will move the amount of **{price:.2f} RON** into the Ledger.")
    if st.button("Confirm Fulfill", type="primary", width="stretch"):
        # Add to ledger
        db.ledger_add_entry(datetime.now().strftime("%Y-%m-%d"), "Inbound", "Product Sale", f"Order Fulfill: {product}", price)
        # Mark order as complete
        db.orders_complete_entry(order_id)
        st.toast("Order fulfilled and recorded!", icon="✅")
        time.sleep(1)
        st.rerun()

@st.dialog("➕ Register New Order")
def register_order_dialog():
    c_name, c_contact = st.columns(2)
    ord_name = c_name.text_input("Customer Name", placeholder="e.g. John Doe")
    ord_contact = c_contact.text_input("Insta / Phone", placeholder="@username or 07xx...")

    ord_product = st.text_area("Product Details", placeholder="Describe the print, scale, color, or special requirements...", height=100)

    c3, c4, c5 = st.columns(3)
    ord_price = c3.number_input("Final Price (RON)", min_value=0.0, step=10.0)
    ord_deadline = c4.date_input("Deadline", datetime.now() + timedelta(days=7))
    ord_method = c5.selectbox("Delivery Method", ["Personal", "Sameday", "FAN", "DHL", "DPD", "FedEx", "UPS", "Other"])

    ord_location = st.text_input("Location to Deliver", placeholder="Full address or pickup point")

    if st.button("Save Order to Queue", type="primary", width="stretch"):
        if ord_product and ord_name:
            db.orders_add_entry(ord_product, ord_name, ord_contact, ord_price,
                               ord_deadline.strftime("%Y-%m-%d"),
                               ord_location, ord_method)
            st.toast("Order Registered!", icon="📦")
            time.sleep(1)
            st.rerun()
        else:
            st.error("Please provide Product details and Customer name.")


# --- DASHBOARD ---
# Dynamic tab creation based on user role
tabs_to_show = ["📊 Overview", "📦 Current Orders", "🖨️ Cost Calculator", "➕ Quick Entry", "📑 All Transactions"]
if st.session_state.current_user == "admin":
    tabs_to_show.append("👤 User Management")

all_tabs = st.tabs(tabs_to_show)

with all_tabs[0]: # Overview
    df = db.ledger_get_data()

    if df.empty:
        st.info("No data yet. Head over to the Calculator to log your first print!")
    else:
        # 1. Get Metrics
        rev, exp, net, margin = db.ledger_get_summary(df)

        # 2. Display Metrics Row
        m1, m2, m3, m4 = st.columns(4)
        metrics = [
            ("Revenue", f"{rev:,.0f} RON", "#FFFFFF"),
            ("Expenses", f"{exp:,.0f} RON", "#E01B24"),
            ("Net Profit", f"{net:,.0f} RON", "#2ECC40"),
            ("Margin", f"{margin:.1f}%", "#2196F3")
        ]

        for col, (label, val, color) in zip([m1, m2, m3, m4], metrics):
            col.markdown(f"""
                <div class="glass-card kpi-box">
                    <div class="kpi-label">{label}</div>
                    <div class="kpi-value" style="color: {color}">{val}</div>
                </div>
            """, unsafe_allow_html=True)

        st.write("<br>", unsafe_allow_html=True)

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
            fillcolor=fill_color,
            name="Current Balance",
            hovertemplate="Balance: %{y:.2f} RON<extra></extra>",
            showlegend=True
        ))

        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            height=400, margin=dict(l=0, r=0, t=40, b=40),
            xaxis=dict(showgrid=False, color="#FFFFFF"),
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", color="#FFFFFF"),
            hovermode="x unified",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                font=dict(size=10, color="#FFFFFF")
            )
        )

        # 4. ML Prediction Logic (Linear Regression)
        chart_container = st.container()

        pred_days = st.slider("Forecast Horizon (Days)", min_value=7, max_value=365, value=config.DEFAULT_PREDICTION_DAYS)

        projected_profit = 0.0
        if len(df_sorted) > 2:
            # --- SMART FEATURE ENGINEERING ---
            # Prepare data for Prophet: requires 'ds' (datetime) and 'y' (value)
            prophet_df = df_sorted[['date', 'balance']].rename(columns={'date': 'ds', 'balance': 'y'})

            # Initialize and fit Prophet model
            # Prophet automatically handles trends, seasonality (weekly, yearly), and holidays
            # changepoint_prior_scale can be adjusted to make the trend more flexible
            model = Prophet(
                growth='linear',
                seasonality_mode='additive',
                weekly_seasonality=True,
                daily_seasonality=False, # Daily seasonality might be too granular for cumulative balance
                yearly_seasonality=False, # Requires more than a year of data
                changepoint_prior_scale=0.05 # Default is 0.05, can increase for more flexibility
            )
            model.fit(prophet_df)

            # Create a DataFrame with future dates for prediction
            future = model.make_future_dataframe(periods=pred_days, include_history=False)
            forecast = model.predict(future)

            # Combine historical and forecasted data for plotting
            # Ensure the prediction starts from the last actual data point
            plot_dates = pd.concat([df_sorted['date'], forecast['ds']])
            plot_yhat = pd.concat([df_sorted['balance'], forecast['yhat']])
            plot_yhat_lower = pd.concat([df_sorted['balance'], forecast['yhat_lower']])
            plot_yhat_upper = pd.concat([df_sorted['balance'], forecast['yhat_upper']])

            # Calculate expected profit over the selected period based on the trend
            last_actual_balance = df_sorted['balance'].iloc[-1]
            predicted_final_balance = forecast['yhat'].iloc[-1]
            projected_profit = predicted_final_balance - last_actual_balance

            # Add prediction trace to the figure
            fig.add_trace(go.Scatter(
                x=plot_dates,
                y=plot_yhat,
                name=f"ML Trend ({pred_days}d)",
                line=dict(color="#FFC107", width=2, dash='dash'),
                # Removed fill="tozeroy" for the prediction line itself
                hovertemplate="Predicted: %{y:.2f} RON<extra></extra>"
            ))

            # Add confidence interval as a shaded area
            fig.add_trace(go.Scatter(
                x=plot_dates,
                y=plot_yhat_upper,
                mode='lines',
                line=dict(width=0),
                showlegend=False,
                hoverinfo='skip' # Don't show hover for this invisible line
            ))
            fig.add_trace(go.Scatter(
                x=plot_dates,
                y=plot_yhat_lower,
                mode='lines',
                line=dict(width=0),
                fill='tonexty', # Fills the area between this trace and the previous one (yhat_upper)
                fillcolor="rgba(255, 193, 7, 0.1)",
                name='Confidence Interval',
                hovertemplate="Lower: %{y:.2f} RON<extra></extra>"
            ))

        with chart_container:
            st.plotly_chart(
                fig,
                width="stretch",
                config={'displaylogo': False, 'modeBarButtonsToRemove': ['lasso2d', 'select2d']}
            )

        # 5. Branded Forecasts
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            st.markdown(f"""
            <div style="padding:15px; border-radius:10px; border-left: 5px solid #2ECC40; background-color: rgba(46, 204, 64, 0.05); height: 100%;">
                <h3 style="margin:0; color:#2ECC40; font-size: 1.1rem;">📈 Performance Insight</h3>
                <p style="margin:5px 0 0 0; font-size: 0.9rem;">Maintain your <b>{margin:.1f}%</b> margin by targeting
                <b>{(rev * 1.1):,.2f} RON</b> in sales next month.</p>
            </div>
            """, unsafe_allow_html=True)

        with f_col2:
            st.markdown(f"""
            <div style="padding:15px; border-radius:10px; border-left: 5px solid #FFC107; background-color: rgba(255, 193, 7, 0.05); height: 100%;">
                <h3 style="margin:0; color:#FFC107; font-size: 1.1rem;">🔮 {pred_days}-Day Projection</h3>
                <p style="margin:5px 0 0 0; font-size: 0.9rem;">Based on ML trends, your projected profit for the next {pred_days} days is
                <b>{projected_profit:,.2f} RON</b>.</p>
            </div>
            """, unsafe_allow_html=True)

with all_tabs[1]: # Current Orders
    st.markdown("### 📦 Active Order Management")

    if st.button("➕ Register New Order", type="primary", width="stretch"):
        register_order_dialog()

    st.divider()
    orders_data = db.orders_get_active()
    if not orders_data.empty:
        status_flow = ["Placed", "Printing", "Packing", "Delivering"]
        for _, row in orders_data.iterrows():
            status = row['status']
            status_colors = {"Placed": "#888", "Printing": "#2196F3", "Packing": "#FF9800", "Delivering": "#9C27B0"}

            st.markdown(f"""
                <div class="glass-card">
                    <div style="display: flex; justify-content: space-between; align-items: start;">
                        <div>
                            <h4 style="margin:0; color:#2ECC40;">{row['customer_name']}</h4>
                            <p style="margin:0; font-size:0.9rem; opacity:0.8;">{row['product']}</p>
                        </div>
                        <span style="background:{status_colors.get(status, '#555')}; padding:4px 12px; border-radius:20px; font-size:0.7rem; font-weight:bold;">{status.upper()}</span>
                    </div>
                    <div style="margin-top:10px; font-size:0.85rem; color:#888;">
                        📅 Due: {row['deadline']} | 📞 {row['contact']} | 📍 {row['location']}
                    </div>
                </div>
            """, unsafe_allow_html=True)

            cols = st.columns([5, 1, 1])
            with cols[1]:
                    # Logic to move to next status or fulfill
                    if status in status_flow:
                        current_idx = status_flow.index(status)
                        if current_idx < len(status_flow) - 1:
                            next_status = status_flow[current_idx + 1]
                            if st.button(f"Next: {next_status}", key=f"nxt_{row['id']}", width="stretch"):
                                db.orders_update_status(row['id'], next_status)
                                st.rerun()
                        else:
                            if st.button("Fulfill", key=f"ful_{row['id']}", type="primary", width="stretch"):
                                fulfill_order_dialog(row['id'], row['product'], row['price'])
            with cols[2]:
                    if st.button("🗑️", key=f"can_{row['id']}", type="secondary", width="stretch"):
                        db.orders_delete_entry(row['id'])
                        st.rerun()
            st.write("<br>", unsafe_allow_html=True)
    else:
        st.info("No active orders found in the queue.")


with all_tabs[2]: # 🖨️ Cost Calculator
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

        m_col1.button("Eryone PLA (70 RON)", on_click=set_material, args=(70.0, "Eryone PLA"), width="stretch")
        m_col2.button("Prusa/Fillam. PLA (100 RON)", on_click=set_material, args=(100.0, "Prusament"), width="stretch")
        m_col3.button("Eryone/The Filam. PETG (60 RON)", on_click=set_material, args=(60.0, "Eryone/The Filament"), width="stretch")
        m_col4.button("Eryone TPU (100 RON)", on_click=set_material, args=(100.0, "Eryone TPU"), width="stretch")

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
        t_col1.button("Quick Print (0.5h/5m)", on_click=set_time_preset, args=(0.5, 5), width="stretch")
        t_col2.button("Standard (2h/10m)", on_click=set_time_preset, args=(2.0, 10), width="stretch")
        t_col3.button("Long/Overnight (12h/20m)", on_click=set_time_preset, args=(12.0, 20), width="stretch")

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
            e_c1.button("Env./Small (2 RON)", on_click=set_extra_presets, kwargs={'pack': 2.0}, width="stretch")
            e_c2.button("Box/Large (7 RON)", on_click=set_extra_presets, kwargs={'pack': 7.0}, width="stretch")

        with ex_col2:
            st.write("Profit Margin:")
            m_c1, m_c2 = st.columns(2)
            m_c1.button("Standard (60%)", on_click=set_extra_presets, kwargs={'margin': 60}, width="stretch")
            m_c2.button("High/Gift (150%)", on_click=set_extra_presets, kwargs={'margin': 150}, width="stretch")

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
    if st.button("🚀 Push to Ledger", width="stretch", type="primary"):
        push_to_ledger_dialog(f_weight, p_time, suggested_price)

with all_tabs[3]: # Quick Entry
    in_cats, out_cats = ["Product Sale", "Custom Print", "Donation", "Subscription", "Other"], ["Filament", "Product Part", "Transport", "Software", "Marketing", "Rent", "Cash Out", "Salary", "Misc"]
    c1, c2 = st.columns(2); t_type = c1.radio("Direction", ["Inbound", "Outbound"], horizontal=True); t_date = c2.date_input("Date", datetime.now())
    c3, c4, c5 = st.columns(3); cat = c3.selectbox("Category", options=in_cats if t_type=="Inbound" else out_cats); desc = c4.text_input("Description"); amt = c5.number_input("Amount (RON)", min_value=0.0)
    if st.button("Confirm & Save", type="primary", width='stretch'):
        if desc and amt > 0:
            db.ledger_add_entry(t_date.strftime("%Y-%m-%d"), t_type, cat, desc, amt)
            st.toast("Saved!", icon="🚀"); time.sleep(1); st.rerun()

with all_tabs[4]: # Transactions
    st.markdown("### 📑 Transaction Ledger")
    df = db.ledger_get_data()

    if not df.empty:
        # 1. Explicit Filtering Interface
        with st.container(border=True):
            f1, f2 = st.columns([2, 1])
            search_desc = f1.text_input("🔍 Search Description", placeholder="Filter by transaction details...")
            filter_type = f2.selectbox("Type", ["All", "Inbound", "Outbound"])

            f3, f4 = st.columns([2, 1])
            unique_cats = sorted(df['category'].unique().tolist())
            filter_cats = f3.multiselect("Categories", options=unique_cats)

            min_d, max_d = df['date'].min().date(), df['date'].max().date()
            date_range = f4.date_input("Date Range", value=(min_d, max_d))

        filtered_df = df.copy()

        if search_desc:
            filtered_df = filtered_df[filtered_df['description'].str.contains(search_desc, case=False, na=False)]
        if filter_type != "All":
            filtered_df = filtered_df[filtered_df['type'] == filter_type]
        if filter_cats:
            filtered_df = filtered_df[filtered_df['category'].isin(filter_cats)]

        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            start_date, end_date = date_range
            filtered_df = filtered_df[(filtered_df['date'].dt.date >= start_date) & (filtered_df['date'].dt.date <= end_date)]

        def color_t(v):
            return "background-color: rgba(46,204,64,0.12); color: #2ECC40;" if v=="Inbound" else "background-color: rgba(224,27,36,0.12); color: #E01B24;"

        # 2. Render Styled Ledger
        st.dataframe(
            filtered_df.sort_values('date', ascending=False).style.map(color_t, subset=['type']),
            width="stretch",
            hide_index=True
        )

        # 3. Management Section (Glass Card)
        st.write("<br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("<h4 style='margin:0 0 1rem 0; color:#FFFFFF;'>🗑️ Entry Management</h4>", unsafe_allow_html=True)
            c_id, c_btn = st.columns([3, 1])
            id_in = c_id.number_input("Transaction ID to remove:", step=1, min_value=0, key="ledger_del_id")
            if c_btn.button("Purge Entry", type="secondary", width="stretch", key="ledger_del_btn"):
                confirm_delete_dialog(id_in)
    else:
        st.info("No transaction history available.")

# --- USER MANAGEMENT TAB (ADMIN ONLY) ---
if st.session_state.current_user == "admin":
    with all_tabs[5]:
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
            if st.button("➕ New User", type="primary", width="stretch"):
                st.session_state.show_add_user = True
                st.rerun()

        # --- 3. DIRECTORY LIST ---
        users_df = db.user_get_list()
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
                    if c_action.button("Edit", key=f"btn_{uname}", width="stretch"):
                        st.session_state.active_manage_user = uname
                        st.rerun()

                    st.markdown('<hr style="margin:0.2rem 0; opacity:0.05">', unsafe_allow_html=True)

    # --- DATABASE BACKUP (ONLY VISIBLE IN DEBUG/LOCAL) ---
    if config.DEBUG_MODE:
        with st.expander("💾 Local Database Management"):
            st.info("Direct DB access is disabled in Production (Supabase).")
            # ... keep your existing Download/Upload code here ...
    with st.expander("💾 Database Management (Backup/Restore)"):
        st.warning("Handling the database file directly can corrupt your ledger if interrupted.")

        col_dl, col_ul = st.columns(2)

        with col_dl:
            st.markdown("#### Export Data")
            st.write("Download the current `biz_vault.db` file.")
            if os.path.exists(db.DB_FILE):
                with open(db.DB_FILE, "rb") as f:
                    st.download_button(
                        label="📥 Download Database",
                        data=f,
                        file_name=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
                        mime="application/octet-stream",
                        width="stretch"
                    )
            else:
                st.error("Database file not found.")

        with col_ul:
            st.markdown("#### Import Data")
            st.write("Replace the current database with a backup file.")
            uploaded_db = st.file_uploader("Upload .db file", type=["db"])

            if uploaded_db is not None:
                if st.button("🔥 Overwrite Current DB", type="secondary", width="stretch"):
                    # Save the uploaded file as the new DB_FILE
                    with open(db.DB_FILE, "wb") as f:
                        f.write(uploaded_db.getbuffer())
                    st.success("Database restored successfully!")
                    time.sleep(1)
                    st.rerun()