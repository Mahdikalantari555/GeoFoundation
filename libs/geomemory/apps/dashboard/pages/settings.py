"""Settings page — model config, index management, collections, and workspace doctor."""
from __future__ import annotations

import streamlit as st

from geomemory import GeoMemory


def render(ws: GeoMemory) -> None:
    st.header("⚙️ Settings")

    tab_config, tab_index, tab_collections, tab_doctor = st.tabs(
        ["Configuration", "Index", "Collections", "Doctor"]
    )

    with tab_config:
        st.subheader("Backend configuration")
        with st.form("update_settings"):
            model_path = st.text_input(
                "LLM model path (GGUF)",
                value=ws.settings.model_path or "",
                help="Path to a llama.cpp GGUF instruct model, e.g. models/qwen-7b.gguf",
            )
            embedding_path = st.text_input(
                "Embedding model path (GGUF)",
                value=ws.settings.embedding_path or "",
                help="Path to an embedding GGUF, e.g. models/nomic-embed-text.gguf",
            )
            vision_path = st.text_input(
                "Vision model path (GGUF, optional)",
                value=ws.settings.vision_path or "",
            )
            submitted = st.form_submit_button("Save settings")
        if submitted:
            try:
                ws.update_settings(
                    model_path=model_path or None,
                    embedding_path=embedding_path or None,
                    vision_path=vision_path or None,
                )
                st.success("Settings saved.")
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.error(f"Save failed: {exc}")

        st.subheader("Current settings")
        st.json(ws.settings.model_dump(mode="json"))

    with tab_index:
        st.subheader("Dense index")
        st.caption("Builds/persists the retrieval index over all segments. Repeat builds are incremental.")
        space_id = st.text_input("Space id", "text.nomic.v1")
        c1, c2 = st.columns(2)
        if c1.button("Build index", type="primary"):
            with st.spinner("Building index…"):
                try:
                    ws.build_index(space_id)
                    st.success("Index built.")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Build failed: {exc}")
        if c2.button("Rebuild index"):
            with st.spinner("Rebuilding index…"):
                try:
                    ws.rebuild_index(space_id)
                    st.success("Index rebuilt.")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Rebuild failed: {exc}")

        st.subheader("Image index")
        st.caption("Builds/persists an image-only index using the configured vision model.")
        img_space = st.text_input("Image space id", "image.v1")
        if st.button("Build image index"):
            with st.spinner("Building image index…"):
                try:
                    ws.image_index(img_space)
                    st.success("Image index built.")
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Image build failed: {exc}")

    with tab_collections:
        st.subheader("Create collection")
        with st.form("create_collection"):
            name = st.text_input("Collection name")
            description = st.text_area("Description", "")
            created = st.form_submit_button("Create")
        if created:
            if not name.strip():
                st.warning("Name is required.")
            else:
                try:
                    coll = ws.create_collection(name, description)
                    st.success(f"Created collection `{coll.name}`.")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Create failed: {exc}")

        st.subheader("Existing collections")
        try:
            collections = ws.list_collections()
        except Exception as exc:  # noqa: BLE001
            st.error(f"List failed: {exc}")
            collections = []
        if not collections:
            st.info("No collections yet.")
        for coll in collections:
            with st.container(border=True):
                st.write(f"**{coll.name}** — `{coll.id}`")
                st.caption(coll.description or "No description")

    with tab_doctor:
        st.subheader("Workspace diagnostics")
        try:
            from geomemory.services.doctor import doctor_workspace_open
            report = doctor_workspace_open(ws.path)
            st.json(report)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Doctor failed: {exc}")
