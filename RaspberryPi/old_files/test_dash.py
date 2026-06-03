import json
import threading
from collections import deque

import paho.mqtt.client as mqtt
import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import plotly.graph_objs as go
import dash_leaflet as dl

import db

state = {
    "rpm": 0, "speed": 0, "lat": 48.137154, "lng": 11.576124,
    "sats": 0, "roll": 0, "pitch": 0, "temp": 0, "ts": 0,
    "max_lean_left": 0.0,
    "max_lean_right": 0.0,
}

hist = {k: deque(maxlen=150) for k in ["roll", "pitch", "temp", "speed", "rpm"]}


def on_connect(client, userdata, flags, reason_code, properties):
    print(f"[MQTT] verbunden (Code {reason_code})")
    client.subscribe("motosense/data")


def on_message(client, userdata, msg):
    try:
        d = json.loads(msg.payload.decode())
        state.update(d)
        roll = d.get("roll")
        if roll is not None:
            if roll > state["max_lean_left"]:
                state["max_lean_left"] = round(roll, 1)
            if roll < -state["max_lean_right"]:
                state["max_lean_right"] = round(-roll, 1)
        for k in hist:
            if d.get(k) is not None:
                hist[k].append(d[k])
        db.recorder.sample(state)
    except Exception as e:
        print("Parse-Fehler:", e)


def mqtt_thread():
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    c.on_connect = on_connect
    c.on_message = on_message
    try:
        c.connect("localhost", 1883, 60)
    except Exception as e:
        print(f"[MQTT] Verbindung fehlgeschlagen: {e}")
        return
    c.loop_forever()


threading.Thread(target=mqtt_thread, daemon=True).start()

COL = {
    "bg":       "#000000",
    "card":     "rgba(28,28,30,0.72)",
    "card_brd": "rgba(255,255,255,0.08)",
    "text":     "#f5f5f7",
    "text_dim": "#8e8e93",
    "blue":     "#0a84ff",
    "green":    "#30d158",
    "orange":   "#ff9f0a",
    "red":      "#ff453a",
    "teal":     "#64d2ff",
    "yellow":   "#ffd60a",
}
FONT = ('-apple-system, BlinkMacSystemFont, "SF Pro Display", '
        '"Helvetica Neue", Helvetica, Arial, sans-serif')

INDEX_STRING = """
<!DOCTYPE html>
<html>
  <head>
    {%metas%}
    <title>MotoSense</title>
    {%favicon%}
    {%css%}
    <meta name="viewport" content="width=device-width, initial-scale=1,
          maximum-scale=1, user-scalable=no, viewport-fit=cover">
    <style>
      html, body {
        margin: 0; padding: 0;
        background: #000;
        color: #f5f5f7;
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display",
                     "Helvetica Neue", Helvetica, Arial, sans-serif;
        -webkit-font-smoothing: antialiased;
        overscroll-behavior: none;
      }
      .modebar { display: none !important; }
      ::-webkit-scrollbar { width: 0; background: transparent; }
      .leaflet-container { background: #1c1c1e !important; border-radius: 22px; }
      .leaflet-tile { filter: brightness(0.85) contrast(1.05); }
    </style>
  </head>
  <body>
    {%app_entry%}
    <footer>{%config%}{%scripts%}{%renderer%}</footer>
  </body>
</html>
"""


def card(children, style=None):
    base = {
        "background": COL["card"], "backdropFilter": "blur(20px)",
        "WebkitBackdropFilter": "blur(20px)",
        "border": f"1px solid {COL['card_brd']}",
        "borderRadius": "22px", "padding": "18px 20px", "boxSizing": "border-box",
    }
    if style:
        base.update(style)
    return html.Div(children, style=base)


def stat_tile(label, value_id, unit, accent):
    return card([
        html.Div(label, style={
            "color": COL["text_dim"], "fontSize": "13px", "fontWeight": 600,
            "textTransform": "uppercase", "letterSpacing": "0.5px"}),
        html.Div([
            html.Span("0", id=value_id, style={
                "fontSize": "40px", "fontWeight": 700,
                "letterSpacing": "-1px", "color": accent}),
            html.Span(f" {unit}", style={
                "fontSize": "16px", "color": COL["text_dim"], "fontWeight": 500}),
        ], style={"marginTop": "6px"}),
    ], style={"flex": "1 1 150px", "minWidth": "150px"})


def pill_button(label, btn_id, color, bg=None):
    return html.Button(label, id=btn_id, n_clicks=0, style={
        "flex": "1", "padding": "16px 8px", "borderRadius": "16px",
        "border": "none", "background": bg or "rgba(255,255,255,0.08)",
        "color": color, "fontSize": "15px", "fontWeight": 700,
        "fontFamily": FONT, "cursor": "pointer"})


