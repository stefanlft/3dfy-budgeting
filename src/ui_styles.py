import streamlit as st

def init_page(debug_mode=False):
    st.set_page_config(
        page_title="3dfy Budget" + (" (DEBUG)" if debug_mode else ""),
        layout="wide",
        initial_sidebar_state="collapsed"
    )

def apply_custom_css():
    brand_css = """
    <style>
        [data-testid="stHeader"] { display: none !important; }
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .block-container { padding-top: 2rem !important; }
        .stApp { background-color: #122023 !important; color: #FFFFFF !important; }
        [data-testid="stSidebar"] {display: none;}
        h1 { color: #2ECC40 !important; text-align: center; }
        button[kind="primary"] { background-color: #2ECC40 !important; color: #122023 !important; border: none; font-weight: bold; }
        button[kind="secondary"] { border: 1px solid #E01B24 !important; color: #E01B24 !important; background-color: transparent; }
        input:focus { border-color: #2ECC40 !important; box-shadow: 0 0 10px rgba(46, 204, 64, 0.4) !important; }

        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            background-color: rgba(255, 255, 255, 0.03);
            padding: 10px 10px 0px 10px;
            border-radius: 10px 10px 0 0;
        }
        .stTabs [data-baseweb="tab"] {
            height: auto;
            padding: 12px 20px;
            color: #888888 !important;
            transition: all 0.3s ease;
            background-color: transparent !important;
            border-radius: 5px 5px 0 0;
        }
        .stTabs [aria-selected="true"] {
            background-color: rgba(46, 204, 64, 0.12) !important;
            color: #2ECC40 !important;
            font-weight: bold !important;
            border-bottom: 3px solid #2ECC40 !important;
            box-shadow: 0 4px 15px rgba(46, 204, 64, 0.4), 0 0 30px rgba(46, 204, 64, 0.2);
        }
        @media (max-width: 640px) {
            .stTabs [data-baseweb="tab-list"] { justify-content: center; }
            .stTabs [data-baseweb="tab"] { font-size: 0.8rem; flex-grow: 1; }
        }
    </style>
    """
    st.markdown(brand_css, unsafe_allow_html=True)