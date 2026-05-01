"""
Disruption Simulator page.

Allows users to build custom disruption scenarios or select presets,
run them through the agent system, and visualise impact and mitigations.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from config import HUBS, SCENARIO_PRESETS, AIRPORT_COORDS
from data.store import DataStore
from ui.components.agent_chat import render_chat


_SEVERITY_OPTIONS = ["Low", "Medium", "High", "Critical"]
_DISRUPTION_TYPES = ["Weather", "Gate Closure", "Mechanical", "ATC"]


def render_disruption_simulator() -> None:
    """Render the Disruption Simulator page."""
    st.header("Disruption Simulator")

    orchestrator = st.session_state.get("orchestrator")
    data_store = DataStore.get()

    if orchestrator is None:
        st.error("Orchestrator not initialised. Please restart the app.")
        return

    # ---- Scenario Builder + Results ----
    col_builder, col_results = st.columns([2, 3])

    # ================================================================== #
    # LEFT: Scenario Builder
    # ================================================================== #
    with col_builder:
        st.subheader("Scenario Builder")

        disruption_type = st.selectbox(
            "Disruption Type", _DISRUPTION_TYPES, key="ds_type"
        )
        airport = st.selectbox(
            "Affected Airport", list(AIRPORT_COORDS.keys()), key="ds_airport"
        )
        severity = st.select_slider(
            "Severity", options=_SEVERITY_OPTIONS, value="Medium", key="ds_severity"
        )
        duration = st.slider(
            "Duration (hours)", min_value=1, max_value=24, value=4, key="ds_duration"
        )

        if st.button("Run Scenario", type="primary", key="ds_run"):
            query = (
                f"simulate {disruption_type} disruption at {airport} "
                f"with {severity} severity lasting {duration} hours"
            )
            with st.spinner("Running disruption scenario..."):
                try:
                    response = orchestrator.route(query)
                    st.session_state["ds_last_response"] = response
                except Exception as exc:
                    st.error(f"Scenario failed: {exc}")

        # Preset buttons
        st.divider()
        st.markdown("**Quick Presets**")
        preset_cols = st.columns(len(SCENARIO_PRESETS))
        for idx, (name, preset) in enumerate(SCENARIO_PRESETS.items()):
            with preset_cols[idx]:
                if st.button(name, key=f"preset_{idx}", use_container_width=True):
                    query = (
                        f"simulate {preset['disruption_type']} disruption at "
                        f"{', '.join(preset['affected_airports'])} with "
                        f"{preset['severity']} severity lasting "
                        f"{preset['duration_hours']} hours. {preset['description']}"
                    )
                    with st.spinner(f"Running {name}..."):
                        try:
                            response = orchestrator.route(query)
                            st.session_state["ds_last_response"] = response
                        except Exception as exc:
                            st.error(f"Preset failed: {exc}")

    # ================================================================== #
    # RIGHT: Results Panel
    # ================================================================== #
    with col_results:
        st.subheader("Impact Analysis")

        response = st.session_state.get("ds_last_response")
        if response is None:
            st.info("Run a scenario to see results here.")
        else:
            # Insight
            st.markdown(f"**Agent Insight:** {response.insight}")

            result = response.result or {}

            # Metrics row
            mr1, mr2, mr3 = st.columns(3)
            with mr1:
                st.metric(
                    "Affected Flights",
                    result.get("affected_flights_count",
                               len(result.get("affected_flights", []))),
                )
            with mr2:
                st.metric(
                    "Passenger Impact",
                    f"{result.get('estimated_pax_impact', 0):,}",
                )
            with mr3:
                st.metric(
                    "Severity",
                    result.get("severity", "N/A"),
                )

            # Affected flights table
            affected_ids = result.get("affected_flights", [])
            if affected_ids:
                flights = data_store.flights
                affected_df = flights[flights["flight_number"].isin(affected_ids)]
                if not affected_df.empty:
                    with st.expander("Affected Flights Table", expanded=True):
                        display = ["flight_number", "origin", "destination",
                                   "status", "delay_minutes"]
                        avail = [c for c in display if c in affected_df.columns]
                        st.dataframe(
                            affected_df[avail].head(20),
                            use_container_width=True,
                            hide_index=True,
                        )

            # Mitigation recommendations
            mitigations = result.get("mitigations", [])
            if mitigations:
                with st.expander("Mitigation Recommendations", expanded=True):
                    for i, m in enumerate(mitigations, 1):
                        st.markdown(f"{i}. {m}")

            # Cascade delay bar chart
            cascade = result.get("cascade_delays", {})
            if cascade:
                st.markdown("**Cascade Delay Propagation**")
                df_cascade = pd.DataFrame(
                    {"Hour": list(cascade.keys()),
                     "Delayed Flights": list(cascade.values())}
                )
                fig_cascade = px.bar(
                    df_cascade, x="Hour", y="Delayed Flights",
                    color_discrete_sequence=["#dc3232"],
                )
                fig_cascade.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=10, r=10, t=10, b=30),
                    height=250,
                    xaxis=dict(showgrid=False),
                    yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.1)"),
                )
                st.plotly_chart(fig_cascade, use_container_width=True)
            else:
                # Fallback: show disruption severity distribution from data
                disr = data_store.disruptions
                if not disr.empty and "severity" in disr.columns:
                    st.markdown("**Disruption Severity Distribution**")
                    sev_counts = disr["severity"].value_counts()
                    fig_sev = px.bar(
                        x=sev_counts.index, y=sev_counts.values,
                        labels={"x": "Severity", "y": "Count"},
                        color_discrete_sequence=["#0032A0"],
                    )
                    fig_sev.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        margin=dict(l=10, r=10, t=10, b=30),
                        height=250,
                    )
                    st.plotly_chart(fig_sev, use_container_width=True)

            # Tool calls
            if response.tool_calls:
                with st.expander("Tool calls"):
                    for tc in response.tool_calls:
                        st.code(tc, language=None)

    # ---- Bottom: Chat ----
    st.divider()
    st.subheader("Disruption Assistant")
    render_chat(
        orchestrator,
        chat_key="disruption_chat",
        placeholder="Ask about disruptions, recovery plans, passenger impact...",
    )
