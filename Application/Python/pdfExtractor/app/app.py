# app.py
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# =============================
# CONFIG
# =============================
st.set_page_config(page_title="TCC UNESP Bauru", layout="wide")
alt.data_transformers.disable_max_rows()

ARQUIVO = "/saida/bauru_ampla.csv"  # <- ajuste aqui
ENCODING = "latin1"
SEP = ";"  # ajuste se precisar

COLS = {
    "curso": "curso",
    "ano": "ano_origem",
    "tipo": "tipo",  # Ampla / Isentos / Convênio
    "vagas": "vagas",
    "vagas_rem": "vagas_remanescentes",
    "mat_total": "matriculados_total",
    "mat_m": "matriculados_sexo_masc",
    "mat_f": "matriculados_sexo_fem",
    "conv": "matrículas_chamada_conv",
    "le": "matrículas_chamada_le",
    "rel_ad": "matrículas_relação_adicional",
}

# =============================
# LOAD & PREP
# =============================
@st.cache_data(show_spinner=False)
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, encoding=ENCODING, sep=SEP)
    # tipagem
    for c in [COLS["ano"]]:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    for c in [
        COLS["vagas"], COLS["vagas_rem"], COLS["mat_total"],
        COLS["mat_m"], COLS["mat_f"], COLS["conv"], COLS["le"], COLS["rel_ad"]
    ]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)

    # limpeza básica
    for c in [COLS["curso"], COLS["tipo"]]:
        df[c] = df[c].astype(str).str.strip()

    # derivadas úteis
    df["ocupacao"] = np.where(
        (df[COLS["vagas"]].fillna(0) > 0),
        df[COLS["mat_total"]] / df[COLS["vagas"]].replace(0, np.nan),
        np.nan,
    )
    denom_sexo = (df[COLS["mat_m"]].fillna(0) + df[COLS["mat_f"]].fillna(0))
    df["pct_f"] = np.where(denom_sexo > 0, df[COLS["mat_f"]] / denom_sexo, np.nan)

    return df

df = load_data(ARQUIVO)

# =============================
# SIDEBAR (FILTROS)
# =============================
st.sidebar.header("Filtros")
anos = sorted(df[COLS["ano"]].dropna().unique().tolist())
cursos = sorted(df[COLS["curso"]].dropna().unique().tolist())
tipos = sorted(df[COLS["tipo"]].dropna().unique().tolist())

ano_sel = st.sidebar.slider(
    "Ano (intervalo)", int(min(anos)), int(max(anos)),
    (int(min(anos)), int(max(anos)))
)
curso_sel = st.sidebar.multiselect("Curso(s)", options=cursos, default=cursos)
tipo_sel = st.sidebar.multiselect("Tipo de convocação", options=tipos, default=tipos)
modo = st.sidebar.radio("Modo de exibição", ["Absoluto", "Percentual"], index=0)

# aplica filtros
df_f = df[
    df[COLS["ano"]].between(ano_sel[0], ano_sel[1])
    & df[COLS["curso"]].isin(curso_sel)
    & df[COLS["tipo"]].isin(tipo_sel)
].copy()

# =============================
# FUNÇÕES DE AGREGAÇÃO
# =============================
def agg_por_ano(dfx: pd.DataFrame) -> pd.DataFrame:
    g = dfx.groupby(COLS["ano"], as_index=False)[COLS["mat_total"]].sum()
    return g.rename(columns={COLS["mat_total"]: "matriculas"})

def agg_sexo_por_ano(dfx: pd.DataFrame, percentual: bool) -> pd.DataFrame:
    g = dfx.groupby(COLS["ano"], as_index=False)[[COLS["mat_m"], COLS["mat_f"]]].sum()
    g = g.rename(columns={COLS["mat_m"]: "M", COLS["mat_f"]: "F"})
    if percentual:
        tot = g["M"] + g["F"]
        g["M"] = np.where(tot > 0, g["M"]/tot, 0.0)
        g["F"] = np.where(tot > 0, g["F"]/tot, 0.0)
    return g

def agg_tipo_por_ano(dfx: pd.DataFrame, percentual: bool) -> pd.DataFrame:
    g = dfx.groupby([COLS["ano"], COLS["tipo"]], as_index=False)[COLS["mat_total"]].sum()
    g = g.rename(columns={COLS["mat_total"]: "matriculas"})
    if percentual:
        g["total_ano"] = g.groupby(COLS["ano"])["matriculas"].transform("sum")
        g["matriculas"] = np.where(g["total_ano"] > 0, g["matriculas"]/g["total_ano"], 0.0)
        g = g.drop(columns=["total_ano"])
    return g

