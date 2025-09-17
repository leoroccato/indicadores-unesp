# app.py
# Dashboard UNESP – Ingressantes & Formandos
# Foco: simplicidade, baixo acoplamento e tolerância a variações de dados
# Requisitos: streamlit, pandas, altair

import streamlit as st
import pandas as pd
import altair as alt
from pathlib import Path

st.set_page_config(page_title="UNESP – Ingressantes & Formandos", layout="wide")

# ========== Config ==========
DATA_DIR = Path(".")
# Alvos padrão (tente primeiro)
INGRESSANTES_CSV = DATA_DIR / "base.csv"
PLANILHA_XLSX     = DATA_DIR / "base.xlsx"     # caso tenha virado Excel com múltiplas abas
FORMANDOS_CSV     = DATA_DIR / "formandos.csv" # fallback se enviarem formandos num CSV separado
FORMANDOS_SHEET   = "Formandos"                # nome esperado da segunda aba

# ========== Util: normalização de colunas ==========
def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    # mapa flexível de nomes -> canônicos
    mapping_candidates = {
        "ano":        ["ano", "year", "período", "periodo"],
        "curso":      ["curso", "course", "graduação", "graduacao", "programa"],
        "sexo":       ["sexo", "gender", "gênero", "genero"],
        "quantidade": ["quantidade", "qtd", "qtde", "count", "alunos", "numero", "n", "qte"]
    }

    cols = {c.lower().strip(): c for c in df.columns}
    canon = {}
    for target, candidates in mapping_candidates.items():
        for c in candidates:
            if c in cols:
                canon[target] = cols[c]
                break

    # aplica renome se existir
    rename_map = {}
    for target, found in canon.items():
        rename_map[found] = target
    if rename_map:
        df = df.rename(columns=rename_map)

    # garante existência das canônicas se possível inferir
    # (não cria dados; apenas mantém o que foi mapeado)
    return df

# ========== Carregamento robusto ==========
@st.cache_data(show_spinner=True)
def load_data():
    ingressantes = None
    formandos = None
    messages = []

    # 1) Tenta Excel com abas
    if PLANILHA_XLSX.exists():
        try:
            xls = pd.ExcelFile(PLANILHA_XLSX)
            # Heurística: primeira aba = ingressantes; segunda = formandos (ou busca por nome)
            sheet_names = [s.lower() for s in xls.sheet_names]
            # tenta achar por nome
            ing_sheet = next((s for s in xls.sheet_names if "ingress" in s.lower()), xls.sheet_names[0])
            frm_sheet = next((s for s in xls.sheet_names if "formand" in s.lower() or s.lower()==FORMANDOS_SHEET.lower()),
                             (xls.sheet_names[1] if len(xls.sheet_names) > 1 else None))

            ingressantes = pd.read_excel(PLANILHA_XLSX, sheet_name=ing_sheet)
            messages.append(f"Carregado de {PLANILHA_XLSX.name} (aba '{ing_sheet}').")

            if frm_sheet is not None:
                formandos = pd.read_excel(PLANILHA_XLSX, sheet_name=frm_sheet)
                messages.append(f"Formandos carregado de {PLANILHA_XLSX.name} (aba '{frm_sheet}').")
        except Exception as e:
            messages.append(f"Falha ao ler {PLANILHA_XLSX.name}: {e}")

    # 2) Fallback CSV para ingressantes
    if ingressantes is None and INGRESSANTES_CSV.exists():
        try:
            ingressantes = pd.read_csv(INGRESSANTES_CSV)
            messages.append(f"Carregado de {INGRESSANTES_CSV.name}.")
        except Exception as e:
            messages.append(f"Falha ao ler {INGRESSANTES_CSV.name}: {e}")

    # 3) Fallback CSV separado para formandos
    if formandos is None and FORMANDOS_CSV.exists():
        try:
            formandos = pd.read_csv(FORMANDOS_CSV)
            messages.append(f"Formandos carregado de {FORMANDOS_CSV.name}.")
        except Exception as e:
            messages.append(f"Falha ao ler {FORMANDOS_CSV.name}: {e}")

    # Normaliza nomes de colunas se carregou algo
    if ingressantes is not None:
        ingressantes = _normalize_columns(ingressantes)
    if formandos is not None:
        formandos = _normalize_columns(formandos)

    return ingressantes, formandos, messages

