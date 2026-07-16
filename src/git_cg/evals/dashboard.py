import json
import os

import streamlit as st


@st.cache_data(max_entries=1)
def load_data():
    """
    Loads the full benchmark payload from disk.
    Cached with max_entries=1 to prevent RAM exhaustion.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    full_path = os.path.join(base_dir, "results", "benchmark_full.json")

    if not os.path.exists(full_path):
        return []

    with open(full_path) as f:
        return json.load(f)


def render_dashboard():
    st.set_page_config(page_title="git-cg Evaluation Dashboard", layout="wide")
    st.title("git-cg Deep Evaluation & Benchmark Dashboard")

    with st.spinner("Loading massive JSON dataset..."):
        data = load_data()

    if not data:
        st.warning("No benchmark history found. Please run `git-cg evals --run` first.")
        return

    st.subheader("Benchmark History")

    # Very simple tabular view for now, using Streamlit's dataframe
    # We could use Polars for faster loading if the dataset is > gigabyte
    import pandas as pd

    df = pd.json_normalize(data)

    # Drop raw text columns from the main summary table for rendering performance
    summary_cols = [c for c in df.columns if "raw_outputs" not in c]
    st.dataframe(df[summary_cols], use_container_width=True)

    st.divider()

    st.subheader("Deep Dive: Raw Text Outputs")
    selected_run = st.selectbox("Select a Run ID (timestamp)", df["timestamp"].tolist())

    if selected_run:
        run_data = next((d for d in data if d["timestamp"] == selected_run), None)
        if run_data and "raw_outputs" in run_data:
            for item in run_data["raw_outputs"]:
                with st.expander(f"Prompt: {item.get('prompt', 'Unknown')[:50]}..."):
                    if item.get("thinking_trace"):
                        st.markdown("**Thinking Trace:**")
                        st.code(item.get("thinking_trace"))
                    st.markdown("**Output:**")
                    st.markdown(item.get("output"))


if __name__ == "__main__":
    render_dashboard()