def fmt_duration(s):
    s = int(s or 0)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


def home_layout():
    return html.Div([
        card([
            html.Div([
                html.Div(id="rec-status", children="Keine Fahrt aktiv", style={
                    "fontSize": "15px", "fontWeight": 600, "color": COL["text_dim"]}),
                html.Div(id="rec-timer", children="00:00", style={
                    "fontSize": "15px", "fontWeight": 700,
                    "fontVariantNumeric": "tabular-nums"}),
            ], style={"display": "flex", "justifyContent": "space-between",
                      "marginBottom": "12px"}),
            html.Div([
                pill_button("Beginnen", "btn-start", "#fff", "rgba(48,209,88,0.25)"),
                pill_button("Pause", "btn-pause", COL["yellow"]),
                pill_button("Beenden", "btn-stop", COL["red"]),
            ], style={"display": "flex", "gap": "10px"}),
        ], style={"marginBottom": "14px"}),

        card([
            html.Div("Geschwindigkeit", style={
                "color": COL["text_dim"], "fontSize": "14px", "fontWeight": 600,
                "textAlign": "center", "textTransform": "uppercase",
                "letterSpacing": "0.5px"}),
            html.Div([
                html.Span("0", id="hero-speed", style={
                    "fontSize": "92px", "fontWeight": 700,
                    "letterSpacing": "-3px", "lineHeight": "1"}),
                html.Span(" km/h", style={
                    "fontSize": "22px", "color": COL["text_dim"], "fontWeight": 500}),
            ], style={"textAlign": "center", "marginTop": "4px"}),
        ], style={"marginBottom": "14px",
                  "background": "linear-gradient(160deg, rgba(10,132,255,0.18),"
                                " rgba(28,28,30,0.72))"}),

        html.Div([
            stat_tile("Drehzahl", "tile-rpm", "1/min", COL["red"]),
            stat_tile("Temperatur", "tile-temp", "°C", COL["orange"]),
        ], style={"display": "flex", "gap": "14px", "marginBottom": "14px"}),

        card([
            html.Div("Schräglage", style={
                "color": COL["text_dim"], "fontSize": "13px", "fontWeight": 600,
                "textTransform": "uppercase", "letterSpacing": "0.5px",
                "marginBottom": "10px"}),
            html.Div([
                html.Span("0", id="tile-roll", style={
                    "fontSize": "56px", "fontWeight": 700,
                    "letterSpacing": "-1px", "color": COL["teal"]}),
                html.Span(" °", style={"fontSize": "20px", "color": COL["text_dim"]}),
            ], style={"textAlign": "center"}),
        ], style={"marginBottom": "14px"}),

        html.Div([
            card([
                html.Div("Max. Links", style={
                    "color": COL["text_dim"], "fontSize": "13px", "fontWeight": 600,
                    "textTransform": "uppercase", "letterSpacing": "0.5px"}),
                html.Div([
                    html.Span("0", id="tile-max-left", style={
                        "fontSize": "40px", "fontWeight": 700,
                        "color": COL["green"], "letterSpacing": "-1px"}),
                    html.Span(" °", style={"fontSize": "16px", "color": COL["text_dim"]}),
                ], style={"marginTop": "6px"}),
            ], style={"flex": "1"}),
            card([
                html.Div("Max. Rechts", style={
                    "color": COL["text_dim"], "fontSize": "13px", "fontWeight": 600,
                    "textTransform": "uppercase", "letterSpacing": "0.5px"}),
                html.Div([
                    html.Span("0", id="tile-max-right", style={
                        "fontSize": "40px", "fontWeight": 700,
                        "color": COL["green"], "letterSpacing": "-1px"}),
                    html.Span(" °", style={"fontSize": "16px", "color": COL["text_dim"]}),
                ], style={"marginTop": "6px"}),
            ], style={"flex": "1"}),
        ], style={"display": "flex", "gap": "14px", "marginBottom": "14px"}),

        html.Button("Max-Werte zurücksetzen", id="reset-max", n_clicks=0, style={
            "width": "100%", "padding": "14px", "borderRadius": "14px",
            "border": "none", "background": "rgba(255,255,255,0.08)",
            "color": COL["blue"], "fontSize": "16px", "fontWeight": 600,
            "fontFamily": FONT, "cursor": "pointer"}),
    ], style={"padding": "0 16px"})


