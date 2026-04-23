"""
Vector Search Studio

Qdrant's built-in lab for tuning and evaluating vector search.
Compare models, hybrid configs, and index settings, then ship the best recipe with confidence.

Usage: python mission_control.py
Then open: http://localhost:8050
"""

import os
import json
import time
import random
from datetime import datetime
from pathlib import Path
from threading import Thread
from dotenv import load_dotenv
from datasets import load_dataset
from qdrant_client import QdrantClient, models
from qdrant_client.models import Distance, VectorParams, PointStruct
from fastembed import TextEmbedding

import dash
from dash import dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import pandas as pd

load_dotenv()

# Configuration
QDRANT_URL = os.getenv('QDRANT_CLOUD_URL')
QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')
RESULTS_FILE = Path("mission_results.json")

# Flight configurations (embedding models)
FLIGHT_CONFIGS = {
    "bge-small": {
        "model_name": "BAAI/bge-small-en-v1.5",
        "vector_size": 384,
        "description": "Fast & efficient"
    },
    "bge-base": {
        "model_name": "BAAI/bge-base-en-v1.5",
        "vector_size": 768,
        "description": "High quality"
    },
    "minilm-l6": {
        "model_name": "sentence-transformers/all-MiniLM-L6-v2",
        "vector_size": 384,
        "description": "Ultra fast"
    }
}

TOP_K_VALUES = [1, 3, 5, 10]

# Global state
experiment_running = False
current_status = ""

# [Include helper functions from previous version]
def load_results():
    if RESULTS_FILE.exists():
        with open(RESULTS_FILE, 'r') as f:
            return json.load(f)
    return []

def save_results(results):
    with open(RESULTS_FILE, 'w') as f:
        json.dump(results, f, indent=2)

# Initialize Dash app
app = dash.Dash(
    __name__, 
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
    assets_folder='assets'
)
app.title = "Vector Search Studio | Qdrant"

# =============================================================================
# ZONE 1: BRIDGE / HUD (Top)
# =============================================================================

