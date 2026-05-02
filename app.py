"""
UA Network Intelligence -- Streamlit application entry point.

Run with:  streamlit run app.py
"""

import sys
import os
import logging

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

# ------------------------------------------------------------------ #
# Page config (must be the first Streamlit command)
# ------------------------------------------------------------------ #
st.set_page_config(
    layout="wide",
    page_title="UA Network Intelligence",
    page_icon="✈️",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------------ #
# Custom CSS
# ------------------------------------------------------------------ #
st.markdown(
    """
    <style>
    /* ---- UA blue accent ---- */
    :root {
        --ua-blue: #0032A0;
        --ua-blue-light: #4169E1;
    }

    /* Primary button colour */
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="stBaseButton-primary"] {
        background-color: #0032A0 !important;
        border-color: #0032A0 !important;
        color: white !important;
    }
    .stButton > button[kind="primary"]:hover,
    .stButton > button[data-testid="stBaseButton-primary"]:hover {
        background-color: #001F6D !important;
        border-color: #001F6D !important;
    }

    /* Metric cards */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, rgba(0,50,160,0.12) 0%, rgba(65,105,225,0.08) 100%);
        border: 1px solid rgba(0,50,160,0.2);
        border-radius: 10px;
        padding: 12px 16px;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.85em !important;
    }

    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        border-right: 2px solid rgba(0,50,160,0.3);
    }

    /* Headers */
    h1, h2, h3 {
        color: #0032A0 !important;
    }

    /* Chat message styling */
    [data-testid="stChatMessage"] {
        border-radius: 10px;
        margin-bottom: 4px;
    }

    /* Expander headers */
    .streamlit-expanderHeader {
        font-weight: 600 !important;
    }

    /* Divider */
    hr {
        border-color: rgba(0,50,160,0.15) !important;
    }

    /* Dataframe header */
    .stDataFrame thead th {
        background-color: rgba(0,50,160,0.15) !important;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------------ #
# Initialise orchestrator (once per session)
# ------------------------------------------------------------------ #
if "orchestrator" not in st.session_state:
    with st.spinner("Initialising agent system..."):
        try:
            from agents.orchestrator import OrchestratorAgent

            orchestrator = OrchestratorAgent.setup()
            st.session_state["orchestrator"] = orchestrator
            logging.info("Orchestrator initialised successfully.")
        except Exception as exc:
            st.error(f"Failed to initialise the agent system: {exc}")
            st.session_state["orchestrator"] = None
            logging.exception("Orchestrator init failed")

# ------------------------------------------------------------------ #
# Sidebar + page routing
# ------------------------------------------------------------------ #
from ui.sidebar import render_sidebar

selected_page = render_sidebar()

# ------------------------------------------------------------------ #
# Page dispatch
# ------------------------------------------------------------------ #
if selected_page == "Dashboard":
    from ui.pages.home import render_home
    render_home()

elif selected_page == "Network Planning":
    from ui.pages.network_planning import render_network_planning
    render_network_planning()

elif selected_page == "Disruption Simulator":
    from ui.pages.disruption_simulator import render_disruption_simulator
    render_disruption_simulator()

elif selected_page == "Analytics & Insights":
    from ui.pages.analytics import render_analytics
    render_analytics()

elif selected_page == "Chat":
    from ui.pages.chat import render_chat_page
    render_chat_page()

elif selected_page == "Agent Trace":
    from ui.pages.agent_trace import render_agent_trace
    render_agent_trace()

else:
    st.error(f"Unknown page: {selected_page}")
