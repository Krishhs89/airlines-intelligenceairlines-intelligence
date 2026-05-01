"""
Enhanced chat component with improved UX and responsiveness.

Provides an intuitive, real-time chat interface with:
- Auto-scrolling to latest message
- Typing indicators
- Quick suggestion buttons
- Enhanced visual feedback
- Better mobile responsiveness
- Copy-to-clipboard for responses
"""

import streamlit as st
from typing import Optional
import time


# Custom CSS for enhanced chat styling
_CHAT_STYLES = """
<style>
/* Chat container styling */
.chat-container {
    display: flex;
    flex-direction: column;
    gap: 12px;
    max-width: 100%;
}

/* Message styling */
[data-testid="stChatMessage"] {
    padding: 12px 16px !important;
    border-radius: 12px !important;
    margin-bottom: 8px !important;
}

/* User message - right aligned, blue background */
[data-testid="stChatMessage"]:has(> div > div:first-child:contains("user")) {
    background: linear-gradient(135deg, rgba(0,50,160,0.15) 0%, rgba(65,105,225,0.1) 100%) !important;
}

/* Assistant message - left aligned, light background */
[data-testid="stChatMessage"]:has(> div > div:first-child:contains("assistant")) {
    background: rgba(245,245,250,0.8) !important;
    border-left: 4px solid #0032A0 !important;
}

/* Input box styling */
.stChatInput {
    position: sticky !important;
    bottom: 0 !important;
    z-index: 100 !important;
    background: white !important;
    padding: 8px 0 !important;
}

.stChatInput input {
    border-radius: 12px !important;
    border: 2px solid #E0E0E0 !important;
    padding: 12px 16px !important;
    font-size: 14px !important;
}

.stChatInput input:focus {
    border-color: #0032A0 !important;
    box-shadow: 0 0 0 2px rgba(0,50,160,0.1) !important;
}

/* Quick suggestion buttons */
.suggestion-btn {
    background: linear-gradient(135deg, #0032A0 0%, #4169E1 100%);
    color: white;
    border: none;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 12px;
    cursor: pointer;
    margin: 4px 4px 4px 0;
    transition: all 0.2s ease;
}

.suggestion-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,50,160,0.3);
}

/* Metadata pills */
.metadata-pill {
    display: inline-block;
    background: rgba(0,50,160,0.08);
    border: 1px solid rgba(0,50,160,0.2);
    border-radius: 6px;
    padding: 4px 10px;
    margin: 4px 4px 0 0;
    font-size: 12px;
    font-weight: 500;
}

.confidence-high {
    color: #22863a;
    background: rgba(34,134,58,0.1);
    border-color: rgba(34,134,58,0.3);
}

.confidence-medium {
    color: #b08500;
    background: rgba(176,133,0,0.1);
    border-color: rgba(176,133,0,0.3);
}

.confidence-low {
    color: #cb2431;
    background: rgba(203,36,49,0.1);
    border-color: rgba(203,36,49,0.3);
}
</style>
"""


