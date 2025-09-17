# app.py
# Streamlit Dashboard – UNESP (Ingresso & Formandos)
# Foco em robustez: leitura flexível de XLSX, mapeamento automático de colunas,
# e interface simples para decisões rápidas. Autor: você ;)

import unicodedata
import pandas as pd
import numpy as np
import altair as alt
import streamlit as st
from functools import lru_cache
from pathlib import Path

st.set_page_config(page_title="UNESP – Ingressantes & Formandos", layout="wide")

# ========= Utils =========

def _strip_accents(text: str) -> str:
    if not isinstance(text, str):
        return text
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [
        _strip_accents(c).strip().lower().replace("\n", " ").replace("\r", " ")
        for c in df.columns
    ]
    return df

def find_first_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    cols = list(df.columns)
    for cand in candidates:
        # busca exata
        if cand in df.columns:
            return cand
    # busca por "contém"
    for cand in candidates:
        for c in cols:
            if cand in c:
                return c
    return None

def friendly_missing(*cols):
    return " | ".join(cols)

@lru_cache
def load_excel(path: str | Path, sheet: str | int | None = None) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=sheet)
    return df

def safe_number(x):
    try:
        return pd.to_numeric(x)
    except Exception:
        return pd.NA

# ========= Data Load =========

BASE_XLSX = Path("Application/Python/pdfExtractor/saida/base.xlsx")
FORM_XLSX = Path("Application/Python/pdfExtractor/saida/formandos.xlsx")

@st.cache_data(show_spinner=True)
def load_ingresso() -> pd.DataFrame | None:
    if not BASE_XLSX.exists():
        st.warning(f"Arquivo não encontrado: {BASE_XLSX.resolve()}")
        return None
    df = load_excel(str(BASE_XLSX))
    return normalize_columns(df)

@st.cache_data(show_spinner=True)
def load_formandos() -> pd.DataFrame | None:
    if not FORM_XLSX.exists():
        st.warning(f"Arquivo não encontrado: {FORM_XLSX.resolve()}")
        return None
    df = load_excel(str(FORM_XLSX))
    return normalize_columns(df)

df_ing = load_ingresso()
df_for = load_formandos()

st.title("📊 UNESP – Ingressantes & Formandos")
st.caption("Dashboard do TCC – indicadores de ingresso (vestibular) e formandos por curso/ano.")

# ========= Column Mapping Heuristics =========

def map_ingresso_columns(df: pd.DataFrame):
    if df is None:
        return None
    curso_col = find_first_col(df, ["curso", "nome do curso", "curso_nome"])
    ano_col   = find_first_col(df, ["ano", "ano_ingresso", "ano_letivo", "periodo"])
    sexo_col  = find_first_col(df, ["sexo", "genero"])
    count_col = find_first_col(df, ["quantidade", "qtd", "ingressantes", "matriculas", "matriculados"])

    return {
        "curso": curso_col,
        "ano": ano_col,
        "sexo": sexo_col,
        "valor": count_col
    }

def map_formandos_columns(df: pd.DataFrame):
    if df is None:
        return None
    curso_col = find_first_col(df, ["curso", "nome do curso", "curso_nome"])
    ano_col   = find_first_col(df, ["ano", "ano_formatura", "ano_conclusao"])
    valor_col = find_first_col(df, ["formandos", "concluintes", "quantidade", "qtd"])

    return {
        "curso": curso_col,
        "ano": ano_col,
        "valor": valor_col
    }

map_ing = map_ingresso_columns(df_ing)
map_for = map_formandos_columns(df_for)

with st.expander("🔎 Ver mapeamento automático de colunas"):
    st.write("Ingresso:", map_ing)
    st.write("Formandos:", map_for)
    st.info("Se algum campo estiver **None**, confira os nomes das colunas na planilha.")

# ========= Sidebar Filters =========

st.sidebar.header("Filtros")
if df_ing is not None and map_ing["ano"] is not None:
    anos_ing = sorted([a for a in df_ing[map_ing["ano"]].dropna().unique()])
