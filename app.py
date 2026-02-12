import streamlit as st
import pandas as pd
import networkx as nx
from pyvis.network import Network
import streamlit.components.v1 as components

from BOM_Explosion import BOMExplosionApp

st.set_page_config(page_title="BOM Explosion", layout="wide")

# Reduce top padding / margin so content starts higher on the page
st.markdown(
    """
    <style>
        .block-container {
            padding-top: 1rem !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# Keep a single global app instance
if "bom_app" not in st.session_state:
    st.session_state["bom_app"] = BOMExplosionApp()

app = st.session_state["bom_app"]

st.title("BOM Explosion Tool")

st.markdown(
    """
    Upload a BOM file (single SKU for now) with at least these columns:

    - `Level`
    - `Component number`
    - quantity column like `Comp. Qty (BUn)` (optional, but recommended)
    """
)

# --- Upload box ---
uploaded_file = st.file_uploader(
    "Upload BOM file",
    type=["csv", "xlsx"],
    help="Upload a BOM for one SKU. Supported formats: CSV, Excel.",
)

df = None

if uploaded_file is not None:
    try:
        if uploaded_file.name.lower().endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        app.load_from_dataframe(df)
        st.success("BOM data loaded successfully!")

    except Exception as e:
        st.error(f"Error while reading or parsing the file: {e}")

# --- Tabs: Data / Topology / Tree View ---
tab_data, tab_topology, tab_tree = st.tabs(["Data", "Topology", "Tree view"])

# =========================
# DATA TAB
# =========================
with tab_data:
    st.subheader("Raw BOM data")
    if app.has_data():
        st.dataframe(app.get_dataframe())
    else:
        st.info("Upload a BOM file to view data.")

# =========================
# TOPOLOGY TAB
# =========================
with tab_topology:
    st.subheader("Topology")

    if app.has_topology():
        topology = app.get_topology()

        # Topology summary (best-effort; BOMExplosionApp can expose these)
        with st.expander("Topology summary", expanded=False):
            try:
                summary = {
                    "Nodes": len(topology.nodes),
                    "Edges": len(topology.edges),
                }
                # Optional attributes if you add them in BOMExplosionApp
                if hasattr(topology, "max_level"):
                    summary["Max level"] = topology.max_level
                if hasattr(topology, "avg_branching_factor"):
                    summary["Average children per parent"] = topology.avg_branching_factor
                st.write(summary)
            except Exception:
                st.write("Summary not available.")

        # --- Controls above the graph ---
        col_p1, col_p2, col_p3 = st.columns([1, 1, 1])

        # Physics toggle + layout sliders
        with col_p1:
            physics_enabled = st.checkbox(
                "Enable physics layout",
                value=True,
                key="physics_enabled",
                help=(
                    "When enabled, nodes move dynamically to a readable layout. "
                    "Turn off if you want a stable, non-moving diagram."
                ),
            )
            show_raw_data = st.checkbox(
                "Show raw nodes/edges table",
                value=False,
                key="show_raw_data",
                help="Display the underlying node and edge lists for debugging or export.",
            )

        # Layout / physics parameter sliders
        with col_p2:
            st.markdown("**Layout parameters**")
            level_separation = st.slider(
                "Level separation (LR distance between levels)",
                50,
                400,
                150,
                step=10,
                help="Increase if levels overlap or are too close.",
                key="level_separation",
            )
            node_spacing = st.slider(
                "Node spacing (same-level spacing)",
                50,
                400,
                150,
                step=10,
                help="Increase if siblings overlap.",
                key="node_spacing",
            )
            node_distance = st.slider(
                "Physics node distance",
                50,
                400,
                150,
                step=10,
                help="Distance nodes try to keep from each other.",
                key="node_distance",
            )

        # Root / subtree selection + search / full screen
        with col_p3:
            # Root nodes (if BOMExplosionApp provides them)
            root_nodes = getattr(topology, "root_nodes", None)
            selected_root = None
            if root_nodes:
                selected_root = st.selectbox(
                    "Select finished good / root",
                    root_nodes,
                    help="Focus the visualization on a specific root and its subtree.",
                    key="selected_root",
                )

            search_term = st.text_input(
                "Search node (part / component)",
                "",
                key="search_term",
                help="Highlight nodes whose label contains this text.",
            )

            fullscreen = st.checkbox(
                "Full screen graph",
                value=False,
                key="fullscreen",
                help="Hide most padding to maximize graph space.",
            )

        # Optional raw data
        if show_raw_data:
            with st.expander("Nodes and edges (raw data)", expanded=False):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Nodes (all unique parts)**")
                    st.write(topology.nodes)
                with col2:
                    st.markdown("**Edges (Parent → Child relationships)**")
                    st.write(topology.edges)

        # --- Build NetworkX graph (with subtree focusing) ---
        G = nx.DiGraph()

        # Support subtree view if BOMExplosionApp exposes get_subtree(root)
        if selected_root and hasattr(topology, "get_subtree"):
            try:
                sub_nodes, sub_edges = topology.get_subtree(selected_root)
                nodes_iter = sub_nodes
                edges_iter = sub_edges
            except Exception:
                # Fallback to full topology if something goes wrong
                nodes_iter = topology.nodes
                edges_iter = topology.edges
        else:
            nodes_iter = topology.nodes
            edges_iter = topology.edges

        # Example: optional metadata dict on topology (add in BOMExplosionApp)
        # topology.node_data: dict[node] = {"level": int, "total_quantity": float, "type": str, ...}
        node_data = getattr(topology, "node_data", {})

        # Node styling: color by level, size by total quantity, highlight search
        level_colors = [
            "#1f77b4",
            "#ff7f0e",
            "#2ca02c",
            "#d62728",
            "#9467bd",
            "#8c564b",
            "#e377c2",
            "#7f7f7f",
            "#bcbd22",
            "#17becf",
        ]

        for node in nodes_iter:
            data = node_data.get(node, {})
            level = data.get("level", 0)
            total_qty = data.get("total_quantity", 1)
            node_type = data.get("type", "")

            # Base color from level
            color = level_colors[level % len(level_colors)]

            # Search highlight
            highlight = bool(search_term and search_term.lower() in str(node).lower())
            if highlight:
                color = "#ff0000"  # red highlight

            # Node size from total quantity (clamped)
            try:
                qty_val = float(total_qty)
            except Exception:
                qty_val = 1.0
            size = min(60, max(10, qty_val * 2))

            title_parts = [f"{node}"]
            title_parts.append(f"Level: {level}")
            title_parts.append(f"Total qty: {total_qty}")
            if node_type:
                title_parts.append(f"Type: {node_type}")

            G.add_node(
                node,
                label=str(node),
                color=color,
                size=size,
                title="<br>".join(title_parts),
            )

        # Edge styling: thickness and color by quantity
        for edge in edges_iter:
            parent = edge["from"]
            child = edge["to"]
            qty = edge.get("quantity", 1)

            try:
                qty_val = float(qty)
            except Exception:
                qty_val = 1.0

            width = min(10, max(1, qty_val))  # 1–10 px
            color = "#2ca02c" if qty_val > 1 else "#999999"

            G.add_edge(
                parent,
                child,
                quantity=qty,
                title=f"Qty: {qty}",
                width=width,
                color=color,
            )

        # --- Render with PyVis ---
        # Initial height is a placeholder; JS/CSS will stretch to viewport height.
        net = Network(height="600px", width="100%", directed=True)

        # Inject physics_enabled and sliders into valid JSON options
        options_json = f"""
        {{
          "layout": {{
            "hierarchical": {{
              "enabled": true,
              "direction": "LR",
              "sortMethod": "hubsize",
              "levelSeparation": {level_separation},
              "nodeSpacing": {node_spacing},
              "treeSpacing": 200
            }}
          }},
          "physics": {{
            "enabled": {str(physics_enabled).lower()},
            "hierarchicalRepulsion": {{
              "nodeDistance": {node_distance},
              "centralGravity": 0.0,
              "springLength": 100,
              "springConstant": 0.02,
              "damping": 0.09
            }}
          }}
        }}
        """
        net.set_options(options_json)

        net.from_nx(G)

        html_file = "bom_topology.html"
        net.save_graph(html_file)

        with open(html_file, "r", encoding="utf-8") as f:
            html = f.read()

        # CSS + JS to make the network take (almost) the full viewport height.
        # The Streamlit iframe will be very tall; network container will be resized inside.
        offset = 140 if fullscreen else 220  # smaller offset in fullscreen mode

        resize_script = f"""
        <style>
          html, body {{
            height: 100%;
            margin: 0;
            padding: 0;
          }}
          #mynetwork {{
            height: 100vh !important;
          }}
        </style>
        <script type="text/javascript">
        function resizeNetwork() {{
            var net = document.getElementById('mynetwork');
            if (!net) return;
            var offset = {offset};
            var h = window.innerHeight - offset;
            if (h < 600) {{ h = 600; }}
            net.style.height = h + "px";
        }}
        window.addEventListener('load', resizeNetwork);
        window.addEventListener('resize', resizeNetwork);
        </script>
        """

        final_html = html.replace("</body>", resize_script + "</body>")

        # Optional extra CSS to reduce padding in "fullscreen" mode
        if fullscreen:
            st.markdown(
                """
                <style>
                header, footer {
                    visibility: hidden;
                    height: 0;
                }
                .block-container {
                    padding-top: 0rem !important;
                    padding-bottom: 0rem !important;
                }
                </style>
                """,
                unsafe_allow_html=True,
            )

        st.subheader("Graph view")

        # Height is a large fallback; inner JS will adapt to viewport.
        components.html(final_html, height=1600, scrolling=False)

    else:
        st.info("Upload a BOM file to see the topology.")

# =========================
# TREE VIEW TAB (alternative to graph)
# =========================
with tab_tree:
    st.subheader("Indented tree view")

    if app.has_data():
        df_view = app.get_dataframe().copy()

        # Best-effort tree indentation: if there's a 'Level' column, indent the component number
        level_col_candidates = [c for c in df_view.columns if c.lower() == "level"]
        comp_col_candidates = [
            c for c in df_view.columns if "component" in c.lower() and "number" in c.lower()
        ]

        if level_col_candidates and comp_col_candidates:
            level_col = level_col_candidates[0]
            comp_col = comp_col_candidates[0]

            try:
                df_view["__indent_label"] = df_view.apply(
                    lambda row: " " * int(row[level_col]) * 4 + str(row[comp_col]),
                    axis=1,
                )

                display_cols = ["__indent_label"] + [
                    c for c in df_view.columns if c not in ["__indent_label"]
                ]

                st.dataframe(df_view[display_cols].rename(columns={"__indent_label": "Component (indented)"}))
            except Exception as e:
                st.warning(f"Could not build indented tree view: {e}")
                st.dataframe(df_view)
        else:
            st.info(
                "To show an indented tree view, ensure your data has 'Level' and 'Component number' columns."
            )
            st.dataframe(df_view)
    else:
        st.info("Upload a BOM file to view the tree.")
