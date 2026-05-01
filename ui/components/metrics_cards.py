"""
KPI metrics cards component for the dashboard.

Renders a row of four key performance indicators using Streamlit metric widgets.
"""

import streamlit as st
from typing import Any, Dict


def render_kpi_row(stats: Dict[str, Any]) -> None:
    """Display a row of four KPI metric cards.

    Args:
        stats: Dictionary from DataStore.get_summary_stats() containing
               on_time_rate, average_load_factor, active_disruptions, etc.
    """
    c1, c2, c3, c4 = st.columns(4)

    on_time_pct = round(stats.get("on_time_rate", 0) * 100, 1)
    avg_load = round(stats.get("average_load_factor", 0) * 100, 1)
    active_disruptions = stats.get("active_disruptions", 0)
    total_flights = stats.get("total_flights", 0)

    # Determine delta hints based on thresholds
    with c1:
        st.metric(
            label="On-Time %",
            value=f"{on_time_pct}%",
            delta="Good" if on_time_pct >= 75 else "Below target",
            delta_color="normal" if on_time_pct >= 75 else "inverse",
        )

    with c2:
        st.metric(
            label="Fleet Utilization %",
            value=f"{avg_load}%",
            delta="Healthy" if avg_load >= 70 else "Low",
            delta_color="normal" if avg_load >= 70 else "inverse",
        )

    with c3:
        st.metric(
            label="Active Disruptions",
            value=active_disruptions,
            delta=f"{stats.get('cancelled_count', 0)} cancelled",
            delta_color="inverse" if stats.get("cancelled_count", 0) > 0 else "off",
        )

    with c4:
        st.metric(
            label="Avg Load Factor",
            value=f"{avg_load}%",
            delta=f"{total_flights} flights",
            delta_color="off",
        )
