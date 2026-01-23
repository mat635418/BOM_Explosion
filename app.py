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

# --- Tabs: Data / Topology ---
tab_data, tab_topology = st.tabs(["Data", "Topology"])

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

        # --- Compact parameters / info above the graph ---
        col_p1, col_p2 = st.columns([1, 1])
        with col_p1:
            st.checkbox(
                "Enable physics layout",
                value=True,
                key="physics_enabled",
                help=(
                    "When enabled, nodes move dynamically to a readable layout. "
                    "Turn off if you want a stable, non-moving diagram."
                ),
            )
        with col_p2:
            st.checkbox(
                "Show raw nodes/edges table",
                value=False,
                key="show_raw_data",
                help="Display the underlying node and edge lists for debugging or export.",
            )

        physics_enabled = bool(st.session_state["physics_enabled"])
        show_raw_data = bool(st.session_state["show_raw_data"])

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

        # --- Build NetworkX graph with node levels ---
        G = nx.DiGraph()

        # We rely on BOM_Explosion keeping 'Level' in edge meta.
        node_level = {}

        for edge in topology.edges:
            meta = edge.get("meta", {})
            level_val = meta.get("Level", None)
            try:
                level_int = int(level_val)
            except Exception:
                level_int = 1
            child = edge["to"]
            if child not in node_level or level_int < node_level[child]:
                node_level[child] = level_int

        # Root nodes might never be "child"; default them to level 1
        for node in topology.nodes:
            if node not in node_level:
                node_level[node] = 1

        for node in topology.nodes:
            lvl = node_level.get(node, 1)
            # store level as a node attribute (used later in JS)
            G.add_node(node, label=node, level=lvl)

        for edge in topology.edges:
            parent = edge["from"]
            child = edge["to"]
            qty = edge.get("quantity", 1)
            G.add_edge(parent, child, quantity=qty, title=f"Qty: {qty}")

        # --- Render with PyVis ---
        net = Network(height="600px", width="100%", directed=True)

        options_json = f"""
        {{
          "layout": {{
            "hierarchical": {{
              "enabled": true,
              "direction": "LR",
              "sortMethod": "hubsize",
              "levelSeparation": 150,
              "nodeSpacing": 150,
              "treeSpacing": 200
            }}
          }},
          "physics": {{
            "enabled": {str(physics_enabled).lower()},
            "hierarchicalRepulsion": {{
              "nodeDistance": 150,
              "centralGravity": 0.0,
              "springLength": 100,
              "springConstant": 0.01,
              "damping": 0.09
            }}
          }}
        }}
        """
        net.set_options(options_json)

        net.from_nx(G)

        # Export nodes / edges data so JS can access levels and parents
        # PyVis already dumps this into the HTML as 'nodes' and 'edges' DataSet.

        html_file = "bom_topology.html"
        net.save_graph(html_file)

        with open(html_file, "r", encoding="utf-8") as f:
            html = f.read()

        # JS:
        #  - Initially hide nodes with level > 5
        #  - On doubleClick on a node, reveal its children at next level
        #  - Resize network to viewport height
        js_script = """
        <script type="text/javascript">
        function resizeNetwork() {
            var net = document.getElementById('mynetwork');
            if (!net) return;
            var offset = 220;  // space for title, tabs, and controls
            var h = window.innerHeight - offset;
            if (h < 400) { h = 400; }
            net.style.height = h + "px";
        }

        function setupLevelVisibility() {
            if (typeof network === 'undefined' || typeof nodes === 'undefined' || typeof edges === 'undefined') {
                return;
            }

            var VISIBLE_MAX_LEVEL = 5;   // show levels 1–5
            var MAX_LEVEL = 15;          // only expand up to this

            // Helper to get node data by id
            function getNode(nid) {
                return nodes.get(nid);
            }

            // Initially hide all nodes with level > VISIBLE_MAX_LEVEL
            nodes.get().forEach(function(n) {
                var lvl = n.level || 1;
                if (lvl > VISIBLE_MAX_LEVEL && lvl <= MAX_LEVEL) {
                    nodes.update({id: n.id, hidden: true});
                }
            });

            // On double-click, expand one more level under the clicked node
            network.on("doubleClick", function(params) {
                if (!params || !params.nodes || params.nodes.length === 0) {
                    return;
                }
                var nid = params.nodes[0];
                var node = getNode(nid);
                if (!node) return;
                var lvl = node.level || 1;
                var targetLevel = lvl + 1;
                if (targetLevel > MAX_LEVEL) {
                    return;
                }

                // Find children edges whose from == nid and whose child node is at targetLevel
                edges.get().forEach(function(e) {
                    if (e.from === nid) {
                        var child = getNode(e.to);
                        if (child && (child.level || 1) === targetLevel) {
                            nodes.update({id: child.id, hidden: false});
                        }
                    }
                });

                // Optional: fit again around the clicked node
                // network.focus(nid, {scale: 1.0, animation: true});
            });
        }

        window.addEventListener('load', function() {
            resizeNetwork();
            setTimeout(setupLevelVisibility, 500);  // wait for vis.js to init
        });
        window.addEventListener('resize', resizeNetwork);
        </script>
        """

        final_html = html.replace("</body>", js_script + "</body>")

        st.subheader("Graph view")
        st.caption(
            "Levels 1–5 are shown. Levels 6–15 start collapsed; "
            "double-click a node to expand its next level of children."
        )

        # Height is a fallback; JS will adjust to viewport
        components.html(final_html, height=700, scrolling=False)

    else:
        st.info("Upload a BOM file to see the topology.")
