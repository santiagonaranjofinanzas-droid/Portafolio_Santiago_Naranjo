"""
generate_visualizations.py - Generador de Visualizaciones 3D Interactivas
Crea los gráficos dinámicos de:
1. Superficie de Correlación Condicional (Terrain 3D)
2. MDS 3D Animado (Proyección Geométrica con Procrustes)
3. MST 3D Animado (Grafo de Expansión Mínima sobre MDS)
"""

import sys
import os
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from sklearn.manifold import MDS
import logging

#Agregar ruta de trabajo
sys.path.append(r"c:\Users\YOUR_USERNAME\Desktop\Universidad\Tesis_2026\Tesis_Repotenciada")

from VolatilityEngine import VolatilityEngine
from TopologyEngine import TopologyEngine
from analyze_detection_capacity import generate_multi_crisis_data, compute_drawdown_target

#Configuración de logs
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Visualizer")

def procrustes_align(target, source):
    """
    Alineación ortogonal de Procrustes para estabilizar los ejes en la animación MDS
    y evitar el jittering rotacional entre frames.
    """
    mu_target = np.mean(target, axis=0)
    mu_source = np.mean(source, axis=0)
    
    target_c = target - mu_target
    source_c = source - mu_source
    
    # Descomposición en valores singulares (SVD) de la matriz de covarianza cruzada
    U, S, Vt = np.linalg.svd(np.dot(target_c.T, source_c))
    
    # Matriz de rotación óptima
    R = np.dot(Vt.T, U.T)
    
    # Alinear y re-centrar sobre el objetivo
    source_aligned = np.dot(source_c, R) + mu_target
    return source_aligned

def compute_mst_edges(N, R_t):
    """
    Calcula los enlaces del Minimum Spanning Tree (MST) usando el algoritmo de Kruskal
    para una matriz de correlación R_t en el instante t.
    """
    edges = []
    for i in range(N):
        for j in range(i):
            # Distancia métrica de Mantegna
            dist = np.sqrt(2.0 * (1.0 - R_t[i, j]))
            edges.append((dist, i, j))
    edges.sort()
    
    # Union-Find simple
    parent = list(range(N))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
        
    def union(i, j):
        root_i = find(i)
        root_j = find(j)
        if root_i != root_j:
            parent[root_i] = root_j
            return True
        return False
        
    mst_edges = []
    for dist, u, v in edges:
        if union(u, v):
            mst_edges.append((u, v, dist))
            if len(mst_edges) == N - 1:
                break
    return mst_edges