bridge_hud = html.Div([
    # Header Bar
    dbc.Row([
        dbc.Col([
            html.Div([
                html.Div([
                    html.Div([
                        html.Span("Qdrant", style={'fontSize': '0.875rem', 'color': 'hsl(var(--muted-foreground))', 'marginRight': '8px', 'fontWeight': '500'}),
                        html.Span("/", style={'fontSize': '0.875rem', 'color': 'hsl(var(--muted-foreground))', 'marginRight': '8px'}),
                        html.Span("Vector Search Studio", style={'fontSize': '0.875rem', 'color': 'hsl(var(--muted-foreground))', 'fontWeight': '500'})
                    ], style={'marginBottom': '8px'}),
                    html.H1("Vector Search Studio", style={'margin': 0, 'fontSize': '2.25rem', 'fontWeight': '700', 'letterSpacing': '-0.025em', 'color': 'hsl(var(--foreground))'}),
                    html.P("Experiment with embedding models and Qdrant configurations to find the best setup for your app", 
                           style={'margin': 0, 'fontSize': '1rem', 'color': 'hsl(var(--muted-foreground))', 'marginTop': '8px', 'lineHeight': '1.5'})
                ])
            ], style={'paddingBottom': '24px'})
        ], md=7),
        dbc.Col([
            html.Div([
                dbc.Button("New Experiment", color="primary", className="btn-mission-primary", size="sm", style={'marginRight': '8px'}),
                dbc.Button("Save Recipe", color="secondary", className="btn-mission-secondary", size="sm", outline=True, style={'marginRight': '8px'}),
                dbc.Button("Export Report", color="secondary", className="btn-mission-secondary", size="sm", outline=True)
            ], style={'textAlign': 'right', 'display': 'flex', 'justifyContent': 'flex-end', 'gap': '8px'})
        ], md=5)
    ], className="mb-4"),
    
    # Scenario Chips
    html.Div([
        html.Div("Scenario", style={'fontSize': '0.875rem', 'color': 'hsl(var(--muted-foreground))', 
                                    'marginBottom': '8px', 'fontWeight': '500'}),
        html.Div([
            html.Div([
                html.Span("Dataset: CA_Housing_Statutes", className="scenario-chip"),
                html.Span("Query Set: Lawyer_QA_v3", className="scenario-chip"),
            ], style={'display': 'inline-block', 'marginRight': '16px'}),
            html.Div([
                html.Span("Task: Legal Retrieval", className="scenario-chip"),
                html.Span("Environment: local-qdrant", className="scenario-chip"),
            ], style={'display': 'inline-block'})
        ])
    ], className="mb-4"),
    
    # KPI Cards
    dbc.Row([
        dbc.Col([
            html.Div([
                html.Div("Best Recall@K", className="kpi-label mb-3"),
                html.Div(id='kpi-recall', children="—", className="kpi-value", style={'fontSize': '2.5rem', 'marginBottom': '12px'}),
                html.Div(id='kpi-recall-detail', children="Run an experiment to see winners here", className="kpi-sublabel")
            ], className="kpi-card kpi-recall", style={'padding': '24px !important'})
        ], md=3),
        dbc.Col([
            html.Div([
                html.Div("Fastest Run", className="kpi-label mb-3"),
                html.Div(id='kpi-speed', children="—", className="kpi-value", style={'fontSize': '2.5rem', 'marginBottom': '12px'}),
                html.Div(id='kpi-speed-detail', children="Run an experiment to see winners here", className="kpi-sublabel")
            ], className="kpi-card kpi-speed", style={'padding': '24px !important'})
        ], md=3),
        dbc.Col([
            html.Div([
                html.Div("Cost Efficiency", className="kpi-label mb-3"),
                html.Div(id='kpi-cost', children="—", className="kpi-value", style={'fontSize': '2.5rem', 'marginBottom': '12px'}),
                html.Div(id='kpi-cost-detail', children="Run an experiment to see winners here", className="kpi-sublabel")
            ], className="kpi-card kpi-cost", style={'padding': '24px !important'})
        ], md=3),
        dbc.Col([
            html.Div([
                html.Div("Active Recipe", className="kpi-label mb-3"),
                html.Div(id='kpi-config', children="—", className="kpi-value", style={'fontSize': '1.75rem', 'marginBottom': '12px'}),
                html.Div(id='kpi-config-detail', children="None active", className="kpi-sublabel")
            ], className="kpi-card kpi-config", style={'padding': '24px !important'})
        ], md=3)
    ], className="mb-5")
], style={'padding': '30px 0'})

# =============================================================================
# ZONE 2: FLIGHT DECK (Middle)
# =============================================================================