def kpis(dfx: pd.DataFrame):
    if dfx.empty:
        return 0, None, None, {}
    # total no filtro
    total = int(dfx[COLS["mat_total"]].sum())

    # ano atual = maior dentro do filtro; ano anterior
    anos_loc = sorted(dfx[COLS["ano"]].dropna().unique())
    yoy = None
    pct_f_ultimo = None
    part_tipo_ultimo = {}

    if anos_loc:
        ano_ult = anos_loc[-1]
        ano_ant = anos_loc[-2] if len(anos_loc) >= 2 else None

        df_ult = dfx[dfx[COLS["ano"]] == ano_ult]
        total_ult = int(df_ult[COLS["mat_total"]].sum())
        if ano_ant is not None:
            df_ant = dfx[dfx[COLS["ano"]] == ano_ant]
            total_ant = int(df_ant[COLS["mat_total"]].sum())
            if total_ant > 0:
                yoy = (total_ult - total_ant) / total_ant

        # %F no último ano
        fem = int(df_ult[COLS["mat_f"]].sum())
        masc = int(df_ult[COLS["mat_m"]].sum())
        denom = fem + masc
        pct_f_ultimo = (fem / denom) if denom > 0 else None

        # participação por tipo no último ano
        g = df_ult.groupby(COLS["tipo"])[COLS["mat_total"]].sum()
        tot = g.sum()
        if tot > 0:
            part_tipo_ultimo = {k: float(v/tot) for k, v in g.to_dict().items()}

    return total, yoy, pct_f_ultimo, part_tipo_ultimo

# =============================
# CABEÇALHO + KPIs
# =============================
st.title("Análise dos Dados do Vestibular — UNESP Bauru")

col_a, col_b, col_c, col_d = st.columns(4)
total, yoy, pctf, part_tipo = kpis(df_f)
col_a.metric("Total de matrículas (filtro)", f"{total:,}".replace(",", "."))

if yoy is None:
    col_b.metric("Variação vs. ano anterior", "—")
else:
    col_b.metric("Variação vs. ano anterior", f"{yoy*100:,.1f}%".replace(",", "."))
col_c.metric("% Feminino (último ano)", "—" if pctf is None else f"{pctf*100:,.1f}%".replace(",", "."))

if part_tipo:
    # mostra a maior participação
    tipo_top = max(part_tipo, key=part_tipo.get)
    col_d.metric(f"Maior participação (últ. ano)", f"{tipo_top} — {part_tipo[tipo_top]*100:,.1f}%".replace(",", "."))
else:
    col_d.metric("Participação por tipo (últ. ano)", "—")

st.divider()

# =============================
# ABAS
# =============================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Visão Geral", "Por Sexo", "Por Tipo", "Drilldown por Curso", "Insights"
])

# ---- Visão Geral ----
with tab1:
    g1 = agg_por_ano(df_f)
    st.subheader("Matrículas por ano")
    if g1.empty:
        st.info("Sem dados para os filtros selecionados.")
    else:
        chart1 = (
            alt.Chart(g1)
            .mark_line(point=True)
            .encode(
                x=alt.X("ano_origem:O", title="Ano"),
                y=alt.Y("matriculas:Q", title="Matrículas"),
                tooltip=["ano_origem", "matriculas"]
            )
            .properties(height=320)
        )
        st.altair_chart(chart1, use_container_width=True)

    st.subheader("Composição por tipo (último ano selecionado)")
    if not df_f.empty:
        ano_last = df_f[COLS["ano"]].max()
        df_last = df_f[df_f[COLS["ano"]] == ano_last]
        g_last = agg_tipo_por_ano(df_last, percentual=(modo == "Percentual"))
        if g_last.empty:
            st.info("Sem dados para o último ano.")
        else:
            chart2 = (
                alt.Chart(g_last)
                .mark_bar()
                .encode(
                    x=alt.X("tipo:N", title="Tipo de convocação"),
                    y=alt.Y("matriculas:Q", title="Matrículas" if modo=="Absoluto" else "Participação"),
                    tooltip=["tipo", alt.Tooltip("matriculas:Q", format=".2%") if modo=="Percentual" else "matriculas"]
                )
                .properties(height=320)
            )
            st.altair_chart(chart2, use_container_width=True)

    st.subheader("Resumo por ano")
    st.dataframe(g1.sort_values("ano_origem"))

    st.download_button(
        "Baixar dados filtrados (CSV)",
        data=df_f.to_csv(index=False).encode("utf-8"),
        file_name="dados_filtrados.csv",
        mime="text/csv",
    )