def main():
    logger.info("1. Generando datos de mercado con crisis...")
    T, N = 1200, 26
    data, crisis_periods = generate_multi_crisis_data(T=T, N=N)
    
    # Mapear columnas a nombres reales de activos para evitar genéricos 'Asset_X'
    REAL_ASSET_NAMES = [
        "S&P 500", "Nasdaq 100", "Dow Jones", "DAX 40", "FTSE 100", "Nikkei 225", "Euro Stoxx 50",
        "EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CAD", "USD/CHF",
        "Oro", "Plata", "Crudo Brent", "Gas Natural", "Cobre", "Trigo", "Maíz",
        "EEUU 10Y", "EEUU 2Y", "Alemania 10Y", "Reino Unido 10Y", "Japón 10Y", "EEUU 5Y"
    ]
    data.columns = REAL_ASSET_NAMES
    
    logger.info("2. Ejecutando el pipeline DCC-GARCH...")
    v_engine = VolatilityEngine(data)
    v_engine.fit(n_jobs=2)
    
    H_t = v_engine.get_conditional_covariances()
    R_t = v_engine.get_conditional_correlations()
    
    # Definir categorías de activos para colorear los nodos
    # Asset_1 a Asset_7: Renta Variable (Equities)
    # Asset_8 a Asset_13: Divisas (FX)
    # Asset_14 a Asset_20: Materias Primas (Commodities)
    # Asset_21 a Asset_26: Renta Fija (Bonds)
    categories = []
    colors = []
    for i in range(N):
        if i < 7:
            categories.append("Renta Variable")
            colors.append("#3b82f6")  # Azul neón
        elif i < 13:
            categories.append("FX (Divisas)")
            colors.append("#10b981")  # Verde esmeralda
        elif i < 20:
            categories.append("Commodities")
            colors.append("#f59e0b")  # Oro/Naranja
        else:
            categories.append("Renta Fija")
            colors.append("#8b5cf6")  # Violeta neón
            
    # Seleccionar ventana de interés alrededor del primer evento de crisis (t=250 a 300)
    # Tomamos desde t=180 (estabilidad) hasta t=320 (recuperación)
    start_t, end_t = 180, 320
    window_length = end_t - start_t
    dates_window = data.index[start_t:end_t]
    
    # Guardar las matrices de correlación de la ventana
    R_window = R_t[start_t:end_t]
    
    logger.info(f"3. Calculando proyecciones MDS 3D con Procrustes (t = {start_t} a {end_t})...")
    mds = MDS(n_components=3, dissimilarity='precomputed', random_state=42, max_iter=300, eps=1e-6)
    
    # Contenedores para las coordenadas de todos los días
    coords_history = np.zeros((window_length, N, 3))
    
    # Primer día como referencia inicial
    D_initial = np.sqrt(2.0 * np.maximum(0.0, 1.0 - R_window[0]))
    coords_history[0] = mds.fit_transform(D_initial)
    
    for t_idx in range(1, window_length):
        D_t = np.sqrt(2.0 * np.maximum(0.0, 1.0 - R_window[t_idx]))
        coords_raw = mds.fit_transform(D_t)
        # Alinear con respecto al día anterior para evitar jittering
        coords_history[t_idx] = procrustes_align(coords_history[t_idx - 1], coords_raw)
        
    # ==========================================
    # VISUALIZACIÓN 1: TERRENO DE CORRELACIÓN 3D
    # ==========================================
    logger.info("Generando Visualización 1: Superficie de Correlación 3D...")
    # X: Activos del 1 al 26
    # Y: Línea temporal de la ventana (días indexados)
    # Z: Correlación condicional de cada activo con Asset_1 (SPX500)
    x_surf = np.arange(N)
    y_surf = np.arange(window_length)
    z_surf = np.zeros((window_length, N))
    
    for t_idx in range(window_length):
        z_surf[t_idx, :] = R_window[t_idx, 0, :] # Correlación con Asset_1
        
    fig_surf = go.Figure(data=[go.Surface(
        z=z_surf,
        x=[v_engine.assets[i] for i in x_surf],
        y=[dates_window[t].strftime('%Y-%m-%d') for t in y_surf],
        colorscale='Viridis',
        colorbar=dict(title=dict(text='Correlación con SPX500', font=dict(color='#ffffff')), tickfont=dict(color='#ffffff'))
    )])
    
    fig_surf.update_layout(
        title={
            'text': "Superficie de Correlación Condicional Dinámica con SPX500 (DCC-GARCH)",
            'y':0.95, 'x':0.5, 'xanchor': 'center', 'yanchor': 'top',
            'font': {'size': 20, 'color': '#ffffff'}
        },
        scene=dict(
            xaxis=dict(title=dict(text='Activos', font=dict(color='#ffffff')), backgroundcolor="rgb(20, 20, 30)", gridcolor="rgba(100,100,100,0.2)", showbackground=True, tickfont=dict(color='#ffffff')),
            yaxis=dict(title=dict(text='Tiempo (t)', font=dict(color='#ffffff')), backgroundcolor="rgb(20, 20, 30)", gridcolor="rgba(100,100,100,0.2)", showbackground=True, tickfont=dict(color='#ffffff')),
            zaxis=dict(title=dict(text='Correlación', font=dict(color='#ffffff')), backgroundcolor="rgb(20, 20, 30)", gridcolor="rgba(100,100,100,0.2)", showbackground=True, tickfont=dict(color='#ffffff'), range=[-0.2, 1.05])
        ),
        paper_bgcolor='rgb(10, 10, 18)',
        plot_bgcolor='rgb(10, 10, 18)',
        margin=dict(l=10, r=10, t=50, b=10)
    )
    fig_surf.write_html("correlation_surface_3d.html", include_plotlyjs="cdn")
    
    # ==========================================
    # VISUALIZACIÓN 2: MDS 3D ANIMADO
    # ==========================================
    logger.info("Generando Visualización 2: Dispersión MDS 3D Animada...")
    
    # Inicializar figura
    fig_mds = go.Figure()
    
    # Agregar trazas iniciales para cada categoría para separarlos en la leyenda
    categories_unique = ["Renta Variable", "FX (Divisas)", "Commodities", "Renta Fija"]
    category_colors = ["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6"]
    
    for cat, col in zip(categories_unique, category_colors):
        indices = [i for i, c in enumerate(categories) if c == cat]
        fig_mds.add_trace(go.Scatter3d(
            x=coords_history[0, indices, 0],
            y=coords_history[0, indices, 1],
            z=coords_history[0, indices, 2],
            mode='markers+text',
            marker=dict(size=8, color=col, opacity=0.85, line=dict(width=1, color='#ffffff')),
            text=[v_engine.assets[i] for i in indices],
            textposition="top center",
            textfont=dict(size=9, color="#ffffff"),
            name=cat
        ))
        
    # Crear frames de animación
    frames = []
    for t_idx in range(window_length):
        frame_data = []
        for cat, col in zip(categories_unique, category_colors):
            indices = [i for i, c in enumerate(categories) if c == cat]
            frame_data.append(go.Scatter3d(
                x=coords_history[t_idx, indices, 0],
                y=coords_history[t_idx, indices, 1],
                z=coords_history[t_idx, indices, 2],
                text=[v_engine.assets[i] for i in indices]
            ))
        frames.append(go.Frame(
            data=frame_data,
            name=dates_window[t_idx].strftime('%Y-%m-%d')
        ))
        
    fig_mds.frames = frames
    
    # Configurar controladores de animación (Slider y Botón Play)
    sliders_dict = {
        "active": 0,
        "yanchor": "top",
        "xanchor": "left",
        "currentvalue": {
            "font": {"size": 16, "color": "#ffffff"},
            "prefix": "Fecha de Inferencia: ",
            "visible": True,
            "xanchor": "right"
        },
        "transition": {"duration": 100, "easing": "cubic-in-out"},
        "pad": {"b": 10, "t": 50},
        "len": 0.9,
        "x": 0.1,
        "y": 0,
        "steps": []
    }
    
    for t_idx in range(window_length):
        date_str = dates_window[t_idx].strftime('%Y-%m-%d')
        # Determinar si el día actual es parte del pánico (t=250 a 300)
        status_suffix = " (CRISIS / APANICAMIENTO)" if (250 <= (start_t + t_idx) <= 300) else " (ESTABLE)"
        slider_step = {
            "args": [
                [date_str],
                {"frame": {"duration": 100, "redraw": True},
                 "mode": "immediate",
                 "transition": {"duration": 100}}
            ],
            "label": date_str + status_suffix,
            "method": "animate"
        }
        sliders_dict["steps"].append(slider_step)
        
    fig_mds.update_layout(
        title={
            'text': "Escalamiento Multidimensional 3D Dinámico (MDS) - Colapso Geométrico",
            'y':0.95, 'x':0.5, 'xanchor': 'center', 'yanchor': 'top',
            'font': {'size': 20, 'color': '#ffffff'}
        },
        scene=dict(
            xaxis=dict(title=dict(text='Dimensión 1', font=dict(color='#ffffff')), backgroundcolor="rgb(15, 15, 25)", gridcolor="rgba(100,100,100,0.15)", showbackground=True, tickfont=dict(color='#aaaaaa'), range=[-1.8, 1.8]),
            yaxis=dict(title=dict(text='Dimensión 2', font=dict(color='#ffffff')), backgroundcolor="rgb(15, 15, 25)", gridcolor="rgba(100,100,100,0.15)", showbackground=True, tickfont=dict(color='#aaaaaa'), range=[-1.8, 1.8]),
            zaxis=dict(title=dict(text='Dimensión 3', font=dict(color='#ffffff')), backgroundcolor="rgb(15, 15, 25)", gridcolor="rgba(100,100,100,0.15)", showbackground=True, tickfont=dict(color='#aaaaaa'), range=[-1.8, 1.8])
        ),
        paper_bgcolor='rgb(10, 10, 18)',
        plot_bgcolor='rgb(10, 10, 18)',
        legend=dict(font=dict(color='#ffffff'), bgcolor='rgba(20,20,30,0.5)', bordercolor='rgba(255,255,255,0.1)', borderwidth=1),
        updatemenus=[{
            "buttons": [
                {
                    "args": [None, {"frame": {"duration": 100, "redraw": True}, "fromcurrent": True, "transition": {"duration": 100, "easing": "quadratic-in-out"}}],
                    "label": "▶ Play",
                    "method": "animate"
                },
                {
                    "args": [[None], {"frame": {"duration": 0, "redraw": True}, "mode": "immediate", "transition": {"duration": 0}}],
                    "label": " Pause",
                    "method": "animate"
                }
            ],
            "direction": "left",
            "pad": {"r": 10, "t": 87},
            "showactive": False,
            "type": "buttons",
            "x": 0.1,
            "xanchor": "right",
            "y": 0,
            "yanchor": "top",
            "font": {"color": "#ffffff"}
        }],
        sliders=[sliders_dict],
        margin=dict(l=10, r=10, t=50, b=10)
    )
    fig_mds.write_html("mds_rotation_3d.html", include_plotlyjs="cdn")
    
    # ==========================================
    # VISUALIZACIÓN 3: MST 3D ANIMADO
    # ==========================================
    logger.info("Generando Visualización 3: Grafo MST 3D Animado...")
    
    # Para animar el MST necesitamos representar dos elementos en el mismo gráfico:
    # 1. Las aristas (líneas 3D discontinuas separadas por None) -> Trace 0
    # 2. Los nodos (puntos 3D coloreados por categoría) -> Traces 1-4
    
    # Generar aristas iniciales de MST a t=0
    initial_mst = compute_mst_edges(N, R_window[0])
    edge_x = []
    edge_y = []
    edge_z = []
    for u, v, _ in initial_mst:
        edge_x.extend([coords_history[0, u, 0], coords_history[0, v, 0], None])
        edge_y.extend([coords_history[0, u, 1], coords_history[0, v, 1], None])
        edge_z.extend([coords_history[0, u, 2], coords_history[0, v, 2], None])
        
    fig_mst = go.Figure()
    
    # Traza 0: Aristas del MST (Líneas grises translúcidas)
    fig_mst.add_trace(go.Scatter3d(
        x=edge_x, y=edge_y, z=edge_z,
        mode='lines',
        line=dict(color='rgba(200, 200, 255, 0.4)', width=2.5),
        hoverinfo='none',
        name='Enlaces MST (Distancia Mantegna)'
    ))
    
    # Trazas 1-4: Nodos (Activos)
    for cat, col in zip(categories_unique, category_colors):
        indices = [i for i, c in enumerate(categories) if c == cat]
        fig_mst.add_trace(go.Scatter3d(
            x=coords_history[0, indices, 0],
            y=coords_history[0, indices, 1],
            z=coords_history[0, indices, 2],
            mode='markers+text',
            marker=dict(size=7, color=col, opacity=0.9, line=dict(width=1, color='#ffffff')),
            text=[v_engine.assets[i] for i in indices],
            textposition="top center",
            textfont=dict(size=8, color="#ffffff"),
            name=cat
        ))
        
    # Construir frames de animación
    frames_mst = []
    for t_idx in range(window_length):
        # Calcular aristas de este día
        mst_t = compute_mst_edges(N, R_window[t_idx])
        e_x = []
        e_y = []
        e_z = []
        for u, v, _ in mst_t:
            e_x.extend([coords_history[t_idx, u, 0], coords_history[t_idx, v, 0], None])
            e_y.extend([coords_history[t_idx, u, 1], coords_history[t_idx, v, 1], None])
            e_z.extend([coords_history[t_idx, u, 2], coords_history[t_idx, v, 2], None])
            
        frame_data = [
            # Actualizar aristas (Trace 0)
            go.Scatter3d(x=e_x, y=e_y, z=e_z)
        ]
        # Actualizar nodos (Traces 1-4)
        for cat in categories_unique:
            indices = [i for i, c in enumerate(categories) if c == cat]
            frame_data.append(go.Scatter3d(
                x=coords_history[t_idx, indices, 0],
                y=coords_history[t_idx, indices, 1],
                z=coords_history[t_idx, indices, 2],
                text=[v_engine.assets[i] for i in indices]
            ))
            
        frames_mst.append(go.Frame(
            data=frame_data,
            name=dates_window[t_idx].strftime('%Y-%m-%d')
        ))
        
    fig_mst.frames = frames_mst
    
    # Copiar sliders de MDS modificando la traza afectada
    sliders_mst = {
        "active": 0,
        "yanchor": "top",
        "xanchor": "left",
        "currentvalue": {
            "font": {"size": 16, "color": "#ffffff"},
            "prefix": "Fecha de Inferencia: ",
            "visible": True,
            "xanchor": "right"
        },
        "transition": {"duration": 100, "easing": "cubic-in-out"},
        "pad": {"b": 10, "t": 50},
        "len": 0.9,
        "x": 0.1,
        "y": 0,
        "steps": []
    }
    
    for t_idx in range(window_length):
        date_str = dates_window[t_idx].strftime('%Y-%m-%d')
        status_suffix = " (CRISIS / CONTRACCIÓN RED)" if (250 <= (start_t + t_idx) <= 300) else " (ESTABLE)"
        slider_step = {
            "args": [
                [date_str],
                {"frame": {"duration": 100, "redraw": True},
                 "mode": "immediate",
                 "transition": {"duration": 100}}
            ],
            "label": date_str + status_suffix,
            "method": "animate"
        }
        sliders_mst["steps"].append(slider_step)
        
    fig_mst.update_layout(
        title={
            'text': "Redes Complejas Dinámicas 3D (Minimum Spanning Tree - Kruskal)",
            'y':0.95, 'x':0.5, 'xanchor': 'center', 'yanchor': 'top',
            'font': {'size': 20, 'color': '#ffffff'}
        },
        scene=dict(
            xaxis=dict(title=dict(text='Dimensión 1', font=dict(color='#ffffff')), backgroundcolor="rgb(15, 15, 25)", gridcolor="rgba(100,100,100,0.15)", showbackground=True, tickfont=dict(color='#aaaaaa'), range=[-1.8, 1.8]),
            yaxis=dict(title=dict(text='Dimensión 2', font=dict(color='#ffffff')), backgroundcolor="rgb(15, 15, 25)", gridcolor="rgba(100,100,100,0.15)", showbackground=True, tickfont=dict(color='#aaaaaa'), range=[-1.8, 1.8]),
            zaxis=dict(title=dict(text='Dimensión 3', font=dict(color='#ffffff')), backgroundcolor="rgb(15, 15, 25)", gridcolor="rgba(100,100,100,0.15)", showbackground=True, tickfont=dict(color='#aaaaaa'), range=[-1.8, 1.8])
        ),
        paper_bgcolor='rgb(10, 10, 18)',
        plot_bgcolor='rgb(10, 10, 18)',
        legend=dict(font=dict(color='#ffffff'), bgcolor='rgba(20,20,30,0.5)', bordercolor='rgba(255,255,255,0.1)', borderwidth=1),
        updatemenus=[{
            "buttons": [
                {
                    "args": [None, {"frame": {"duration": 100, "redraw": True}, "fromcurrent": True, "transition": {"duration": 100, "easing": "quadratic-in-out"}}],
                    "label": "▶ Play",
                    "method": "animate"
                },
                {
                    "args": [[None], {"frame": {"duration": 0, "redraw": True}, "mode": "immediate", "transition": {"duration": 0}}],
                    "label": " Pause",
                    "method": "animate"
                }
            ],
            "direction": "left",
            "pad": {"r": 10, "t": 87},
            "showactive": False,
            "type": "buttons",
            "x": 0.1,
            "xanchor": "right",
            "y": 0,
            "yanchor": "top",
            "font": {"color": "#ffffff"}
        }],
        sliders=[sliders_mst],
        margin=dict(l=10, r=10, t=50, b=10)
    )
    fig_mst.write_html("mst_graph_3d.html", include_plotlyjs="cdn")
    
    logger.info("¡Las tres visualizaciones interactivas en HTML han sido creadas exitosamente!")
    
    # ==========================================
    # 4. CALCULAR EL ESTADO ACTUAL DEL MERCADO (INFERENCIA FINAL)
    # ==========================================
    logger.info("4. Calculando el estado actual del mercado (inferencia final)...")
    from MetaClassifier import MetaClassifier
    import json
    
    spx_returns = data.iloc[:, 0].values
    spx_prices = 100.0 * np.exp(np.cumsum(spx_returns))
    y = compute_drawdown_target(spx_prices, H=63, threshold=0.08)
    
    t_engine = TopologyEngine(H_t, R_t, v_engine.assets, v_engine.dates)
    X_features = t_engine.extract_features(k=3, stable_window=150)
    
    clf = MetaClassifier(n_groups=6, n_test_groups=2, purge_window=63, embargo_window=21)
    clf.fit_final_model(X_features, y, spx_returns)
    probs, xi = clf.predict_proba(X_features, spx_returns)
    
    # 4.1. Calcular los pares de correlación extremos (Top 5 más altos y Top 5 más bajos)
    N = len(v_engine.assets)
    R_final = R_t[-1]
    pairs = []
    for i in range(N):
        for j in range(i + 1, N):
            pairs.append({
                "asset_a": v_engine.assets[i],
                "asset_b": v_engine.assets[j],
                "corr": float(R_final[i, j])
            })
            
    # Ordenar por correlación descendente para obtener los más altos
    pairs_sorted_desc = sorted(pairs, key=lambda x: x["corr"], reverse=True)
    top_highest = pairs_sorted_desc[:5]
    
    # Ordenar por correlación ascendente para obtener los más bajos/negativos
    pairs_sorted_asc = sorted(pairs, key=lambda x: x["corr"])
    top_lowest = pairs_sorted_asc[:5]
    
    # 4.2. Generar el Heatmap interactivo 2D de la correlación del último día
    fig_heatmap = go.Figure(data=go.Heatmap(
        z=R_final,
        x=v_engine.assets,
        y=v_engine.assets,
        colorscale='RdBu',
        zmin=-1.0,
        zmax=1.0,
        colorbar=dict(
            title=dict(text='Correlación', font=dict(color='#ffffff')),
            tickfont=dict(color='#ffffff')
        ),
        hoverongaps=False,
        hovertemplate='Activo A: %{x}<br>Activo B: %{y}<br>Correlación: %{z:.4f}<extra></extra>'
    ))
    
    fig_heatmap.update_layout(
        title={
            'text': f"Matriz de Correlación Condicional del Mercado ({data.index[-1].strftime('%Y-%m-%d')})",
            'y': 0.95, 'x': 0.5, 'xanchor': 'center', 'yanchor': 'top',
            'font': {'size': 18, 'color': '#ffffff'}
        },
        xaxis=dict(
            tickfont=dict(color='#ffffff', size=9),
            showgrid=False
        ),
        yaxis=dict(
            tickfont=dict(color='#ffffff', size=9),
            showgrid=False,
            autorange='reversed'
        ),
        paper_bgcolor='rgb(10, 10, 18)',
        plot_bgcolor='rgb(10, 10, 18)',
        margin=dict(l=50, r=10, t=60, b=50),
        width=700,
        height=650
    )
    
    fig_heatmap.write_html("market_correlation_today.html", include_plotlyjs="cdn")
    logger.info("¡market_correlation_today.html generado!")
    
    latest_status = {
        "date": data.index[-1].strftime('%Y-%m-%d'),
        "prob": float(probs[-1]),
        "xi": float(xi[-1]),
        "lambda_dominant": float(X_features["lambda_dominant"].values[-1]),
        "entropy_spectral": float(X_features["entropy_spectral"].values[-1]),
        "mtl": float(X_features["mtl"].values[-1]),
        "kld": float(X_features["kld"].values[-1]),
        "top_highest_corr": top_highest,
        "top_lowest_corr": top_lowest
    }
    
    # Escribir market_status.json
    with open("market_status.json", "w") as f:
        json.dump(latest_status, f, indent=4)
    logger.info("¡market_status.json generado!")
        
    # Inyectar el estado en dashboard.html
    if os.path.exists("dashboard.html"):
        with open("dashboard.html", "r", encoding="utf-8") as f:
            html_content = f.read()
            
        start_idx = html_content.find("const latestMarketStatus =")
        if start_idx != -1:
            end_idx = html_content.find("};", start_idx)
            if end_idx != -1:
                old_code = html_content[start_idx:end_idx+2]
                new_code = f"const latestMarketStatus = {json.dumps(latest_status, indent=12)};"
                html_content = html_content.replace(old_code, new_code)
                
                with open("dashboard.html", "w", encoding="utf-8") as f:
                    f.write(html_content)
                logger.info("¡Estado del mercado inyectado con éxito en dashboard.html!")

if __name__ == "__main__":
    main()