# Left: Configuration
engine_controls = dbc.Card([
    dbc.CardBody([
        html.Div([
            html.H3("Configuration", className="section-header"),
            html.P("Define your vector search recipe", style={'fontSize': '0.875rem', 'color': 'hsl(var(--muted-foreground))', 'marginBottom': '16px'})
        ]),
        
        # Basic/Advanced Toggle
        dbc.ButtonGroup([
            dbc.Button("Basic", id='mode-basic', color="primary", size="sm", outline=True),
            dbc.Button("Advanced", id='mode-advanced', color="primary", size="sm", outline=True)
        ], className="mb-5"),
        
        # SECTION: Embedding Model
        html.Div([
            html.Div("Embedding Model", className="control-section-label"),
            dcc.Dropdown(
                id='model-dropdown',
                options=[
                    {'label': f"{k} — {v['description']}", 'value': k}
                    for k, v in FLIGHT_CONFIGS.items()
                ],
                value='bge-small',
                clearable=False,
                className="dash-dropdown mb-3",
                style={'width': '100%'}
            )
        ], className="mb-5"),
        
        # SECTION: Retrieval Engine
        html.Div([
            html.Div("Retrieval Engine", className="control-section-label"),
            html.Div([
                dbc.Button("Dense (Semantic)", 
                          id='btn-dense', color="primary", outline=False, className="segmented-btn"),
                dbc.Button("Sparse (Lexical)", 
                          id='btn-sparse', color="primary", outline=True, className="segmented-btn"),
                dbc.Button("Hybrid (Fusion)", 
                          id='btn-hybrid', color="primary", outline=True, className="segmented-btn")
            ], className="btn-group w-100 mb-3", id='retrieval-mode-group'),
            dcc.Store(id='retrieval-mode', data='dense'),
            
            # Hybrid fusion slider (conditional)
            html.Div([
                html.Div("Fusion Balance", className="control-section-label", style={'marginTop': '12px'}),
                dcc.Slider(
                    id='fusion-balance',
                    min=0,
                    max=100,
                    step=10,
                    value=70,
                    marks={0: 'Sparse', 50: '50/50', 100: 'Dense'},
                    tooltip={"placement": "bottom", "always_visible": True}
                ),
                html.Div(id='fusion-display', children="Dense 70% / Sparse 30%", 
                        style={'fontSize': '0.8125rem', 'textAlign': 'center', 'marginTop': '8px', 'color': 'hsl(var(--muted-foreground))'})
            ], id='fusion-controls', style={'display': 'none'})
        ], className="mb-5"),
        
        # SECTION: Noise Level
        html.Div([
            html.Div("Noise Level", className="control-section-label"),
            html.P("Simulates messier queries with irrelevant statutes", 
                  style={'fontSize': '0.8125rem', 'color': 'hsl(var(--muted-foreground))', 'margin': '4px 0 12px 0'}),
            dcc.Slider(
                id='noise-slider',
                min=100,
                max=1000,
                step=100,
                value=500,
                marks={100: {'label': 'Clean', 'style': {'fontSize': '0.7rem'}}, 
                       1000: {'label': 'Chaotic', 'style': {'fontSize': '0.7rem'}}},
                tooltip={"placement": "bottom", "always_visible": True}
            )
        ], className="mb-5"),
        
        # SECTION: Execution
        html.Hr(style={'borderColor': 'var(--border-default)', 'margin': '24px 0'}),
        html.Div([
            html.Div("Execution", className="control-section-label mb-3"),
            dbc.RadioItems(
                id='run-mode',
                options=[
                    {'label': '○ Single Run', 'value': 'single'},
                    {'label': '○ Parameter Sweep', 'value': 'sweep'}
                ],
                value='single',
                className="mb-4"
            ),
            html.Div([
                dbc.Button("Run Experiment", id='launch-button', color="primary", className="btn-mission-primary btn-launch w-100 mb-2"),
                dbc.Button("Dry Run", id='dry-run-button', color="secondary", 
                          className="btn-mission-secondary w-100 mb-2", outline=True),
                html.Div(id='flight-estimate', children="~90s · 1 recipe · 181 queries",
                        style={'fontSize': '0.8125rem', 'textAlign': 'center', 'color': 'hsl(var(--muted-foreground))'})
            ])
        ])
    ])
], className="mission-card", style={'height': '100%'})

# Right: Results
telemetry_panel = dbc.Card([
    dbc.CardBody([
        html.Div([
            html.H3("Results", className="section-header"),
            html.P("Compare recipes across quality, latency, and cost", 
                  style={'fontSize': '0.875rem', 'color': 'hsl(var(--muted-foreground))', 'marginBottom': '16px'})
        ]),
        
        # Experiment Summary (compact verdict)
        html.Div(id='experiment-summary', className="experiment-summary mb-3"),
        
        # Tabs
        dbc.Tabs([
            dbc.Tab(label="Overview", tab_id="tab-overview"),
            dbc.Tab(label="Quality", tab_id="tab-quality"),
            dbc.Tab(label="Latency & Cost", tab_id="tab-latency"),
            dbc.Tab(label="Robustness", tab_id="tab-robustness")
        ], id='telemetry-tabs', active_tab="tab-overview", className="mb-2"),
        
        # Tab description
        html.Div(id='tab-description', className="tab-description mb-3"),
        
        # Tab content
        html.Div(id='tab-content')
    ])
], className="mission-card", style={'height': '100%'})

flight_deck = dbc.Row([
    dbc.Col(engine_controls, md=4),
    dbc.Col(telemetry_panel, md=8)
], className="mb-5")

# =============================================================================
# ZONE 3: DIAGNOSTICS BAY (Bottom)
# =============================================================================

