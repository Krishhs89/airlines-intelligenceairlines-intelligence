"""
Agent Trace / MCP Inspector page.

This is the KEY DEMO DIFFERENTIATOR -- shows full MCP message flow,
tool-call timelines, agent badges, and context-store internals.
"""

import streamlit as st
import json
from datetime import datetime

from mcp.tool_registry import MCPToolRegistry


# Agent colour palette for visual differentiation
_AGENT_COLORS = {
    "user": "#4CAF50",
    "orchestrator": "#0032A0",
    "network_planning": "#E65100",
    "disruption_analysis": "#C62828",
    "analytics_insights": "#6A1B9A",
    "error": "#757575",
}

_AGENT_ICONS = {
    "user": "👤",
    "orchestrator": "🎯",
    "network_planning": "🗺️",
    "disruption_analysis": "⚡",
    "analytics_insights": "📊",
}


def _badge(agent_name: str) -> str:
    """Return an HTML badge span for an agent name."""
    colour = _AGENT_COLORS.get(agent_name, "#555")
    icon = _AGENT_ICONS.get(agent_name, "🤖")
    return (
        f"<span style='"
        f"background-color:{colour};color:white;padding:2px 10px;"
        f"border-radius:12px;font-size:0.82em;font-weight:600;"
        f"display:inline-block;margin:2px 0;"
        f"'>{icon} {agent_name}</span>"
    )