ingressantes, formandos, load_msgs = load_data()

with st.expander("🧾 Log de carregamento", expanded=False):
    if not load_msgs:
        st.write("Nenhuma mensagem de carregamento.")
    else:
        for m in load_msgs:
            st.write("•", m)

if ingressantes is None and formandos is None:
    st.warning("Não encontrei dados. Certifique-se de que 'base.xlsx' (com abas) ou 'base.csv' e/ou 'formandos.csv' estão na pasta.")
    st.stop()

# ========== Barra lateral (filtros compartilhados) ==========
st.sidebar.header("Filtros")
# Detecta listas a partir de ambos os datasets
def collect_unique(df, col):
    return sorted(df[col].dropna().unique().tolist()) if df is not None and col in df.columns else []

anos = sorted(set(collect_unique(ingressantes, "ano")) | set(collect_unique(formandos, "ano")))
cursos = sorted(set(collect_unique(ingressantes, "curso")) | set(collect_unique(formandos, "curso")))
sexos = sorted(set(collect_unique(ingressantes, "sexo")) | set(collect_unique(formandos, "sexo")))

sel_anos  = st.sidebar.multiselect("Ano", anos, default=anos or None)
sel_curso = st.sidebar.multiselect("Curso", cursos, default=None)
sel_sexo  = st.sidebar.multiselect("Sexo", sexos, default=None)

def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    if df is None:
        return df
    f = df.copy()
    if "ano" in f.columns and sel_anos:
        f = f[f["ano"].isin(sel_anos)]
    if "curso" in f.columns and sel_curso:
        f = f[f["curso"].isin(sel_curso)]
    if "sexo" in f.columns and sel_sexo:
        f = f[f["sexo"].isin(sel_sexo)]
    return f

# ========== Abas ==========
aba_ing, aba_frm = st.tabs(["📈 Ingressantes", "🎓 Formandos"])

# --------- Ingressantes ---------
with aba_ing:
    st.subheader("Ingressantes")
    if ingressantes is None:
        st.info("Sem dados de ingressantes.")
    else:
        df = apply_filters(ingressantes)
        # tenta achar coluna de medida
        medida_col = "quantidade" if "quantidade" in df.columns else None
        if medida_col is None:
            # se não houver quantidade, assume 1 por linha
            df["_count"] = 1
            medida_col = "_count"

        # KPIs
        total = int(df[medida_col].sum())
        n_cursos = df["curso"].nunique() if "curso" in df.columns else 0
        n_anos = df["ano"].nunique() if "ano" in df.columns else 0

        c1, c2, c3 = st.columns(3)
        c1.metric("Total de ingressantes", f"{total:,}".replace(",", "."))
        c2.metric("Cursos", n_cursos)
        c3.metric("Anos", n_anos)

        # Gráficos padrão
        if "ano" in df.columns:
            by_year = df.groupby("ano", as_index=False)[medida_col].sum()
            chart = alt.Chart(by_year).mark_bar().encode(
                x=alt.X("ano:O", title="Ano", sort="ascending"),
                y=alt.Y(f"{medida_col}:Q", title="Ingressantes"),
                tooltip=["ano", alt.Tooltip(medida_col, title="Ingressantes")]
            ).properties(height=300)
            st.altair_chart(chart, use_container_width=True)

        if "curso" in df.columns:
            topn = df.groupby("curso", as_index=False)[medida_col].sum().sort_values(medida_col, ascending=False).head(20)
            chart = alt.Chart(topn).mark_bar().encode(
                x=alt.X(f"{medida_col}:Q", title="Ingressantes"),
                y=alt.Y("curso:N", sort="-x", title="Curso"),
                tooltip=["curso", alt.Tooltip(medida_col, title="Ingressantes")]
            ).properties(height=500)
            st.altair_chart(chart, use_container_width=True)

        if "sexo" in df.columns:
            by_sex = df.groupby("sexo", as_index=False)[medida_col].sum()
            chart = alt.Chart(by_sex).mark_arc(innerRadius=40).encode(
                theta=alt.Theta(f"{medida_col}:Q"),
                color=alt.Color("sexo:N", legend=alt.Legend(title="Sexo")),
                tooltip=["sexo", alt.Tooltip(medida_col, title="Ingressantes")]
            ).properties(height=300)
            st.altair_chart(chart, use_container_width=True)

        st.dataframe(df, use_container_width=True)

