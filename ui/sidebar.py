"""
Sidebar component for page navigation, agent status, and data controls.
"""

import streamlit as st

from config import USE_MOCK_LLM
from data.store import DataStore


_PAGES = [
    "Dashboard",
    "Chat",
    "Network Planning",
    "Disruption Simulator",
    "Analytics & Insights",
    "Agent Trace",
]

_AGENT_NAMES = [
    ("Orchestrator", "🎯"),
    ("Network Planning", "🗺️"),
    ("Disruption Analysis", "⚡"),
    ("Analytics & Insights", "📊"),
]


def render_sidebar() -> str:
    """Render the sidebar and return the selected page name.

    Returns:
        The name of the selected page (matches _PAGES list).
    """
    with st.sidebar:
        st.markdown(
            "<h2 style='text-align:center;color:#0032A0;'>✈️ UA Network Intelligence</h2>",
            unsafe_allow_html=True,
        )
        st.caption("Multi-Agent System for Airline Operations")

        st.divider()

        # ---- Navigation ----
        page = st.radio(
            "Navigation",
            _PAGES,
            index=0,
            key="nav_page",
            label_visibility="collapsed",
        )

        st.divider()

        # ---- Agent Status ----
        st.markdown("**Agent Status**")
        orchestrator = st.session_state.get("orchestrator")
        for name, icon in _AGENT_NAMES:
            status = "🟢" if orchestrator is not None else "🔴"
            st.markdown(
                f"<div style='display:flex;align-items:center;gap:6px;"
                f"font-size:0.9em;padding:1px 0;'>"
                f"{status} {icon} {name}</div>",
                unsafe_allow_html=True,
            )

        st.divider()

        # ---- MCP Context Summary ----
        st.markdown("**MCP Context**")
        if orchestrator is not None:
            ctx = orchestrator.context_store
            summary = ctx.get_session_summary()
            st.markdown(
                f"Messages: **{summary.get('total_messages', 0)}**"
            )
            st.markdown(
                f"Context keys: **{len(ctx.keys())}**"
            )
            agents = summary.get("unique_agents", [])
            if agents:
                st.markdown(f"Active agents: {', '.join(agents)}")
        else:
            st.markdown("_Not initialised_")

        st.divider()

        # ---- Data Controls ----
        st.markdown("**Data Controls**")
        if st.button("Reset Data", key="sb_reset", use_container_width=True):
            try:
                DataStore.get().reset()
                # Clear cached responses
                keys_to_clear = [
                    k for k in st.session_state
                    if k.endswith("_response") or k.endswith("_history")
                ]
                for k in keys_to_clear:
                    del st.session_state[k]
                st.success("Data reset successfully.")
                st.rerun()
            except Exception as exc:
                st.error(f"Reset failed: {exc}")

        # Quick stats
        try:
            stats = DataStore.get().get_summary_stats()
            st.caption(
                f"{stats['total_flights']} flights | "
                f"{stats['total_routes']} routes | "
                f"{stats['total_aircraft']} aircraft"
            )
        except Exception:
            st.caption("Data loading...")

        st.divider()

        # ---- Model Info ----
        st.markdown("**Model**")
        if USE_MOCK_LLM:
            st.markdown(
                "<span style='background:#FF9800;color:white;padding:2px 10px;"
                "border-radius:10px;font-size:0.82em;font-weight:600;'>"
                "Mock LLM</span>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<span style='background:#4CAF50;color:white;padding:2px 10px;"
                "border-radius:10px;font-size:0.82em;font-weight:600;'>"
                "AWS Bedrock</span>",
                unsafe_allow_html=True,
            )

        st.caption("v1.0 | Multi-Agent MCP Architecture")

    return page
