"""
AI Chat Assistant Page - Streamlit UI for multi-agent chat interface.

Provides an intuitive chat interface for querying the airline network intelligence system.
Users can ask questions about routes, schedules, disruptions, and analytics.
"""

import streamlit as st
from ui.components.agent_chat import render_chat


def render_chat_page() -> None:
    """Render the AI Chat Assistant page."""
    st.title("🤖 AI Chat Assistant")
    st.markdown(
        """
        Ask me anything about your airline network, operations, and planning.
        I'll analyze your query and provide intelligent insights using our multi-agent system.
        """
    )

    # Get orchestrator from session state
    orchestrator = st.session_state.get("orchestrator")

    if orchestrator is None:
        st.error("⚠️ Agent system is not initialized. Please refresh the page.")
        return

    # Render the enhanced chat interface
    render_chat(
        orchestrator=orchestrator,
        chat_key="airline_chat",
        placeholder="Ask me about routes, schedules, disruptions, or analytics...",
        show_suggestions=True,
    )


if __name__ == "__main__":
    render_chat_page()