# ---- Por Sexo ----
with tab2:
    st.subheader("Matrículas por sexo por ano")
    g2 = agg_sexo_por_ano(df_f, percentual=(modo == "Percentual"))
    if g2.empty:
        st.info("Sem dados para os filtros selecionados.")
    else:
        g2m = g2.melt(id_vars=[COLS["ano"]], value_vars=["M", "F"], var_name="sexo", value_name="valor")
        chart = (
            alt.Chart(g2m)
            .mark_bar()
            .encode(
                x=alt.X("ano_origem:O", title="Ano"),
                y=alt.Y("valor:Q", title="Matrículas" if modo=="Absoluto" else "Participação"),
                color="sexo:N",
                tooltip=["ano_origem", "sexo", alt.Tooltip("valor:Q", format=".2%") if modo=="Percentual" else "valor:Q"]
            )
            .properties(height=360)
        )
        st.altair_chart(chart, use_container_width=True)

    # Tabela
    if not g2.empty:
        if modo == "Percentual":
            g2_show = g2.copy()
            g2_show["M"] = (g2_show["M"]*100).round(1)
            g2_show["F"] = (g2_show["F"]*100).round(1)
        else:
            g2_show = g2
        st.dataframe(g2_show.sort_values("ano_origem"))

# ---- Por Tipo ----
with tab3:
    st.subheader("Matrículas por tipo de convocação por ano")
    g3 = agg_tipo_por_ano(df_f, percentual=(modo == "Percentual"))
    if g3.empty:
        st.info("Sem dados para os filtros selecionados.")
    else:
        chart = (
            alt.Chart(g3)
            .mark_bar()
            .encode(
                x=alt.X("ano_origem:O", title="Ano"),
                y=alt.Y("matriculas:Q", title="Matrículas" if modo=="Absoluto" else "Participação"),
                color=alt.Color("tipo:N", legend=alt.Legend(title="Tipo")),
                tooltip=["ano_origem", "tipo", alt.Tooltip("matriculas:Q", format=".2%") if modo=="Percentual" else "matriculas:Q"]
            )
            .properties(height=380)
        )
        st.altair_chart(chart, use_container_width=True)

    st.dataframe(
        g3.sort_values(["ano_origem", "tipo"]).assign(
            **({"matriculas(%)": (g3["matriculas"]*100).round(1)} if modo=="Percentual" else {})
        )
    )

# ---- Drilldown por Curso ----
with tab4:
    st.subheader("Drilldown por curso")
    cursos_disp = sorted(df_f[COLS["curso"]].unique().tolist())
    curso_unique = st.selectbox("Selecione um curso", options=cursos_disp) if cursos_disp else None
    if curso_unique is None:
        st.info("Sem cursos disponíveis no filtro atual.")
    else:
        df_c = df_f[df_f[COLS["curso"]] == curso_unique]
        # linha histórica do curso
        g_c = df_c.groupby(COLS["ano"], as_index=False)[COLS["mat_total"]].sum().rename(columns={COLS["mat_total"]: "matriculas"})
        chart_c = (
            alt.Chart(g_c)
            .mark_line(point=True)
            .encode(x=alt.X("ano_origem:O", title="Ano"), y=alt.Y("matriculas:Q", title="Matrículas"), tooltip=["ano_origem", "matriculas"])
            .properties(height=320)
        )
        st.altair_chart(chart_c, use_container_width=True)

        # barras por sexo e por tipo no último ano
        ano_last = df_c[COLS["ano"]].max()
        df_c_last = df_c[df_c[COLS["ano"]] == ano_last]

        col1, col2 = st.columns(2)
        with col1:
            st.caption(f"Por sexo — {ano_last}")
            gsex = df_c_last.agg({COLS["mat_m"]:"sum", COLS["mat_f"]:"sum"}).rename({COLS["mat_m"]:"M", COLS["mat_f"]:"F"}).reset_index()
            gsex.columns = ["sexo", "valor"]
            chart_sex = alt.Chart(gsex).mark_bar().encode(x="sexo:N", y="valor:Q", tooltip=["sexo","valor"])
            st.altair_chart(chart_sex, use_container_width=True)

        with col2:
            st.caption(f"Por tipo — {ano_last}")
            gtipo = df_c_last.groupby(COLS["tipo"], as_index=False)[COLS["mat_total"]].sum().rename(columns={COLS["mat_total"]:"matriculas"})
            chart_tipo = alt.Chart(gtipo).mark_bar().encode(x="tipo:N", y="matriculas:Q", tooltip=["tipo","matriculas"])
            st.altair_chart(chart_tipo, use_container_width=True)

        st.download_button(
            f"Baixar dados do curso ({curso_unique})",
            data=df_c.to_csv(index=False).encode("utf-8"),
            file_name=f"dados_{curso_unique.replace(' ','_')}.csv",
            mime="text/csv",
        )