else:
    anos_ing = []

if df_for is not None and map_for["ano"] is not None:
    anos_for = sorted([a for a in df_for[map_for["ano"]].dropna().unique()])
else:
    anos_for = []

anos_all = sorted(set(anos_ing) | set(anos_for))
ano_sel = st.sidebar.multiselect("Ano", anos_all, default=anos_all)
curso_sel = []

# ========= Tabs =========

tab1, tab2, tab3 = st.tabs(["📥 Ingresso (Vestibular)", "🎓 Formandos", "⚖️ Comparativo"])

# ---------- TAB 1: Ingresso ----------
with tab1:
    st.subheader("Ingresso por Curso/Ano")
    if df_ing is None:
        st.warning("Dados de ingresso não carregados.")
    else:
        curso_col = map_ing["curso"]
        ano_col   = map_ing["ano"]
        sexo_col  = map_ing["sexo"]
        val_col   = map_ing["valor"]

        if curso_col is None or ano_col is None:
            st.error(f"Colunas necessárias ausentes em ingresso: {friendly_missing('curso', 'ano')}")
        else:
            dfi = df_ing.copy()
            # Filtros
            if ano_sel:
                dfi = dfi[dfi[ano_col].isin(ano_sel)]
            if curso_col in dfi.columns:
                cursos = sorted(dfi[curso_col].dropna().unique().tolist())
                curso_sel_local = st.multiselect("Curso", cursos, default=cursos)
                if curso_sel_local:
                    dfi = dfi[dfi[curso_col].isin(curso_sel_local)]

            # Agregação
            if val_col is None:
                dfi["_valor"] = 1
            else:
                dfi["_valor"] = pd.to_numeric(dfi[val_col], errors="coerce")
                if dfi["_valor"].isna().all():
                    dfi["_valor"] = 1

            group_cols = [ano_col, curso_col]
            if sexo_col is not None and sexo_col in dfi.columns:
                add_sexo = st.checkbox("Detalhar por sexo", value=False)
                if add_sexo:
                    group_cols.append(sexo_col)

            resumo = dfi.groupby(group_cols, dropna=False)["_valor"].sum().reset_index()
            st.dataframe(resumo, use_container_width=True)

            # Gráfico séries por ano
            try:
                chart = (
                    alt.Chart(resumo)
                    .mark_line(point=True)
                    .encode(
                        x=alt.X(f"{ano_col}:O", title="Ano"),
                        y=alt.Y("_valor:Q", title="Ingresso"),
                        color=alt.Color(f"{curso_col}:N", title="Curso"),
                        tooltip=group_cols + ["_valor"]
                    )
                    .properties(height=360)
                )
                st.altair_chart(chart, use_container_width=True)
            except Exception as e:
                st.info(f"Gráfico não pôde ser renderizado: {e}")

# ---------- TAB 2: Formandos ----------
with tab2:
    st.subheader("Formandos por Curso/Ano")
    if df_for is None:
        st.warning("Dados de formandos não carregados.")
    else:
        curso_col = map_for["curso"]
        ano_col   = map_for["ano"]
        val_col   = map_for["valor"]

        if curso_col is None or ano_col is None:
            st.error(f"Colunas necessárias ausentes em formandos: {friendly_missing('curso', 'ano')}")
        else:
            dff = df_for.copy()
            # Filtros
            if ano_sel:
                dff = dff[dff[ano_col].isin(ano_sel)]
            if curso_col in dff.columns:
                cursos = sorted(dff[curso_col].dropna().unique().tolist())
                curso_sel_local = st.multiselect("Curso", cursos, default=cursos, key="form_cursos")
                if curso_sel_local:
                    dff = dff[dff[curso_col].isin(curso_sel_local)]

            # Agregação
            if val_col is None:
                dff["_valor"] = 1
            else:
                dff["_valor"] = pd.to_numeric(dff[val_col], errors="coerce")
                if dff["_valor"].isna().all():
                    dff["_valor"] = 1

            resumo = dff.groupby([ano_col, curso_col], dropna=False)["_valor"].sum().reset_index()
            st.dataframe(resumo, use_container_width=True)

            # Gráfico
            try:
                chart = (
                    alt.Chart(resumo)
                    .mark_bar()
                    .encode(
                        x=alt.X(f"{ano_col}:O", title="Ano"),
                        y=alt.Y("_valor:Q", title="Formandos"),
                        color=alt.Color(f"{curso_col}:N", title="Curso"),
                        tooltip=[ano_col, curso_col, "_valor"]
                    )
                    .properties(height=360)
                )
                st.altair_chart(chart, use_container_width=True)
            except Exception as e:
                st.info(f"Gráfico não pôde ser renderizado: {e}")

