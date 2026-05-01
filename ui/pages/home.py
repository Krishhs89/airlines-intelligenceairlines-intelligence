"""
Home / Dashboard page.

Shows KPI row, network map, recent disruptions, fleet composition,
and hub activity at a glance.
"""

import streamlit as st
import pandas as pd

from data.store import DataStore
from ui.components.metrics_cards import render_kpi_row
from ui.components.flight_map import render_network_map


def render_home() -> None:
    """Render the main dashboard page."""
    st.header("Operations Dashboard")

    data_store = DataStore.get()
    stats = data_store.get_summary_stats()

    # ---- KPI row ----
    render_kpi_row(stats)

    st.divider()

    # ---- Two-column layout: map + disruptions ----
    col_map, col_disruptions = st.columns([3, 2])

    with col_map:
        st.subheader("Network Map")
        try:
            fig = render_network_map(data_store.routes, data_store.flights)
            st.plotly_chart(fig, use_container_width=True)
        except Exception as exc:
            st.error(f"Map rendering error: {exc}")

    with col_disruptions:
        st.subheader("Recent Disruptions")
        disr = data_store.disruptions
        if disr.empty:
            st.info("No active disruptions.")
        else:
            display_cols = [
                "disruption_id", "disruption_type", "severity",
                "affected_airports", "duration_hours",
            ]
            available = [c for c in display_cols if c in disr.columns]
            st.dataframe(
                disr[available].head(10),
                use_container_width=True,
                hide_index=True,
            )

    st.divider()

    # ---- Quick stats: fleet composition + hub activity ----
    col_fleet, col_hubs = st.columns(2)

    with col_fleet:
        st.subheader("Fleet Composition")
        fleet = stats.get("fleet_by_type", {})
        if fleet:
            import plotly.express as px
            df_fleet = pd.DataFrame(
                {"Aircraft Type": list(fleet.keys()),
                 "Count": list(fleet.values())}
            )
            fig_fleet = px.pie(
                df_fleet, names="Aircraft Type", values="Count",
                color_discrete_sequence=["#0032A0", "#4169E1", "#6495ED", "#87CEEB"],
                hole=0.4,
            )
            fig_fleet.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=10, r=10, t=10, b=10),
                height=280,
                legend=dict(font=dict(size=11)),
            )
            st.plotly_chart(fig_fleet, use_container_width=True)
        else:
            st.info("No fleet data available.")

    with col_hubs:
        st.subheader("Hub Activity")
        flights = data_store.flights
        hub_counts = flights["origin"].value_counts().head(8)
        if not hub_counts.empty:
            import plotly.express as px
            df_hubs = pd.DataFrame(
                {"Hub": hub_counts.index, "Departures": hub_counts.values}
            )
            fig_hubs = px.bar(
                df_hubs, x="Hub", y="Departures",
                color_discrete_sequence=["#0032A0"],
            )
            fig_hubs.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=10, r=10, t=10, b=30),
                height=280,
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.1)"),
            )
            st.plotly_chart(fig_hubs, use_container_width=True)
        else:
            st.info("No flight data available.")
