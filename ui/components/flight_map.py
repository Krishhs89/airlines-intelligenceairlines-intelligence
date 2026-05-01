"""
Network map component using Plotly Scattergeo.

Renders US hub airports and connecting routes coloured by demand score.
"""

from typing import Optional

import pandas as pd
import plotly.graph_objects as go

from config import AIRPORT_COORDS, HUBS


def render_network_map(
    routes_df: pd.DataFrame,
    flights_df: pd.DataFrame,
) -> go.Figure:
    """Build a US-centred Scattergeo figure showing the airline network.

    Args:
        routes_df: DataFrame with columns origin, destination, demand_score.
        flights_df: DataFrame with origin column used to size hub markers.

    Returns:
        A plotly Figure ready to display with st.plotly_chart.
    """
    fig = go.Figure()

    # ------------------------------------------------------------------ #
    # Route lines coloured by demand_score
    # ------------------------------------------------------------------ #
    for _, row in routes_df.iterrows():
        origin = row["origin"]
        dest = row["destination"]
        demand = row.get("demand_score", 0.5)

        if origin not in AIRPORT_COORDS or dest not in AIRPORT_COORDS:
            continue

        o_lat, o_lon = AIRPORT_COORDS[origin]
        d_lat, d_lon = AIRPORT_COORDS[dest]

        # Colour gradient: high demand = red, medium = gold, low = green
        if demand >= 0.7:
            color = "rgba(220, 50, 50, 0.6)"
        elif demand >= 0.4:
            color = "rgba(230, 180, 30, 0.5)"
        else:
            color = "rgba(50, 180, 80, 0.4)"

        fig.add_trace(
            go.Scattergeo(
                lon=[o_lon, d_lon],
                lat=[o_lat, d_lat],
                mode="lines",
                line=dict(width=max(1, demand * 3), color=color),
                hoverinfo="text",
                text=f"{origin}-{dest}  demand: {demand:.2f}",
                showlegend=False,
            )
        )

    # ------------------------------------------------------------------ #
    # Hub airport markers sized by flight count
    # ------------------------------------------------------------------ #
    flight_counts = flights_df["origin"].value_counts().to_dict()

    hub_lats, hub_lons, hub_texts, hub_sizes = [], [], [], []
    for code in AIRPORT_COORDS:
        lat, lon = AIRPORT_COORDS[code]
        count = flight_counts.get(code, 0)
        hub_lats.append(lat)
        hub_lons.append(lon)
        hub_texts.append(f"{code}: {count} flights")
        hub_sizes.append(max(6, min(count * 0.6, 30)))

    is_hub = [code in HUBS for code in AIRPORT_COORDS]
    hub_colors = [
        "#0032A0" if h else "#5a7fba" for h in is_hub
    ]

    fig.add_trace(
        go.Scattergeo(
            lon=hub_lons,
            lat=hub_lats,
            mode="markers+text",
            marker=dict(
                size=hub_sizes,
                color=hub_colors,
                line=dict(width=1, color="white"),
                opacity=0.9,
            ),
            text=list(AIRPORT_COORDS.keys()),
            textposition="top center",
            textfont=dict(size=9, color="white"),
            hovertext=hub_texts,
            hoverinfo="text",
            showlegend=False,
        )
    )

    # ------------------------------------------------------------------ #
    # Layout
    # ------------------------------------------------------------------ #
    fig.update_layout(
        geo=dict(
            scope="usa",
            projection_type="albers usa",
            showland=True,
            landcolor="rgb(30, 30, 40)",
            showlakes=True,
            lakecolor="rgb(20, 20, 30)",
            bgcolor="rgba(0,0,0,0)",
            coastlinecolor="rgb(60,60,70)",
            countrycolor="rgb(60,60,70)",
            subunitcolor="rgb(50,50,60)",
            showsubunits=True,
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=0, b=0),
        height=450,
    )

    return fig