def map_layout():
    return html.Div([
        html.Div(
            dl.Map(id="map", center=[48.137154, 11.576124], zoom=15,
                   style={"height": "100%", "width": "100%"},
                   children=[
                       dl.TileLayer(
                           url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"),
                       dl.Marker(id="marker", position=[48.137154, 11.576124]),
                   ]),
            style={"height": "calc(100vh - 200px)", "borderRadius": "22px",
                   "overflow": "hidden", "border": f"1px solid {COL['card_brd']}"}),
        card([
            html.Div([
                html.Div([
                    html.Div("Position", style={"color": COL["text_dim"],
                             "fontSize": "11px", "fontWeight": 600}),
                    html.Div("—", id="map-coords", style={
                        "fontSize": "15px", "fontWeight": 600,
                        "fontVariantNumeric": "tabular-nums"}),
                ]),
                html.Div([
                    html.Div("Satelliten", style={"color": COL["text_dim"],
                             "fontSize": "11px", "fontWeight": 600}),
                    html.Div("0", id="map-sats", style={
                        "fontSize": "15px", "fontWeight": 600, "color": COL["green"]}),
                ], style={"textAlign": "right"}),
            ], style={"display": "flex", "justifyContent": "space-between",
                      "alignItems": "center"}),
        ], style={"marginTop": "14px"}),
    ], style={"padding": "0 16px"})


def rides_layout():
    return html.Div([
        html.Div(id="rides-view", children=rides_list_view()),
    ], style={"padding": "0 16px"})


def rides_list_view():
    rides = db.list_rides()
    if not rides:
        return card([
            html.Div("Noch keine Fahrten aufgezeichnet", style={
                "color": COL["text_dim"], "textAlign": "center", "padding": "20px 0"}),
            html.Div("Starte eine Fahrt über den Home-Tab.", style={
                "color": COL["text_dim"], "fontSize": "13px", "textAlign": "center"}),
        ])
    items = []
    for r in rides:
        ongoing = r["ended_at"] is None
        items.append(html.Button([
            html.Div([
                html.Div(r["name"], style={"fontSize": "17px", "fontWeight": 700}),
                html.Div("● läuft" if ongoing else fmt_duration(r["duration_s"]),
                         style={"fontSize": "13px", "fontWeight": 600,
                                "color": COL["green"] if ongoing else COL["text_dim"]}),
            ], style={"display": "flex", "justifyContent": "space-between",
                      "marginBottom": "6px"}),
            html.Div([
                html.Span(f"{(r['distance_km'] or 0):.1f} km",
                          style={"marginRight": "14px"}),
                html.Span(f"{(r['max_speed'] or 0):.0f} km/h max",
                          style={"marginRight": "14px", "color": COL["blue"]}),
                html.Span(f"{(r['max_lean_l'] or 0):.0f}°/"
                          f"{(r['max_lean_r'] or 0):.0f}° Lean",
                          style={"color": COL["teal"]}),
            ], style={"fontSize": "13px", "color": COL["text_dim"], "fontWeight": 500}),
        ], id={"type": "ride-item", "index": r["id"]}, n_clicks=0, style={
            "width": "100%", "textAlign": "left",
            "background": COL["card"], "backdropFilter": "blur(20px)",
            "WebkitBackdropFilter": "blur(20px)",
            "border": f"1px solid {COL['card_brd']}", "borderRadius": "18px",
            "padding": "16px 18px", "marginBottom": "12px",
            "color": COL["text"], "fontFamily": FONT, "cursor": "pointer"}))
    return html.Div(items)


def ride_detail_view(ride_id):
    ride = db.get_ride(ride_id)
    pts = db.get_trackpoints(ride_id)
    if not ride:
        return rides_list_view()

    line = [[p["lat"], p["lng"]] for p in pts if p["lat"] and p["lng"]]
    center = line[len(line) // 2] if line else [48.137154, 11.576124]

    header = card([
        html.Div([
            html.Button("‹ Zurück", id={"type": "ride-back", "index": 0},
                        n_clicks=0, style={
                            "background": "none", "border": "none",
                            "color": COL["blue"], "fontSize": "16px",
                            "fontWeight": 600, "fontFamily": FONT,
                            "cursor": "pointer", "padding": "0"}),
            html.Button("Löschen", id={"type": "ride-delete", "index": ride_id},
                        n_clicks=0, style={
                            "background": "none", "border": "none",
                            "color": COL["red"], "fontSize": "15px",
                            "fontWeight": 600, "fontFamily": FONT,
                            "cursor": "pointer", "padding": "0"}),
        ], style={"display": "flex", "justifyContent": "space-between",
                  "marginBottom": "10px"}),
        html.Div(ride["name"], style={"fontSize": "22px", "fontWeight": 800,
                 "marginBottom": "8px"}),
        html.Div([
            html.Span(f"{(ride['distance_km'] or 0):.1f} km",
                      style={"marginRight": "8px"}),
            html.Span(f"{fmt_duration(ride['duration_s'])}",
                      style={"marginRight": "8px"}),
            html.Span(f"max {(ride['max_speed'] or 0):.0f} km/h"),
        ], style={"color": COL["text_dim"], "fontSize": "14px", "fontWeight": 500}),
    ], style={"marginBottom": "14px"})

    detail_map = html.Div(
        dl.Map(center=center, zoom=14,
               style={"height": "100%", "width": "100%"},
               children=[
                   dl.TileLayer(
                       url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"),
                   dl.Polyline(positions=line, color=COL["blue"], weight=4),
                   dl.Marker(id="detail-marker", position=center),
               ]),
        style={"height": "300px", "borderRadius": "22px", "overflow": "hidden",
               "border": f"1px solid {COL['card_brd']}", "marginBottom": "14px"})

    scrubber = card([
        html.Div("Punkt auswählen", style={
            "color": COL["text_dim"], "fontSize": "13px", "fontWeight": 600,
            "textTransform": "uppercase", "letterSpacing": "0.5px",
            "marginBottom": "10px"}),
        dcc.Slider(id="scrub", min=0, max=max(len(pts) - 1, 0), value=0,
                   step=1, marks=None,
                   tooltip={"placement": "bottom", "always_visible": False}),
        html.Div(id="scrub-readout",
                 style={"display": "flex", "justifyContent": "space-between",
                        "marginTop": "12px"}),
    ], style={"marginBottom": "14px"})

    graphs = card([
        dcc.Graph(id="g-speed", config={"displayModeBar": False}),
        dcc.Graph(id="g-rpm",   config={"displayModeBar": False}),
        dcc.Graph(id="g-lean",  config={"displayModeBar": False}),
    ])

    return html.Div([header, detail_map, scrubber, graphs,
                     dcc.Store(id="ride-points", data=pts)])


app = dash.Dash(__name__, suppress_callback_exceptions=True)
app.title = "MotoSense"
app.index_string = INDEX_STRING

TAB_DEF = [("Home", "🏠", "home"), ("Karte", "🗺️", "map"), ("Fahrten", "📊", "rides")]


def tab_button(label, icon, value, active):
    return html.Button([
        html.Div(icon, style={"fontSize": "20px", "lineHeight": "1"}),
        html.Div(label, style={"fontSize": "10px", "fontWeight": 600, "marginTop": "3px"}),
    ], id={"type": "tab-btn", "index": value}, n_clicks=0, style={
        "flex": "1", "background": "none", "border": "none",
        "color": COL["blue"] if active else COL["text_dim"],
        "fontFamily": FONT, "display": "flex", "flexDirection": "column",
        "alignItems": "center", "cursor": "pointer", "padding": "8px 0"})


app.layout = html.Div(style={
    "minHeight": "100vh", "background": COL["bg"], "color": COL["text"],
    "fontFamily": FONT, "paddingBottom": "90px"}, children=[

    html.Div([
        html.Div("MotoSense", style={
            "fontSize": "34px", "fontWeight": 800, "letterSpacing": "-1px"}),
        html.Div(id="live-badge", children="● LIVE", style={
            "fontSize": "12px", "fontWeight": 700, "color": COL["green"],
            "marginTop": "2px"}),
    ], style={"padding": "20px 20px 16px"}),

    html.Div(id="tab-content", children=home_layout()),

    html.Div(id="tab-bar", children=[
        tab_button(l, i, v, v == "home") for l, i, v in TAB_DEF
    ], style={
        "position": "fixed", "bottom": "0", "left": "0", "right": "0",
        "display": "flex", "background": "rgba(20,20,22,0.85)",
        "backdropFilter": "blur(24px)", "WebkitBackdropFilter": "blur(24px)",
        "borderTop": f"1px solid {COL['card_brd']}",
        "padding": "6px 0 calc(6px + env(safe-area-inset-bottom))"}),

    dcc.Store(id="active-tab", data="home"),
    dcc.Interval(id="tick",      interval=200,  n_intervals=0),
    dcc.Interval(id="slow-tick", interval=1000, n_intervals=0),
])


@app.callback(
    Output("active-tab", "data"),
    Input({"type": "tab-btn", "index": dash.ALL}, "n_clicks"),
    prevent_initial_call=True)
def switch_tab(_):
    trig = dash.callback_context.triggered_id
    if trig and isinstance(trig, dict):
        return trig["index"]
    return dash.no_update


@app.callback(
    [Output("tab-content", "children"),
     Output("tab-bar", "children")],
    Input("active-tab", "data"))
def render_tab(active):
    layouts = {"home": home_layout, "map": map_layout, "rides": rides_layout}
    content = layouts.get(active, home_layout)()
    bar = [tab_button(l, i, v, v == active) for l, i, v in TAB_DEF]
    return content, bar


@app.callback(
    Output("rec-status", "children"),
    [Input("btn-start", "n_clicks"),
     Input("btn-pause", "n_clicks"),
     Input("btn-stop",  "n_clicks")],