# ---------- TAB 3: Comparativo ----------
with tab3:
    st.subheader("Ingresso vs. Formandos")
    if df_ing is None or df_for is None:
        st.warning("Para o comparativo, carregue ambos: base.xlsx e formandos.xlsx.")
    else:
        # Mapeamentos
        ci, ai, vi = map_ing["curso"], map_ing["ano"], map_ing["valor"]
        cf, af, vf = map_for["curso"], map_for["ano"], map_for["valor"]
        if None in (ci, ai, cf, af):
            st.error("Comparativo requer colunas de curso e ano em ambos os conjuntos.")
        else:
            a = df_ing.copy()
            b = df_for.copy()

            a["_valor_ing"] = pd.to_numeric(a[vi], errors="coerce") if vi else 1
            if a["_valor_ing"].isna().all():
                a["_valor_ing"] = 1
            a = a.groupby([ai, ci], dropna=False)["_valor_ing"].sum().reset_index()

            b["_valor_for"] = pd.to_numeric(b[vf], errors="coerce") if vf else 1
            if b["_valor_for"].isna().all():
                b["_valor_for"] = 1
            b = b.groupby([af, cf], dropna=False)["_valor_for"].sum().reset_index()

            # Harmonizar tipos (ano pode vir como string/int)
            a[ai] = a[ai].astype(str)
            b[af] = b[af].astype(str)

            comp = a.merge(
                b, left_on=[ai, ci], right_on=[af, cf], how="inner"
            ).rename(columns={
                ai: "ano",
                ci: "curso"
            })[["ano", "curso", "_valor_ing", "_valor_for"]]

            if comp.empty:
                st.info("Não há interseção (curso/ano) entre dados de ingresso e formandos.")
            else:
                comp["saldo (ing - form)"] = comp["_valor_ing"] - comp["_valor_for"]
                st.dataframe(comp.sort_values(["ano", "curso"]), use_container_width=True)

                # Série dupla por curso selecionado
                cursos = sorted(comp["curso"].unique().tolist())
                curso_pick = st.selectbox("Curso para série temporal", cursos)
                comp_c = comp[comp["curso"] == curso_pick].copy()

                try:
                    comp_melt = comp_c.melt(id_vars=["ano", "curso"],
                                            value_vars=["_valor_ing", "_valor_for"],
                                            var_name="tipo", value_name="valor")
                    comp_melt["tipo"] = comp_melt["tipo"].map({
                        "_valor_ing": "Ingresso",
                        "_valor_for": "Formandos"
                    })

                    chart = (
                        alt.Chart(comp_melt)
                        .mark_line(point=True)
                        .encode(
                            x=alt.X("ano:O", title="Ano"),
                            y=alt.Y("valor:Q", title="Quantidade"),
                            color=alt.Color("tipo:N", title="Série"),
                            tooltip=["ano", "tipo", "valor"]
                        )
                        .properties(height=360)
                    )
                    st.altair_chart(chart, use_container_width=True)
                except Exception as e:
                    st.info(f"Não foi possível renderizar a série: {e}")

# ========= Rodapé =========
st.caption(
    "Dica: se algum gráfico não aparecer, verifique os nomes das colunas nas planilhas. "
    "Este app tenta mapear automaticamente, mas headers muito diferentes podem exigir ajuste simples."
)
