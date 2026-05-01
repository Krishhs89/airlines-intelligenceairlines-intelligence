"""
Reusable agent chat component.

Provides a chat interface that routes user queries through the orchestrator
and displays responses with tool-call details and confidence scores.
"""

import streamlit as st
from typing import Optional


def render_chat(
    orchestrator,
    chat_key: str = "global_chat",
    placeholder: str = "Ask the agent system a question...",
) -> None:
    """Render a chat interface backed by the orchestrator agent.

    Args:
        orchestrator: OrchestratorAgent instance (must have .route() method).
        chat_key: Unique session-state key for this chat instance. Allows
                  multiple independent chats on different pages.
        placeholder: Placeholder text for the chat input box.
    """
    # Initialise history for this chat instance
    history_key = f"{chat_key}_history"
    if history_key not in st.session_state:
        st.session_state[history_key] = []

    # Display existing messages
    for entry in st.session_state[history_key]:
        role = entry["role"]
        with st.chat_message(role):
            st.markdown(entry["content"])
            if role == "assistant" and entry.get("tool_calls"):
                with st.expander("Tool calls & details"):
                    cols = st.columns([2, 1])
                    with cols[0]:
                        st.markdown("**Tools invoked:**")
                        for tc in entry["tool_calls"]:
                            st.code(tc, language=None)
                    with cols[1]:
                        conf = entry.get("confidence", 0)
                        colour = (
                            "green" if conf >= 0.7
                            else "orange" if conf >= 0.4
                            else "red"
                        )
                        st.markdown(
                            f"**Confidence:** "
                            f"<span style='color:{colour};font-weight:700'>"
                            f"{conf:.0%}</span>",
                            unsafe_allow_html=True,
                        )
                        st.markdown(f"**Agent:** {entry.get('responder', 'unknown')}")

    # Chat input
    user_input = st.chat_input(placeholder, key=chat_key)
    if user_input:
        # Show user message immediately
        st.session_state[history_key].append(
            {"role": "user", "content": user_input}
        )
        with st.chat_message("user"):
            st.markdown(user_input)

        # Route through orchestrator
        with st.chat_message("assistant"):
            with st.spinner("Agents processing..."):
                try:
                    response = orchestrator.route(user_input)
                    insight = response.insight or "No insight returned."
                    st.markdown(insight)

                    # Tool calls expander
                    if response.tool_calls:
                        with st.expander("Tool calls & details"):
                            cols = st.columns([2, 1])
                            with cols[0]:
                                st.markdown("**Tools invoked:**")
                                for tc in response.tool_calls:
                                    st.code(tc, language=None)
                            with cols[1]:
                                conf = response.confidence
                                colour = (
                                    "green" if conf >= 0.7
                                    else "orange" if conf >= 0.4
                                    else "red"
                                )
                                st.markdown(
                                    f"**Confidence:** "
                                    f"<span style='color:{colour};font-weight:700'>"
                                    f"{conf:.0%}</span>",
                                    unsafe_allow_html=True,
                                )
                                st.markdown(f"**Agent:** {response.responder}")

                    # Store in history
                    st.session_state[history_key].append({
                        "role": "assistant",
                        "content": insight,
                        "tool_calls": response.tool_calls,
                        "confidence": response.confidence,
                        "responder": response.responder,
                    })

                except Exception as exc:
                    st.error(f"Agent error: {exc}")
                    st.session_state[history_key].append({
                        "role": "assistant",
                        "content": f"Error: {exc}",
                        "tool_calls": [],
                        "confidence": 0.0,
                        "responder": "error",
                    })
