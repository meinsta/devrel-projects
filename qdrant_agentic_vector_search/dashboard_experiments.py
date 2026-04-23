"""
Interactive Experiment Dashboard - shadcn inspired design

Beautiful, modern UI for running and comparing embedding model experiments.
Run with: python dashboard_experiments.py
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
import plotly.express as px
import pandas as pd

load_dotenv()

# Configuration
QDRANT_URL = os.getenv('QDRANT_CLOUD_URL')
QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')
RESULTS_FILE = Path("experiment_results.json")

# Available embedding models
EMBEDDING_MODELS = {
    "bge-small": {
        "model_name": "BAAI/bge-small-en-v1.5",
        "vector_size": 384,
        "description": "Fast and efficient baseline",
        "icon": "⚡"
    },
    "bge-base": {
        "model_name": "BAAI/bge-base-en-v1.5",
        "vector_size": 768,
        "description": "Larger model with better quality",
        "icon": "🎯"
    },
    "minilm-l6": {
        "model_name": "sentence-transformers/all-MiniLM-L6-v2",
        "vector_size": 384,
        "description": "Popular SentenceTransformers model",
        "icon": "🚀"
    }
}

TOP_K_VALUES = [1, 3, 5, 10]

# Global state
experiment_running = False
current_experiment_status = ""

# Load or initialize results
def load_results():
    if RESULTS_FILE.exists():
        with open(RESULTS_FILE, 'r') as f:
            return json.load(f)
    return []

def save_results(results):
    with open(RESULTS_FILE, 'w') as f:
        json.dump(results, f, indent=2)

# [Previous helper functions remain the same]
def run_experiment_background(model_name, noise_level, callback_fn):
    """Run experiment in background thread."""
    global experiment_running, current_experiment_status
    
    try:
        experiment_running = True
        model_config = EMBEDDING_MODELS[model_name]
        
        current_experiment_status = f"Loading data..."
        callback_fn()
        
        questions, statutes = load_questions_and_statutes(noise_level)
        
        current_experiment_status = f"Loading model: {model_config['model_name']}..."
        callback_fn()
        
        embedding_model = TextEmbedding(model_name=model_config['model_name'])
        client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        
        current_experiment_status = "Creating collection..."
        callback_fn()
        
        collection_name = f"california_test_{model_name}_{int(time.time())}"
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=model_config['vector_size'],
                distance=Distance.COSINE
            )
        )
        
        current_experiment_status = f"Embedding {len(statutes)} statutes..."
        callback_fn()
        
        batch_size = 32
        start_embed = time.time()
        
        for i in range(0, len(statutes), batch_size):
            batch = statutes[i:i + batch_size]
            texts = [s['text'] for s in batch]
            embeddings = list(embedding_model.embed(texts))
            
            points = []
            for j, statute in enumerate(batch):
                point = PointStruct(
                    id=i + j,
                    vector=embeddings[j].tolist(),
                    payload={
                        'statute_idx': statute['idx'],
                        'text': statute['text'],
                        'citation': statute['citation']
                    }
                )
                points.append(point)
            
            client.upsert(collection_name=collection_name, points=points)
            
            progress = int((i + len(batch)) / len(statutes) * 100)
            current_experiment_status = f"Embedding statutes... {progress}%"
            callback_fn()
        
        embedding_time = time.time() - start_embed
        
        current_experiment_status = f"Evaluating on {len(questions)} questions..."
        callback_fn()
        
        start_eval = time.time()
        metrics = run_retrieval_evaluation(client, collection_name, questions, embedding_model)
        eval_time = time.time() - start_eval
        
        current_experiment_status = "Cleaning up..."
        callback_fn()
        client.delete_collection(collection_name)
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "model_name": model_name,
            "model_full_name": model_config['model_name'],
            "vector_size": model_config['vector_size'],
            "noise_level": noise_level,
            "num_questions": len(questions),
            "num_statutes": len(statutes),
            "embedding_time_s": embedding_time,
            "eval_time_s": eval_time,
            "metrics": metrics
        }
        
        results = load_results()
        results.append(result)
        save_results(results)
        
        current_experiment_status = "✅ Complete!"
        callback_fn()
        
    except Exception as e:
        current_experiment_status = f"❌ Error: {str(e)}"
        callback_fn()
    finally:
        experiment_running = False

def load_questions_and_statutes(noise_level=500):
    questions_dataset = load_dataset(
        "reglab/housing_qa",
        "questions",
        split="test",
        trust_remote_code=True
    )
    
    questions = []
    golden_ids = set()
    
    for item in questions_dataset:
        if item['state'] and item['state'].lower() == 'california':
            statute_ids = []
            if 'statutes' in item and item['statutes']:
                statute_ids = [s.get('statute_idx') for s in item['statutes'] if 'statute_idx' in s]
            
            questions.append({
                'idx': item['idx'],
                'question': item['question'],
                'golden_statute_ids': statute_ids
            })
            golden_ids.update(statute_ids)
    
    statutes_dataset = load_dataset(
        "reglab/housing_qa",
        "statutes",
        split="corpus",
        trust_remote_code=True
    )
    
    california_statutes = []
    golden_statutes = []
    
    for item in statutes_dataset:
        if item['state'] == 'california':
            statute = {
                'idx': item['idx'],
                'text': item['text'],
                'citation': item['citation'],
                'state': item['state'],
                'path': item['path']
            }
            
            if item['idx'] in golden_ids:
                golden_statutes.append(statute)
            else:
                california_statutes.append(statute)
    
    noise_statutes = random.sample(california_statutes, min(noise_level, len(california_statutes)))
    all_statutes = golden_statutes + noise_statutes
    random.shuffle(all_statutes)
    
    return questions, all_statutes

def run_retrieval_evaluation(client, collection_name, questions, embedding_model):
    results = {k: [] for k in TOP_K_VALUES}
    mrr_scores = {k: [] for k in TOP_K_VALUES}
    query_times = []
    
    for question in questions:
        start = time.time()
        query_embedding = list(embedding_model.embed([question['question']]))[0]
        
        search_results = client.query_points(
            collection_name=collection_name,
            query=query_embedding.tolist(),
            limit=max(TOP_K_VALUES)
        )
        
        query_time = time.time() - start
        query_times.append(query_time)
        
        retrieved_ids = [r.payload['statute_idx'] for r in search_results.points]
        golden_ids = set(question['golden_statute_ids'])
        
        for k in TOP_K_VALUES:
            top_k_ids = retrieved_ids[:k]
            recall = 1 if any(rid in golden_ids for rid in top_k_ids) else 0
            results[k].append(recall)
            
            mrr = 0
            for rank, rid in enumerate(top_k_ids, start=1):
                if rid in golden_ids:
                    mrr = 1 / rank
                    break
            mrr_scores[k].append(mrr)
    
    metrics = {}
    for k in TOP_K_VALUES:
        metrics[f'recall@{k}'] = sum(results[k]) / len(results[k]) * 100
        metrics[f'mrr@{k}'] = sum(mrr_scores[k]) / len(mrr_scores[k])
    
    metrics['avg_query_time_ms'] = sum(query_times) / len(query_times) * 1000
    
    return metrics

# Initialize Dash app with custom external stylesheets
external_stylesheets = [
    dbc.themes.BOOTSTRAP,
    'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap'
]

app = dash.Dash(__name__, external_stylesheets=external_stylesheets, suppress_callback_exceptions=True)
app.title = "Embedding Experiments"

# Add custom CSS inline
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            body {
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
                background: linear-gradient(to bottom right, #fafafa, #f4f4f5) !important;
                color: #09090b !important;
            }
            .card {
                background: white !important;
                border: 1px solid #e4e4e7 !important;
                border-radius: 12px !important;
                box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05) !important;
                transition: all 0.2s ease !important;
            }
            .card:hover {
                box-shadow: 0 4px 12px 0 rgba(0, 0, 0, 0.08) !important;
            }
            h1, h2, h3 {
                font-weight: 600 !important;
                letter-spacing: -0.02em !important;
            }
            .btn-dark {
                border-radius: 8px !important;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

# Layout
app.layout = html.Div([
    dbc.Container([
        # Header
        html.Div([
            html.H1("🔬 Embedding Experiments", className="mt-5 mb-2", 
                   style={'fontSize': '2.5rem', 'fontWeight': '700'}),
            html.P("Compare and evaluate different embedding models for retrieval tasks",
                   style={'fontSize': '1.1rem', 'color': '#71717a', 'marginBottom': '40px'})
        ]),
        
        # Stats Row
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.Span("📊", style={'fontSize': '2rem'}),
                            html.Div([
                                html.H3(id='total-experiments', children="0", 
                                       style={'fontSize': '2rem', 'fontWeight': '700', 'margin': '8px 0 4px 0'}),
                                html.P("Total Experiments", style={'color': '#71717a', 'margin': 0, 'fontSize': '0.9rem'})
                            ], style={'marginLeft': '12px'})
                        ], style={'display': 'flex', 'alignItems': 'center'})
                    ])
                ], className="card")
            ], md=3),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.Span("🎯", style={'fontSize': '2rem'}),
                            html.Div([
                                html.H3(id='best-recall', children="—", 
                                       style={'fontSize': '2rem', 'fontWeight': '700', 'margin': '8px 0 4px 0'}),
                                html.P("Best Recall@5", style={'color': '#71717a', 'margin': 0, 'fontSize': '0.9rem'})
                            ], style={'marginLeft': '12px'})
                        ], style={'display': 'flex', 'alignItems': 'center'})
                    ])
                ], className="card")
            ], md=3),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.Span("⚡", style={'fontSize': '2rem'}),
                            html.Div([
                                html.H3(id='fastest-model', children="—", 
                                       style={'fontSize': '2rem', 'fontWeight': '700', 'margin': '8px 0 4px 0'}),
                                html.P("Fastest Model", style={'color': '#71717a', 'margin': 0, 'fontSize': '0.9rem'})
                            ], style={'marginLeft': '12px'})
                        ], style={'display': 'flex', 'alignItems': 'center'})
                    ])
                ], className="card")
            ], md=3),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.Span("🏆", style={'fontSize': '2rem'}),
                            html.Div([
                                html.H3(id='best-model', children="—", 
                                       style={'fontSize': '2rem', 'fontWeight': '700', 'margin': '8px 0 4px 0'}),
                                html.P("Best Model", style={'color': '#71717a', 'margin': 0, 'fontSize': '0.9rem'})
                            ], style={'marginLeft': '12px'})
                        ], style={'display': 'flex', 'alignItems': 'center'})
                    ])
                ], className="card")
            ], md=3)
        ], className="mb-4"),
        
        # Control Panel
        dbc.Card([
            dbc.CardBody([
                html.H3("⚙️ Run New Experiment", className="mb-4", style={'fontSize': '1.3rem'}),
                dbc.Row([
                    dbc.Col([
                        html.Label("Embedding Model", style={'fontWeight': '500', 'marginBottom': '8px', 'display': 'block'}),
                        dcc.Dropdown(
                            id='model-dropdown',
                            options=[
                                {'label': f"{v['icon']} {k}: {v['description']}", 'value': k}
                                for k, v in EMBEDDING_MODELS.items()
                            ],
                            value='bge-small',
                            style={'borderRadius': '8px'}
                        )
                    ], md=6),
                    dbc.Col([
                        html.Label("Noise Level (random statutes)", style={'fontWeight': '500', 'marginBottom': '8px', 'display': 'block'}),
                        dcc.Slider(
                            id='noise-slider',
                            min=100,
                            max=1000,
                            step=100,
                            value=500,
                            marks={i: {'label': str(i), 'style': {'fontSize': '0.85rem'}} for i in range(100, 1001, 200)},
                            tooltip={"placement": "bottom", "always_visible": True}
                        )
                    ], md=6)
                ], className="mb-4"),
                dbc.Row([
                    dbc.Col([
                        dbc.Button("▶️ Run Experiment", id='run-button', color="dark", size="lg", 
                                  className="me-2", style={'borderRadius': '8px', 'fontWeight': '500'}),
                        dbc.Button("🗑️ Clear History", id='clear-button', color="secondary", outline=True, size="lg",
                                  style={'borderRadius': '8px', 'fontWeight': '500'}),
                        html.Span(id='experiment-status', className="ms-3", 
                                 style={'fontSize': '0.95rem', 'fontWeight': '500'})
                    ])
                ])
            ])
        ], className="card mb-4"),
        
        # Charts
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H3("📈 Recall@K Performance", className="mb-3", style={'fontSize': '1.2rem'}),
                        dcc.Graph(id='recall-chart', config={'displayModeBar': False})
                    ])
                ], className="card")
            ], md=6),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H3("🎯 Mean Reciprocal Rank", className="mb-3", style={'fontSize': '1.2rem'}),
                        dcc.Graph(id='mrr-chart', config={'displayModeBar': False})
                    ])
                ], className="card")
            ], md=6)
        ], className="mb-4"),
        
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H3("⚡ Performance Metrics", className="mb-3", style={'fontSize': '1.2rem'}),
                        dcc.Graph(id='performance-chart', config={'displayModeBar': False})
                    ])
                ], className="card")
            ], md=12)
        ], className="mb-4"),
        
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H3("📊 Experiment Timeline", className="mb-3", style={'fontSize': '1.2rem'}),
                        dcc.Graph(id='history-chart', config={'displayModeBar': False})
                    ])
                ], className="card")
            ], md=12)
        ], className="mb-5")
        
    ], fluid=True, style={'maxWidth': '1400px'}),
    
    # Refresh interval
    dcc.Interval(id='interval-component', interval=1000, n_intervals=0)
])

# Callbacks
@app.callback(
    [Output('total-experiments', 'children'),
     Output('best-recall', 'children'),
     Output('fastest-model', 'children'),
     Output('best-model', 'children'),
     Output('experiment-status', 'children')],
    [Input('interval-component', 'n_intervals')]
)
def update_stats(n):
    global experiment_running, current_experiment_status
    
    results = load_results()
    
    if not results:
        return "0", "—", "—", "—", ""
    
    df = pd.DataFrame(results)
    
    # Extract metrics
    df['recall@5'] = df['metrics'].apply(lambda x: x.get('recall@5', 0))
    df['embedding_time_s'] = df['embedding_time_s']
    
    # Get latest result per model
    latest = df.groupby('model_name').last()
    
    total_exp = len(results)
    best_recall = f"{latest['recall@5'].max():.1f}%"
    fastest = latest['embedding_time_s'].idxmin() if len(latest) > 0 else "—"
    best = latest['recall@5'].idxmax() if len(latest) > 0 else "—"
    
    status = ""
    if experiment_running:
        status = html.Span([
            html.Span("● ", style={'color': '#f59e0b'}),
            current_experiment_status
        ], className="status-badge running")
    
    return str(total_exp), best_recall, fastest, best, status

@app.callback(
    [Output('recall-chart', 'figure'),
     Output('mrr-chart', 'figure'),
     Output('performance-chart', 'figure'),
     Output('history-chart', 'figure')],
    [Input('interval-component', 'n_intervals'),
     Input('clear-button', 'n_clicks')],
    prevent_initial_call=False
)
def update_charts(n, clear_clicks):
    ctx = callback_context
    
    if ctx.triggered and ctx.triggered[0]['prop_id'] == 'clear-button.n_clicks' and clear_clicks > 0:
        save_results([])
    
    results = load_results()
    
    # Chart theme
    chart_template = {
        'layout': {
            'plot_bgcolor': 'rgba(0,0,0,0)',
            'paper_bgcolor': 'rgba(0,0,0,0)',
            'font': {'family': 'Inter, sans-serif', 'color': '#09090b'},
            'xaxis': {'gridcolor': '#f4f4f5', 'showgrid': True},
            'yaxis': {'gridcolor': '#f4f4f5', 'showgrid': True}
        }
    }
    
    if not results:
        empty_fig = go.Figure()
        empty_fig.update_layout(
            **chart_template['layout'],
            annotations=[{
                'text': 'No experiments yet 🔬<br>Run an experiment to see results',
                'xref': 'paper', 'yref': 'paper',
                'x': 0.5, 'y': 0.5,
                'showarrow': False,
                'font': {'size': 16, 'color': '#a1a1aa'}
            }],
            xaxis={'visible': False},
            yaxis={'visible': False},
            height=300
        )
        return empty_fig, empty_fig, empty_fig, empty_fig
    
    df = pd.DataFrame(results)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    for k in TOP_K_VALUES:
        df[f'recall@{k}'] = df['metrics'].apply(lambda x: x.get(f'recall@{k}', 0))
        df[f'mrr@{k}'] = df['metrics'].apply(lambda x: x.get(f'mrr@{k}', 0))
    df['avg_query_time_ms'] = df['metrics'].apply(lambda x: x.get('avg_query_time_ms', 0))
    
    # Color palette
    colors = ['#667eea', '#764ba2', '#f093fb']
    
    # Recall Chart
    recall_fig = go.Figure()
    for idx, model_name in enumerate(df['model_name'].unique()):
        model_data = df[df['model_name'] == model_name].iloc[-1]
        recall_fig.add_trace(go.Bar(
            name=model_name,
            x=[f'Top {k}' for k in TOP_K_VALUES],
            y=[model_data[f'recall@{k}'] for k in TOP_K_VALUES],
            text=[f"{model_data[f'recall@{k}']:.1f}%" for k in TOP_K_VALUES],
            textposition='outside',
            marker_color=colors[idx % len(colors)],
            hovertemplate='%{y:.1f}%<extra></extra>'
        ))
    
    recall_fig.update_layout(
        **chart_template['layout'],
        barmode='group',
        xaxis_title='',
        yaxis_title='Recall (%)',
        showlegend=True,
        legend={'orientation': 'h', 'y': 1.1, 'x': 0.5, 'xanchor': 'center'},
        height=350,
        margin={'t': 40}
    )
    
    # MRR Chart
    mrr_fig = go.Figure()
    for idx, model_name in enumerate(df['model_name'].unique()):
        model_data = df[df['model_name'] == model_name].iloc[-1]
        mrr_fig.add_trace(go.Scatter(
            name=model_name,
            x=[f'Top {k}' for k in TOP_K_VALUES],
            y=[model_data[f'mrr@{k}'] for k in TOP_K_VALUES],
            mode='lines+markers',
            line={'width': 3, 'color': colors[idx % len(colors)]},
            marker={'size': 10},
            hovertemplate='%{y:.3f}<extra></extra>'
        ))
    
    mrr_fig.update_layout(
        **chart_template['layout'],
        xaxis_title='',
        yaxis_title='MRR',
        showlegend=True,
        legend={'orientation': 'h', 'y': 1.1, 'x': 0.5, 'xanchor': 'center'},
        height=350,
        margin={'t': 40}
    )
    
    # Performance Chart
    perf_data = []
    for model_name in df['model_name'].unique():
        model_data = df[df['model_name'] == model_name].iloc[-1]
        perf_data.append({
            'Model': model_name,
            'Embedding Time (s)': model_data['embedding_time_s'],
            'Query Time (ms)': model_data['avg_query_time_ms']
        })
    
    perf_df = pd.DataFrame(perf_data)
    
    perf_fig = go.Figure()
    perf_fig.add_trace(go.Bar(
        name='Embedding Time (s)',
        x=perf_df['Model'],
        y=perf_df['Embedding Time (s)'],
        marker_color='#667eea',
        hovertemplate='%{y:.1f}s<extra></extra>'
    ))
    perf_fig.add_trace(go.Bar(
        name='Query Time (ms)',
        x=perf_df['Model'],
        y=perf_df['Query Time (ms)'],
        marker_color='#764ba2',
        hovertemplate='%{y:.1f}ms<extra></extra>'
    ))
    
    perf_fig.update_layout(
        **chart_template['layout'],
        barmode='group',
        xaxis_title='',
        yaxis_title='Time',
        showlegend=True,
        legend={'orientation': 'h', 'y': 1.1, 'x': 0.5, 'xanchor': 'center'},
        height=350,
        margin={'t': 40}
    )
    
    # History Chart
    history_fig = go.Figure()
    for idx, model_name in enumerate(df['model_name'].unique()):
        model_history = df[df['model_name'] == model_name]
        history_fig.add_trace(go.Scatter(
            name=model_name,
            x=model_history['timestamp'],
            y=model_history['recall@5'],
            mode='lines+markers',
            line={'width': 3, 'color': colors[idx % len(colors)]},
            marker={'size': 8},
            hovertemplate='%{y:.1f}%<extra></extra>'
        ))
    
    history_fig.update_layout(
        **chart_template['layout'],
        xaxis_title='',
        yaxis_title='Recall@5 (%)',
        showlegend=True,
        legend={'orientation': 'h', 'y': 1.1, 'x': 0.5, 'xanchor': 'center'},
        height=350,
        margin={'t': 40}
    )
    
    return recall_fig, mrr_fig, perf_fig, history_fig

@app.callback(
    Output('run-button', 'disabled'),
    [Input('run-button', 'n_clicks'),
     Input('interval-component', 'n_intervals')],
    [State('model-dropdown', 'value'),
     State('noise-slider', 'value')],
    prevent_initial_call=True
)
def run_experiment(n_clicks, n_intervals, model_name, noise_level):
    ctx = callback_context
    
    if ctx.triggered and ctx.triggered[0]['prop_id'] == 'run-button.n_clicks':
        if not experiment_running:
            thread = Thread(
                target=run_experiment_background,
                args=(model_name, noise_level, lambda: None)
            )
            thread.daemon = True
            thread.start()
    
    return experiment_running

if __name__ == '__main__':
    print("\n" + "="*80)
    print("🚀 Starting Embedding Experiments Dashboard")
    print("="*80)
    print("\n✨ Dashboard URL: http://localhost:8050")
    print("📖 Press Ctrl+C to stop\n")
    
    app.run(debug=False, host='0.0.0.0', port=8050)