diagnostics_bay = dbc.Card([
    dbc.CardBody([
        html.Div([
            html.Div([
                html.H3("Query Diagnostics", className="section-header", style={'display': 'inline-block', 'marginBottom': '0'}),
                html.Span(" · Advanced analysis", style={'fontSize': '0.875rem', 'color': 'var(--text-dim)', 'marginLeft': '12px'})
            ], style={'marginBottom': '12px'}),
            html.P("Inspect individual queries to see where new runs improved or regressed versus baseline", 
                  style={'fontSize': '0.875rem', 'color': 'hsl(var(--muted-foreground))', 'marginBottom': '20px'})
        ]),
        
        # Skeleton table header + empty state
        html.Div([
            html.Div([
                    html.Div([
                        html.Span("Query", style={'flex': '3', 'fontWeight': '500'}),
                        html.Span("Baseline", style={'flex': '1', 'textAlign': 'center', 'fontWeight': '500'}),
                        html.Span("Selected Run", style={'flex': '1', 'textAlign': 'center', 'fontWeight': '500'}),
                        html.Span("Δ Rank", style={'flex': '1', 'textAlign': 'center', 'fontWeight': '500'})
                    ], style={'display': 'flex', 'padding': '12px 16px', 'fontSize': '0.875rem', 
                             'color': 'hsl(var(--muted-foreground))', 'borderBottom': '1px solid hsl(var(--border))',
                             'letterSpacing': '-0.01em'})
            ]),
                html.Div([
                    html.Div("⏱", style={'fontSize': '3rem', 'opacity': 0.2, 'textAlign': 'center', 'marginTop': '24px', 'marginBottom': '16px', 'color': 'var(--qd-violet)'}),
                html.P("Query Diagnostics lets you inspect individual queries and see where new runs improved or regressed versus baseline.", 
                      style={'textAlign': 'center', 'color': 'hsl(var(--muted-foreground))', 'fontSize': '0.875rem', 'lineHeight': '1.5', 'maxWidth': '600px', 'margin': '0 auto 24px auto'})
            ], style={'padding': '20px', 'border': '1px solid hsl(var(--border))', 
                     'borderTop': 'none', 'borderRadius': '0 0 calc(var(--radius) - 2px) calc(var(--radius) - 2px)'})
        ])
    ])
], className="mission-card")

# =============================================================================
# MAIN LAYOUT
# =============================================================================

app.layout = html.Div([
    dbc.Container([
        bridge_hud,
        flight_deck,
        diagnostics_bay,
        
        # Refresh interval
        dcc.Interval(id='interval', interval=1000, n_intervals=0)
    ], fluid=True, style={'maxWidth': '1600px', 'padding': '20px'})
])

# =============================================================================
# CALLBACKS
# =============================================================================

# Segmented button callbacks
@app.callback(
    [Output('btn-dense', 'outline'),
     Output('btn-sparse', 'outline'),
     Output('btn-hybrid', 'outline'),
     Output('retrieval-mode', 'data'),
     Output('fusion-controls', 'style')],
    [Input('btn-dense', 'n_clicks'),
     Input('btn-sparse', 'n_clicks'),
     Input('btn-hybrid', 'n_clicks')],
    prevent_initial_call=True
)
def update_retrieval_mode(dense_clicks, sparse_clicks, hybrid_clicks):
    ctx = callback_context
    if not ctx.triggered:
        return False, True, True, 'dense', {'display': 'none'}
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if button_id == 'btn-dense':
        return False, True, True, 'dense', {'display': 'none'}
    elif button_id == 'btn-sparse':
        return True, False, True, 'sparse', {'display': 'none'}
    elif button_id == 'btn-hybrid':
        return True, True, False, 'hybrid', {'display': 'block'}
    
    return False, True, True, 'dense', {'display': 'none'}

@app.callback(
    Output('fusion-display', 'children'),
    Input('fusion-balance', 'value')
)
def update_fusion_display(value):
    dense_pct = value
    sparse_pct = 100 - value
    return f"Dense {dense_pct}% / Sparse {sparse_pct}%"