def render_agent_trace() -> None:
    """Render the Agent Trace / MCP Inspector page."""
    st.header("Agent Trace & MCP Inspector")
    st.caption(
        "Full visibility into multi-agent communication, tool invocations, "
        "and shared context store."
    )

    orchestrator = st.session_state.get("orchestrator")
    if orchestrator is None:
        st.error("Orchestrator not initialised. Please restart the app.")
        return

    context_store = orchestrator.context_store
    tool_registry = orchestrator.tool_registry

    # ================================================================== #
    # Section 1: MCP Message Log
    # ================================================================== #
    st.subheader("MCP Message Log")
    history = context_store.get_conversation_history()

    if not history:
        st.info(
            "No messages yet. Interact with the agents on other pages to "
            "generate trace data."
        )
    else:
        # Reverse chronological
        for idx, entry in enumerate(reversed(history)):
            msg = entry.get("message", {})
            resp = entry.get("response")
            ts = entry.get("timestamp", "")

            sender = msg.get("sender", "unknown")
            recipient = msg.get("recipient", "unknown")
            intent = msg.get("intent", "")
            payload = msg.get("payload", {})
            trace = msg.get("trace", [])
            msg_id = msg.get("message_id", "")[:8]

            # Card header
            header_html = (
                f"<div style='display:flex;align-items:center;gap:8px;"
                f"flex-wrap:wrap;'>"
                f"{_badge(sender)} "
                f"<span style='color:#888;font-size:0.9em;'>→</span> "
                f"{_badge(recipient)} "
                f"<span style='color:#888;font-size:0.8em;margin-left:auto;'>"
                f"#{msg_id} | {ts[:19]}</span>"
                f"</div>"
            )

            with st.expander(
                f"Message {len(history) - idx}: {sender} -> {recipient} ({intent})",
                expanded=(idx == 0),
            ):
                st.markdown(header_html, unsafe_allow_html=True)
                st.markdown(f"**Intent:** `{intent}`")

                # Payload
                if payload:
                    st.markdown("**Payload:**")
                    st.json(payload)

                # Trace steps
                if trace:
                    st.markdown("**Trace path:**")
                    trace_html = " → ".join(
                        _badge(t) for t in trace
                    )
                    st.markdown(trace_html, unsafe_allow_html=True)

                # Response
                if resp:
                    st.divider()
                    responder = resp.get("responder", "unknown")
                    st.markdown(
                        f"**Response from** {_badge(responder)}",
                        unsafe_allow_html=True,
                    )
                    st.markdown(f"**Insight:** {resp.get('insight', '')[:500]}")

                    conf = resp.get("confidence", 0)
                    conf_colour = (
                        "#4CAF50" if conf >= 0.7
                        else "#FF9800" if conf >= 0.4
                        else "#F44336"
                    )
                    st.markdown(
                        f"**Confidence:** "
                        f"<span style='color:{conf_colour};font-weight:700;"
                        f"font-size:1.1em;'>{conf:.0%}</span>",
                        unsafe_allow_html=True,
                    )

                    tool_calls = resp.get("tool_calls", [])
                    if tool_calls:
                        st.markdown("**Tool calls:**")
                        for tc in tool_calls:
                            st.code(tc, language=None)

                    # Full result (collapsed)
                    result_data = resp.get("result", {})
                    if result_data:
                        with st.expander("Full result payload"):
                            st.json(result_data)

    st.divider()

    # ================================================================== #
    # Section 2: Tool Call Timeline
    # ================================================================== #
    st.subheader("Tool Call Timeline")

    if history:
        timeline_data = []
        for idx, entry in enumerate(history):
            resp = entry.get("response")
            if resp and resp.get("tool_calls"):
                for tc in resp["tool_calls"]:
                    timeline_data.append({
                        "Step": idx + 1,
                        "Tool": tc,
                        "Agent": resp.get("responder", "unknown"),
                        "Confidence": resp.get("confidence", 0),
                    })

        if timeline_data:
            import plotly.express as px
            import pandas as pd

            df_tl = pd.DataFrame(timeline_data)
            fig_tl = px.scatter(
                df_tl,
                x="Step",
                y="Tool",
                color="Agent",
                size="Confidence",
                size_max=18,
                color_discrete_map=_AGENT_COLORS,
                hover_data=["Confidence"],
            )
            fig_tl.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=10, r=10, t=10, b=30),
                height=max(200, len(set(df_tl["Tool"])) * 40 + 80),
                xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.1)"),
                yaxis=dict(showgrid=False),
            )
            st.plotly_chart(fig_tl, use_container_width=True)
        else:
            st.info("No tool calls recorded yet.")
    else:
        st.info("No messages in history.")

    st.divider()

    # ================================================================== #
    # Section 3: Registered Tools
    # ================================================================== #
    st.subheader("Registered Tools")
    tools = tool_registry.list_tools()
    if tools:
        import pandas as pd
        df_tools = pd.DataFrame(tools)
        # Colour-code by agent
        st.dataframe(
            df_tools,
            use_container_width=True,
            hide_index=True,
            column_config={
                "agent": st.column_config.TextColumn("Agent", width="medium"),
                "name": st.column_config.TextColumn("Tool Name", width="large"),
                "description": st.column_config.TextColumn("Description", width="large"),
            },
        )
    else:
        st.info("No tools registered.")

    st.divider()

    # ================================================================== #
    # Section 4: Context Store Dump
    # ================================================================== #
    st.subheader("Context Store")

    ctx_keys = context_store.keys()
    session_summary = context_store.get_session_summary()

    mc1, mc2, mc3 = st.columns(3)
    with mc1:
        st.metric("Total Messages", session_summary.get("total_messages", 0))
    with mc2:
        st.metric("Active Context Keys", len(ctx_keys))
    with mc3:
        st.metric(
            "Unique Agents",
            len(session_summary.get("unique_agents", [])),
        )

    # Intent distribution
    intent_dist = session_summary.get("intent_distribution", {})
    if intent_dist:
        st.markdown("**Intent Distribution:**")
        import pandas as pd
        df_int = pd.DataFrame(
            {"Intent": list(intent_dist.keys()),
             "Count": list(intent_dist.values())}
        )
        st.dataframe(df_int, use_container_width=True, hide_index=True)

    # All context keys/values
    if ctx_keys:
        with st.expander(f"All Context Keys ({len(ctx_keys)})", expanded=False):
            for key in ctx_keys:
                val = context_store.get(key)
                st.markdown(f"**`{key}`**")
                if isinstance(val, (dict, list)):
                    st.json(val)
                else:
                    st.code(str(val), language=None)
                st.markdown("---")
    else:
        st.info("Context store is empty.")
