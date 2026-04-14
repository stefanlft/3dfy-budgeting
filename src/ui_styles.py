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
        [data-testid="stSidebar"] { display: none; }

        /* Typography & Headings */
        h1 { color: #2ECC40 !important; text-align: center; }
        h3 { color: #FFFFFF !important; font-weight: 600 !important; }

        /* Custom Card Component */
        .glass-card, div[data-testid="stVerticalBlockBorderWrapper"] > div {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1rem;
            transition: transform 0.2s ease;
        }
        .glass-card:hover { border-color: rgba(46, 204, 64, 0.3); }

        /* KPI Styles */
        .kpi-box { text-align: center; padding: 10px; }
        .kpi-label { font-size: 0.8rem; color: #888; text-transform: uppercase; letter-spacing: 1px; }
        .kpi-value { font-size: 1.8rem; font-weight: bold; color: #2ECC40; margin: 5px 0; }

        /* Buttons */
        button[kind="primary"] { background-color: #2ECC40 !important; color: #122023 !important; border: none; font-weight: bold; }
        button[kind="secondary"] { border: 1px solid rgba(224, 27, 36, 0.5) !important; color: #E01B24 !important; background-color: transparent; }
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
        /* Relocate Plotly Modebar (Download/Zoom) to Bottom Right */
        .js-plotly-plot .modebar-container {
            top: auto !important;
            bottom: 0px !important;
            right: 10px !important;
        }
        @media (max-width: 640px) {
            .block-container { padding-left: 0.7rem !important; padding-right: 0.7rem !important; }
            .stTabs [data-baseweb="tab-list"] {
                justify-content: flex-start !important;
                overflow-x: auto !important;
                gap: 4px !important;
            }
            .stTabs [data-baseweb="tab"] { font-size: 0.75rem; flex-shrink: 0; padding: 10px 12px; }
        }
    </style>
    """
    st.markdown(brand_css, unsafe_allow_html=True)