@app.callback(
    [Output('kpi-recall', 'children'),
     Output('kpi-recall-detail', 'children'),
     Output('kpi-speed', 'children'),
     Output('kpi-speed-detail', 'children'),
     Output('kpi-cost', 'children'),
     Output('kpi-cost-detail', 'children'),
     Output('kpi-config', 'children'),
     Output('kpi-config-detail', 'children')],
    Input('interval', 'n_intervals')
)
def update_kpis(n):
    results = load_results()
    
    if not results:
        return "—", "Run an experiment to see winners here", "—", "Run an experiment to see winners here", "—", "Run an experiment to see winners here", "—", "None active"
    
    df = pd.DataFrame(results)
    df['recall@10'] = df['metrics'].apply(lambda x: x.get('recall@10', 0))
    df['avg_query_time_ms'] = df['metrics'].apply(lambda x: x.get('avg_query_time_ms', 0))
    
    latest = df.groupby('model_name').last()
    
    best_recall = latest['recall@10'].max()
    best_recall_model = latest['recall@10'].idxmax()
    
    fastest_time = latest['avg_query_time_ms'].min()
    fastest_model = latest['avg_query_time_ms'].idxmin()
    
    latest_run = df.iloc[-1]
    active_config = latest_run['model_name']
    active_recall = latest_run['recall@10']
    
    return (
        f"{best_recall:.2f}%",
        f"{best_recall_model}",
        f"{fastest_time:.0f}ms",
        f"{fastest_model}",
        "$0.23",
        "e5-small",
        active_config,
        f"R@10: {active_recall:.1f}%"
    )

@app.callback(
    Output('experiment-summary', 'children'),
    Input('interval', 'n_intervals')
)
def update_experiment_summary(n):
    results = load_results()
    
    if not results or len(results) < 2:
        return ""  # No summary until we have comparison data
    
    latest = results[-1]
    baseline = results[0]
    
    recall_delta = latest['metrics']['recall@10'] - baseline['metrics']['recall@10']
    time_delta = latest['metrics']['avg_query_time_ms'] - baseline['metrics']['avg_query_time_ms']
    
    status_icon = "✓" if recall_delta >= 0 else "!"
    status_class = "verdict-success" if recall_delta >= 0 else "verdict-danger"
    
    return html.Div([
        html.Span("Summary", className="verdict-pill", style={'marginRight': '12px'}),
        html.Span(f"{latest['model_name']} ", style={'fontWeight': '600'}),
        html.Span(f"delivers "),
        html.Span(f"{recall_delta:+.1f}% ", className="verdict-highlight"),
        html.Span(f"recall and "),
        html.Span(f"{time_delta:+.0f}ms ", className="verdict-highlight"),
        html.Span(f"latency vs baseline "),
        html.Span(f"{status_icon}", style={'marginLeft': '6px'})
    ], className=f"experiment-summary {status_class}")