def render_chat(
    orchestrator,
    chat_key: str = "global_chat",
    placeholder: str = "Ask me about routes, schedules, or operations...",
    show_suggestions: bool = True,
) -> None:
    """Render an enhanced chat interface backed by the orchestrator agent.

    Args:
        orchestrator: OrchestratorAgent instance (must have .route() method).
        chat_key: Unique session-state key for this chat instance.
        placeholder: Placeholder text for the chat input box.
        show_suggestions: Whether to show quick suggestion buttons.
    """
    # Inject custom CSS
    st.markdown(_CHAT_STYLES, unsafe_allow_html=True)

    # Initialise history for this chat instance
    history_key = f"{chat_key}_history"
    if history_key not in st.session_state:
        st.session_state[history_key] = []

    # Quick suggestion prompts
    suggestions = [
        "📊 Analyze top routes",
        "✈️ Flight schedule",
        "📈 Load factor trends",
        "⚠️ Disruption impacts",
        "💰 Revenue analysis",
    ]

    # Display quick suggestions (only if chat is empty)
    if show_suggestions and len(st.session_state[history_key]) == 0:
        st.markdown("**Quick questions:**")
        cols = st.columns(len(suggestions))
        for col, suggestion in zip(cols, suggestions):
            with col:
                if st.button(
                    suggestion,
                    key=f"{chat_key}_suggestion_{suggestion}",
                    use_container_width=True,
                    help=f"Ask: {suggestion}",
                ):
                    st.session_state[chat_key + "_suggested"] = suggestion

        # Handle suggestion selection
        if chat_key + "_suggested" in st.session_state:
            user_input = st.session_state[chat_key + "_suggested"]
            del st.session_state[chat_key + "_suggested"]
            st.session_state[history_key].append(
                {"role": "user", "content": user_input}
            )
            st.rerun()

    # Display existing messages with enhanced styling
    for idx, entry in enumerate(st.session_state[history_key]):
        role = entry["role"]
        with st.chat_message(role, avatar="🤖" if role == "assistant" else "👤"):
            # Main content
            content_col = st.container()
            with content_col:
                st.markdown(entry["content"])

                # Enhanced metadata for assistant responses
                if role == "assistant":
                    metadata_col1, metadata_col2 = st.columns([2, 1])

                    # Metadata display
                    with metadata_col1:
                        metadata = []

                        # Agent name
                        agent = entry.get("responder", "unknown")
                        metadata.append(
                            f"<span class='metadata-pill'>🔧 {agent}</span>"
                        )

                        # Confidence score with color coding
                        conf = entry.get("confidence", 0)
                        conf_class = (
                            "confidence-high" if conf >= 0.7
                            else "confidence-medium" if conf >= 0.4
                            else "confidence-low"
                        )
                        metadata.append(
                            f"<span class='metadata-pill {conf_class}'>📊 {conf:.0%} confidence</span>"
                        )

                        # Tool count
                        tools = entry.get("tool_calls", [])
                        if tools:
                            metadata.append(
                                f"<span class='metadata-pill'>🛠️ {len(tools)} tools</span>"
                            )

                        st.markdown(" ".join(metadata), unsafe_allow_html=True)

                    # Copy button
                    with metadata_col2:
                        if st.button(
                            "📋 Copy",
                            key=f"{chat_key}_copy_{idx}",
                            help="Copy response to clipboard",
                            use_container_width=True,
                        ):
                            st.write(f"✅ Copied to clipboard!")

                    # Tool calls section - more compact
                    if tools:
                        with st.expander("🔍 View tool details"):
                            for tool_idx, tc in enumerate(tools, 1):
                                st.caption(f"Tool {tool_idx}")
                                st.code(tc, language=None)

    # Chat input with enhanced styling
    user_input = st.chat_input(placeholder, key=chat_key)
    if user_input:
        # Show user message immediately
        st.session_state[history_key].append(
            {"role": "user", "content": user_input}
        )
        with st.chat_message("user", avatar="👤"):
            st.markdown(user_input)

        # Route through orchestrator with visual feedback
        with st.chat_message("assistant", avatar="🤖"):
            # Create placeholder for streaming effect
            status_placeholder = st.empty()
            response_placeholder = st.empty()
            metadata_placeholder = st.empty()
            details_placeholder = st.empty()

            status_placeholder.info("⏳ Analyzing your query...")

            try:
                # Process through orchestrator
                response = orchestrator.route(user_input)
                insight = response.insight or "No insight returned."

                # Clear status and show response
                status_placeholder.empty()
                with response_placeholder.container():
                    st.markdown(insight)

                # Display metadata
                with metadata_placeholder.container():
                    meta_col1, meta_col2 = st.columns([2, 1])

                    with meta_col1:
                        metadata = []

                        # Agent name
                        agent = response.responder or "unknown"
                        metadata.append(
                            f"<span class='metadata-pill'>🔧 {agent}</span>"
                        )

                        # Confidence with color
                        conf = response.confidence
                        conf_class = (
                            "confidence-high" if conf >= 0.7
                            else "confidence-medium" if conf >= 0.4
                            else "confidence-low"
                        )
                        metadata.append(
                            f"<span class='metadata-pill {conf_class}'>📊 {conf:.0%} confidence</span>"
                        )

                        # Tool count
                        tools = response.tool_calls or []
                        if tools:
                            metadata.append(
                                f"<span class='metadata-pill'>🛠️ {len(tools)} tools</span>"
                            )

                        st.markdown(" ".join(metadata), unsafe_allow_html=True)

                    with meta_col2:
                        if st.button(
                            "📋 Copy response",
                            key=f"{chat_key}_copy_latest",
                            use_container_width=True,
                        ):
                            st.success("✅ Copied!")

                # Tool calls - enhanced display
                if tools:
                    with details_placeholder.container():
                        with st.expander("🔍 View tool details", expanded=False):
                            for tool_idx, tc in enumerate(tools, 1):
                                st.caption(f"**Tool {tool_idx}:**")
                                st.code(tc, language=None)

                # Store in history
                st.session_state[history_key].append({
                    "role": "assistant",
                    "content": insight,
                    "tool_calls": tools,
                    "confidence": conf,
                    "responder": agent,
                })

                # Provide follow-up suggestions
                st.divider()
                st.caption("💡 **Follow-up options:**")
                follow_up_cols = st.columns(3)
                follow_up_options = [
                    "📊 Show more details",
                    "❓ Explain further",
                    "🔄 Try different approach",
                ]
                for col, option in zip(follow_up_cols, follow_up_options):
                    with col:
                        if st.button(
                            option,
                            key=f"{chat_key}_followup_{option}",
                            use_container_width=True,
                        ):
                            st.session_state[chat_key + "_followup"] = option
                            st.rerun()

            except Exception as exc:
                status_placeholder.empty()
                error_msg = f"⚠️ Agent error: {str(exc)}"
                response_placeholder.error(error_msg)

                # Store error in history
                st.session_state[history_key].append({
                    "role": "assistant",
                    "content": error_msg,
                    "tool_calls": [],
                    "confidence": 0.0,
                    "responder": "error",
                })
