"""
Analytics & Insights page.

Executive summaries, OTD by hub, load-factor heatmap, anomaly detection,
and route comparison.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from config import HUBS
from data.store import DataStore
from ui.components.agent_chat import render_chat


def render_analytics() -> None:
    """Render the Analytics & Insights page."""
    st.header("Analytics & Insights")

    orchestrator = st.session_state.get("orchestrator")
    data_store = DataStore.get()

    if orchestrator is None:
        st.error("Orchestrator not initialised. Please restart the app.")
        return

    # ================================================================== #
    # Executive Summary
    # ================================================================== #
    st.subheader("Executive Summary")
    if st.button("Generate Executive Summary", type="primary", key="an_exec"):
        with st.spinner("Generating executive summary..."):
            try:
                response = orchestrator.route("generate executive summary report")
                st.session_state["an_exec_response"] = response
            except Exception as exc:
                st.error(f"Summary generation failed: {exc}")

    exec_resp = st.session_state.get("an_exec_response")
    if exec_resp is not None:
        st.markdown(exec_resp.insight)
        if exec_resp.tool_calls:
            with st.expander("Tool calls"):
                for tc in exec_resp.tool_calls:
                    st.code(tc, language=None)

    st.divider()

    # ================================================================== #
    # Charts: OTD by hub  |  Load factor heatmap
    # ================================================================== #
    col_otd, col_lf = st.columns(2)

    flights = data_store.flights

    with col_otd:
        st.subheader("On-Time % by Hub")
        if not flights.empty:
            otd_data = []
            for hub in HUBS:
                hub_flights = flights[flights["origin"] == hub]
                total = len(hub_flights)
                if total == 0:
                    continue
                on_time = (hub_flights["status"] == "On Time").sum()
                otd_data.append({
                    "Hub": hub,
                    "On-Time %": round(on_time / total * 100, 1),
                    "Total Flights": total,
                })
            if otd_data:
                df_otd = pd.DataFrame(otd_data)
                fig_otd = px.bar(
                    df_otd, x="Hub", y="On-Time %",
                    color="On-Time %",
                    color_continuous_scale=["#dc3232", "#e6b41e", "#32b450"],
                    hover_data=["Total Flights"],
                )
                fig_otd.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=10, r=10, t=10, b=30),
                    height=350,
                    xaxis=dict(showgrid=False),
                    yaxis=dict(
                        showgrid=True, gridcolor="rgba(255,255,255,0.1)",
                        range=[0, 100],
                    ),
                    coloraxis_showscale=False,
                )
                st.plotly_chart(fig_otd, use_container_width=True)
            else:
                st.info("No hub flight data available.")
        else:
            st.info("No flight data available.")

    with col_lf:
        st.subheader("Load Factor by Route")
        routes = data_store.routes
        if not flights.empty and not routes.empty:
            # Build a pivot: origin x destination -> avg load factor
            lf_pivot = flights.groupby(["origin", "destination"])[
                "load_factor"
            ].mean().reset_index()
            # Limit to hubs for a readable heatmap
            lf_pivot = lf_pivot[
                lf_pivot["origin"].isin(HUBS) & lf_pivot["destination"].isin(HUBS)
            ]
            if not lf_pivot.empty:
                pivot_table = lf_pivot.pivot(
                    index="origin", columns="destination", values="load_factor"
                ).fillna(0)
                fig_hm = px.imshow(
                    pivot_table.values,
                    x=pivot_table.columns.tolist(),
                    y=pivot_table.index.tolist(),
                    color_continuous_scale=["#1a1a2e", "#0032A0", "#4169E1", "#ffd700"],
                    labels=dict(color="Load Factor"),
                    aspect="auto",
                )
                fig_hm.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=10, r=10, t=10, b=30),
                    height=350,
                )
                st.plotly_chart(fig_hm, use_container_width=True)
            else:
                st.info("Insufficient hub-to-hub data for heatmap.")
        else:
            st.info("No data available.")

    st.divider()

    # ================================================================== #
    # Anomalies
    # ================================================================== #
    st.subheader("Anomaly Detection")
    if st.button("Detect Anomalies", key="an_anomaly"):
        with st.spinner("Scanning for anomalies..."):
            try:
                response = orchestrator.route(
                    "detect anomalies in flight performance and load factors"
                )
                st.session_state["an_anomaly_response"] = response
            except Exception as exc:
                st.error(f"Anomaly detection failed: {exc}")

    anom_resp = st.session_state.get("an_anomaly_response")
    if anom_resp is not None:
        st.markdown(anom_resp.insight)
        anomalies = anom_resp.result.get("anomalies", [])
        if anomalies:
            st.dataframe(
                pd.DataFrame(anomalies).head(15),
                use_container_width=True,
                hide_index=True,
            )

    st.divider()

    # ================================================================== #
    # Route Comparison
    # ================================================================== #
    st.subheader("Route Comparison")
    rc1, rc2, rc3 = st.columns([2, 2, 1])
    with rc1:
        route_a_orig = st.selectbox("Route A Origin", HUBS, index=0, key="rc_a_orig")
        route_a_dest = st.selectbox(
            "Route A Dest",
            [h for h in HUBS if h != route_a_orig],
            index=0,
            key="rc_a_dest",
        )
    with rc2:
        route_b_orig = st.selectbox("Route B Origin", HUBS, index=1, key="rc_b_orig")
        route_b_dest = st.selectbox(
            "Route B Dest",
            [h for h in HUBS if h != route_b_orig],
            index=0,
            key="rc_b_dest",
        )
    with rc3:
        st.markdown("")  # spacer
        st.markdown("")
        if st.button("Compare", type="primary", key="rc_compare"):
            query = (
                f"compare route {route_a_orig}-{route_a_dest} "
                f"vs {route_b_orig}-{route_b_dest}"
            )
            with st.spinner("Comparing routes..."):
                try:
                    response = orchestrator.route(query)
                    st.session_state["rc_response"] = response
                except Exception as exc:
                    st.error(f"Comparison failed: {exc}")

    rc_resp = st.session_state.get("rc_response")
    if rc_resp is not None:
        st.markdown(rc_resp.insight)
        if rc_resp.tool_calls:
            with st.expander("Tool calls"):
                for tc in rc_resp.tool_calls:
                    st.code(tc, language=None)

    # ---- Bottom: Chat ----
    st.divider()
    st.subheader("Analytics Assistant")
    render_chat(
        orchestrator,
        chat_key="analytics_chat",
        placeholder="Ask about trends, KPIs, performance comparisons...",
    )
