"""
Network Planning page.

Provides route analysis, underperforming-route detection, schedule-conflict
review, and a freeform chat for network planning questions.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from config import HUBS
from data.store import DataStore
from ui.components.agent_chat import render_chat


def render_network_planning() -> None:
    """Render the Network Planning analysis page."""
    st.header("Network Planning")

    orchestrator = st.session_state.get("orchestrator")
    data_store = DataStore.get()

    if orchestrator is None:
        st.error("Orchestrator not initialised. Please restart the app.")
        return

    # ---- Two-column layout ----
    col_left, col_right = st.columns([3, 2])

    # ================================================================== #
    # LEFT: Route Analyser
    # ================================================================== #
    with col_left:
        st.subheader("Route Analyser")

        rc1, rc2 = st.columns(2)
        with rc1:
            origin = st.selectbox("Origin", HUBS, index=0, key="np_origin")
        with rc2:
            dest_options = [h for h in HUBS if h != origin]
            destination = st.selectbox(
                "Destination", dest_options, index=0, key="np_dest"
            )

        if st.button("Analyze Route", type="primary", key="np_analyze"):
            query = f"analyze route {origin} to {destination}"
            with st.spinner("Analyzing route..."):
                try:
                    response = orchestrator.route(query)
                    st.session_state["np_last_response"] = response
                except Exception as exc:
                    st.error(f"Analysis failed: {exc}")

        # Display results
        response = st.session_state.get("np_last_response")
        if response is not None:
            st.markdown(f"**Insight:** {response.insight}")

            result = response.result or {}
            m1, m2, m3 = st.columns(3)

            # Demand score gauge
            demand = result.get("demand_score", 0.65)
            with m1:
                fig_gauge = go.Figure(
                    go.Indicator(
                        mode="gauge+number",
                        value=demand * 100,
                        title={"text": "Demand Score"},
                        gauge=dict(
                            axis=dict(range=[0, 100]),
                            bar=dict(color="#0032A0"),
                            steps=[
                                dict(range=[0, 40], color="rgba(50,180,80,0.3)"),
                                dict(range=[40, 70], color="rgba(230,180,30,0.3)"),
                                dict(range=[70, 100], color="rgba(220,50,50,0.3)"),
                            ],
                        ),
                    )
                )
                fig_gauge.update_layout(
                    height=200,
                    margin=dict(l=20, r=20, t=40, b=10),
                    paper_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig_gauge, use_container_width=True)

            # Load factor chart
            with m2:
                load_factor = result.get("load_factor", 0.82)
                fig_lf = go.Figure(
                    go.Indicator(
                        mode="gauge+number",
                        value=load_factor * 100,
                        title={"text": "Load Factor %"},
                        gauge=dict(
                            axis=dict(range=[0, 100]),
                            bar=dict(color="#4169E1"),
                        ),
                    )
                )
                fig_lf.update_layout(
                    height=200,
                    margin=dict(l=20, r=20, t=40, b=10),
                    paper_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig_lf, use_container_width=True)

            # Frequency recommendation
            with m3:
                freq = result.get("recommended_frequency", "N/A")
                competition = result.get("competition_level", "N/A")
                st.metric("Rec. Weekly Freq", freq)
                st.metric("Competition", competition)

            # Tool calls
            if response.tool_calls:
                with st.expander("Tool calls"):
                    for tc in response.tool_calls:
                        st.code(tc, language=None)

    # ================================================================== #
    # RIGHT: Tables
    # ================================================================== #
    with col_right:
        st.subheader("Underperforming Routes")
        routes = data_store.routes
        if not routes.empty and "demand_score" in routes.columns:
            low_demand = routes[routes["demand_score"] < 0.4].sort_values(
                "demand_score"
            )
            if low_demand.empty:
                st.info("No underperforming routes detected.")
            else:
                st.dataframe(
                    low_demand[
                        ["route_id", "demand_score", "revenue_index",
                         "frequency_weekly", "competition_level"]
                    ].head(10),
                    use_container_width=True,
                    hide_index=True,
                )
        else:
            st.info("Route data unavailable.")

        st.subheader("Schedule Conflicts")
        flights = data_store.flights
        if not flights.empty:
            # Detect potential gate conflicts: same gate, overlapping times
            gate_flights = flights.dropna(subset=["gate_id"]).sort_values(
                ["gate_id", "departure"]
            )
            conflicts = []
            prev = None
            for _, row in gate_flights.iterrows():
                if prev is not None and row["gate_id"] == prev["gate_id"]:
                    if row["departure"] < prev["arrival"]:
                        conflicts.append({
                            "Gate": row["gate_id"],
                            "Flight A": prev["flight_number"],
                            "Flight B": row["flight_number"],
                            "Overlap (min)": int(
                                (prev["arrival"] - row["departure"]).total_seconds() / 60
                            ),
                        })
                prev = row
            if conflicts:
                st.dataframe(
                    pd.DataFrame(conflicts).head(10),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.success("No schedule conflicts detected.")
        else:
            st.info("Flight data unavailable.")

    # ---- Bottom: Chat ----
    st.divider()
    st.subheader("Network Planning Assistant")
    render_chat(
        orchestrator,
        chat_key="network_planning_chat",
        placeholder="Ask about routes, schedules, fleet assignments...",
    )