# ---- Insights ----
with tab5:
    st.subheader("Insights automáticos")

    # Crescimento por curso (período filtrado)
    if df_f.empty:
        st.info("Sem dados para os filtros selecionados.")
    else:
        g_curso_ano = (
            df_f.groupby([COLS["curso"], COLS["ano"]], as_index=False)[COLS["mat_total"]].sum()
            .rename(columns={COLS["mat_total"]:"mat"})
        )
        # calcula variação do primeiro para o último ano por curso
        first_year = g_curso_ano[COLS["ano"]].min()
        last_year = g_curso_ano[COLS["ano"]].max()
        base = g_curso_ano[g_curso_ano[COLS["ano"]] == first_year][[COLS["curso"], "mat"]].rename(columns={"mat":"mat_first"})
        last = g_curso_ano[g_curso_ano[COLS["ano"]] == last_year][[COLS["curso"], "mat"]].rename(columns={"mat":"mat_last"})
        comp = pd.merge(base, last, on=COLS["curso"], how="inner")
        comp["delta_abs"] = comp["mat_last"] - comp["mat_first"]
        comp["delta_pct"] = np.where(comp["mat_first"]>0, comp["delta_abs"]/comp["mat_first"], np.nan)

        top_up = comp.sort_values(["delta_abs", "delta_pct"], ascending=[False, False]).head(3)
        top_down = comp.sort_values(["delta_abs", "delta_pct"], ascending=[True, True]).head(3)

        c1, c2 = st.columns(2)
        with c1:
            st.caption(f"Top 3 ↑ crescimento (de {first_year} para {last_year})")
            if top_up.empty:
                st.write("—")
            else:
                st.dataframe(
                    top_up.assign(delta_pct_fmt=lambda d: (d["delta_pct"]*100).round(1).astype(str)+"%")[[
                        COLS["curso"], "mat_first", "mat_last", "delta_abs", "delta_pct_fmt"
                    ]]
                )
        with c2:
            st.caption(f"Top 3 ↓ queda (de {first_year} para {last_year})")
            if top_down.empty:
                st.write("—")
            else:
                st.dataframe(
                    top_down.assign(delta_pct_fmt=lambda d: (d["delta_pct"]*100).round(1).astype(str)+"%")[[
                        COLS["curso"], "mat_first", "mat_last", "delta_abs", "delta_pct_fmt"
                    ]]
                )

        # Participação de tipos: primeiro vs. último ano
        g_tipo = (
            df_f.groupby([COLS["ano"], COLS["tipo"]], as_index=False)[COLS["mat_total"]].sum()
            .rename(columns={COLS["mat_total"]: "mat"})
        )
        def part_por_ano(d):
            tot = d["mat"].sum()
            d = d.copy()
            d["part"] = np.where(tot>0, d["mat"]/tot, np.nan)
            return d
        g_tipo = g_tipo.groupby(COLS["ano"], group_keys=False).apply(part_por_ano)

        first_part = g_tipo[g_tipo[COLS["ano"]] == first_year][[COLS["tipo"], "part"]].rename(columns={"part":"part_first"})
        last_part = g_tipo[g_tipo[COLS["ano"]] == last_year][[COLS["tipo"], "part"]].rename(columns={"part":"part_last"})
        comp_part = pd.merge(first_part, last_part, on=COLS["tipo"], how="outer")
        comp_part["delta_pp"] = (comp_part["part_last"] - comp_part["part_first"]) * 100

        st.caption(f"Mudança de participação por tipo ({first_year} → {last_year}) — pontos percentuais")
        if comp_part.empty:
            st.write("—")
        else:
            show = comp_part.copy()
            for c in ["part_first", "part_last", "delta_pp"]:
                show[c] = show[c].astype(float)
            show = show.assign(
                part_first=lambda d: (d["part_first"]*100).round(1),
                part_last=lambda d: (d["part_last"]*100).round(1),
                delta_pp=lambda d: d["delta_pp"].round(1),
            )
            st.dataframe(show.rename(columns={
                COLS["tipo"]: "Tipo",
                "part_first": f"Part. {first_year} (%)",
                "part_last": f"Part. {last_year} (%)",
                "delta_pp": "Δ pp"
            }))

# =============================
# RODAPÉ
# =============================
st.markdown("---")
st.caption("Fonte: UNESP — Campus Bauru. Dashboard acadêmico para TCC. Valores podem conter lacunas em anos/cursos específicos.")