# --------- Formandos ---------
with aba_frm:
    st.subheader("Formandos")
    if formandos is None:
        st.info("Sem dados de formandos. Certifique-se de ter a aba/arquivo com estes dados (ex.: 'Formandos' em base.xlsx ou formandos.csv).")
    else:
        df = apply_filters(formandos)
        medida_col = "quantidade" if "quantidade" in df.columns else None
        if medida_col is None:
            df["_count"] = 1
            medida_col = "_count"

        total = int(df[medida_col].sum())
        n_cursos = df["curso"].nunique() if "curso" in df.columns else 0
        n_anos = df["ano"].nunique() if "ano" in df.columns else 0

        c1, c2, c3 = st.columns(3)
        c1.metric("Total de formandos", f"{total:,}".replace(",", "."))
        c2.metric("Cursos", n_cursos)
        c3.metric("Anos", n_anos)

        if "ano" in df.columns:
            by_year = df.groupby("ano", as_index=False)[medida_col].sum()
            chart = alt.Chart(by_year).mark_bar().encode(
                x=alt.X("ano:O", title="Ano", sort="ascending"),
                y=alt.Y(f"{medida_col}:Q", title="Formandos"),
                tooltip=["ano", alt.Tooltip(medida_col, title="Formandos")]
            ).properties(height=300)
            st.altair_chart(chart, use_container_width=True)

        if "curso" in df.columns:
            topn = df.groupby("curso", as_index=False)[medida_col].sum().sort_values(medida_col, ascending=False).head(20)
            chart = alt.Chart(topn).mark_bar().encode(
                x=alt.X(f"{medida_col}:Q", title="Formandos"),
                y=alt.Y("curso:N", sort="-x", title="Curso"),
                tooltip=["curso", alt.Tooltip(medida_col, title="Formandos")]
            ).properties(height=500)
            st.altair_chart(chart, use_container_width=True)

        if "sexo" in df.columns:
            by_sex = df.groupby("sexo", as_index=False)[medida_col].sum()
            chart = alt.Chart(by_sex).mark_arc(innerRadius=40).encode(
                theta=alt.Theta(f"{medida_col}:Q"),
                color=alt.Color("sexo:N", legend=alt.Legend(title="Sexo")),
                tooltip=["sexo", alt.Tooltip(medida_col, title="Formandos")]
            ).properties(height=300)
            st.altair_chart(chart, use_container_width=True)

        st.dataframe(df, use_container_width=True)

# ========== Comparativo (opcional, leve) ==========
st.markdown("---")
st.subheader("📊 Comparativo rápido (Ingressantes vs Formandos por Ano)")
if ingressantes is not None and formandos is not None and "ano" in ingressantes.columns and "ano" in formandos.columns:
    mi = "quantidade" if "quantidade" in ingressantes.columns else None
    mf = "quantidade" if "quantidade" in formandos.columns else None

    gi = ingressantes.copy()
    gf = formandos.copy()
    if mi is None:
        gi["_count"] = 1
        mi = "_count"
    if mf is None:
        gf["_count"] = 1
        mf = "_count"

    gi = gi.groupby("ano", as_index=False)[mi].sum().rename(columns={mi: "Ingressantes"})
    gf = gf.groupby("ano", as_index=False)[mf].sum().rename(columns={mf: "Formandos"})
    comp = pd.merge(gi, gf, on="ano", how="outer").fillna(0)
    st.dataframe(comp.sort_values("ano"), use_container_width=True)

    # gráfico de linhas
    comp_melt = comp.melt(id_vars="ano", var_name="Grupo", value_name="Quantidade")
    line = alt.Chart(comp_melt).mark_line(point=True).encode(
        x=alt.X("ano:O", title="Ano", sort="ascending"),
        y=alt.Y("Quantidade:Q"),
        color="Grupo:N",
        tooltip=["ano", "Grupo", "Quantidade"]
    ).properties(height=350)
    st.altair_chart(line, use_container_width=True)
else:
    st.info("Para o comparativo, preciso de Ano em ambos os datasets.")