@app.callback(
    [Output('tab-content', 'children'),
     Output('tab-description', 'children')],
    Input('telemetry-tabs', 'active_tab')
)
def render_tab_content(active_tab):
    # Tab descriptions
    descriptions = {
        'tab-overview': 'Compare runs across key metrics',
        'tab-quality': 'See Recall@K, nDCG, and MRR across runs',
        'tab-latency': 'Measure performance and cost trade-offs',
        'tab-robustness': 'Evaluate performance under noise and corruptions'
    }
    tab_desc = descriptions.get(active_tab, '')
    results = load_results()
    
    if not results:
        empty_state = html.Div([
            # Skeleton layout hint
            html.Div([
                html.Div("Run Leaderboard", style={'fontSize': '0.875rem', 'color': 'hsl(var(--foreground))', 
                                                   'marginBottom': '12px', 'fontWeight': '600', 'letterSpacing': '-0.01em'}),
                html.Div([
                    html.Div([
                        html.Span("Recipe", style={'flex': '2', 'fontWeight': '500'}),
                        html.Span("Recall@10", style={'flex': '1', 'fontWeight': '500'}),
                        html.Span("Latency", style={'flex': '1', 'fontWeight': '500'}),
                        html.Span("Status", style={'flex': '1', 'fontWeight': '500'})
                    ], style={'display': 'flex', 'padding': '12px 16px', 'fontSize': '0.875rem', 
                             'color': 'hsl(var(--muted-foreground))', 'borderBottom': '1px solid hsl(var(--border))',
                             'letterSpacing': '-0.01em'})
                ], style={'border': '1px solid hsl(var(--border))', 'borderRadius': 'calc(var(--radius) - 2px)'}),
                html.Div([
                    html.Div("📈", style={'fontSize': '4rem', 'opacity': 0.2, 'textAlign': 'center', 'marginBottom': '20px', 'marginTop': '24px', 'color': 'var(--qd-violet)'}),
                    html.P("No experiments yet", 
                          style={'textAlign': 'center', 'color': 'hsl(var(--foreground))', 'fontSize': '1rem', 'marginBottom': '8px', 'fontWeight': '500', 'letterSpacing': '-0.02em'}),
                    html.P("Configure a recipe on the left and run it to populate this leaderboard.", 
                          style={'textAlign': 'center', 'color': 'hsl(var(--muted-foreground))', 'fontSize': '0.875rem', 'lineHeight': '1.5', 'marginBottom': '20px'}),
                    dbc.Button("Run Your First Experiment", 
                              id='empty-state-cta', color="primary", className="btn-mission-primary", 
                              style={'margin': '0 auto', 'display': 'block', 'width': 'fit-content'})
                ], style={'padding': '24px'}),
            ], className="mb-4")
        ], style={'padding': '20px'})
        return empty_state, tab_desc
    
    if active_tab == "tab-overview":
        content = render_overview_tab(results)
    elif active_tab == "tab-quality":
        content = html.Div("Quality metrics coming soon...", style={'padding': '40px', 'textAlign': 'center', 'color': 'var(--text-secondary)'})
    elif active_tab == "tab-latency":
        content = html.Div("Latency analysis coming soon...", style={'padding': '40px', 'textAlign': 'center', 'color': 'var(--text-secondary)'})
    else:
        content = html.Div("Robustness testing coming soon...", style={'padding': '40px', 'textAlign': 'center', 'color': 'var(--text-secondary)'})
    
    return content, tab_desc

def render_overview_tab(results):
    df = pd.DataFrame(results)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Extract metrics
    for k in TOP_K_VALUES:
        df[f'recall@{k}'] = df['metrics'].apply(lambda x: x.get(f'recall@{k}', 0))
    df['avg_query_time_ms'] = df['metrics'].apply(lambda x: x.get('avg_query_time_ms', 0))
    
    # Recall chart
    recall_fig = go.Figure()
    for model in df['model_name'].unique():
        model_data = df[df['model_name'] == model].iloc[-1]
        recall_fig.add_trace(go.Bar(
            name=model,
            x=[f'@{k}' for k in TOP_K_VALUES],
            y=[model_data[f'recall@{k}'] for k in TOP_K_VALUES],
            text=[f"{model_data[f'recall@{k}']:.1f}%" for k in TOP_K_VALUES],
            textposition='outside'
        ))
    
    recall_fig.update_layout(
        title="Recall@K Performance",
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font={'color': '#e8e8f0'},
        showlegend=True,
        height=350
    )
    
    return html.Div([
        dcc.Graph(figure=recall_fig, config={'displayModeBar': False})
    ])

# Run experiment (stub - implement full logic)
@app.callback(
    Output('launch-button', 'disabled'),
    [Input('launch-button', 'n_clicks'),
     Input('empty-state-cta', 'n_clicks')],
    [State('model-dropdown', 'value'),
     State('noise-slider', 'value')],
    prevent_initial_call=True
)
def launch_experiment(main_clicks, empty_clicks, model, noise):
    # TODO: Implement full experiment runner
    return False

if __name__ == '__main__':
    print("\n" + "="*80)
    print("VECTOR SEARCH STUDIO")
    print("="*80)
    print("\n→ Studio Dashboard: http://localhost:8050")
    print("→ Status: Ready")
    print("→ Scenario: California Housing Law Retrieval")
    print("\nTune and benchmark Qdrant vector search configurations")
    print("Press Ctrl+C to exit\n")
    
    app.run(debug=True, host='0.0.0.0', port=8050)

