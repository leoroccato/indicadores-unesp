import pandas as pd
import os

# === 1) Pasta onde estão os CSVs brutos ===
input_folder = r"C:\Users\leoro\Desktop\UNESP\TCC 2.0\Application\Python\pdfExtractor\extracts"

# === 2) Padrão de colunas final esperado ===
colunas_finais = [
    'curso', 'vagas', 'convocados', 'lista_espera',
    'relacao_adic', 'vagas_reman', 'masc', 'fem', 'total',
    'metodo_ingresso', 'area'
]

# === 3) Lista para armazenar os DataFrames filtrados ===
dfs_bauru = []

# === 4) Loop em todos os CSVs na pasta ===
for arquivo in os.listdir(input_folder):
    if arquivo.endswith(".csv"):
        caminho = os.path.join(input_folder, arquivo)

        # Ler CSV
        df = pd.read_csv(caminho)

        # Garantir a coluna 'vagas_reman'
        if 'vagas_reman' not in df.columns:
            df['vagas_reman'] = pd.NA

        # Filtrar apenas cursos de Bauru (case-insensitive)
        df_bauru = df[df['curso'].str.upper().str.contains('BAURU', na=False)].copy()

        # Garantir que todas as colunas finais existem
        for col in colunas_finais:
            if col not in df_bauru.columns:
                df_bauru[col] = pd.NA

        # Reordenar as colunas
        df_bauru = df_bauru[colunas_finais]

        # Anexar à lista
        dfs_bauru.append(df_bauru)

        print(f"✅ Processado: {arquivo} | Bauru encontrados: {len(df_bauru)}")

# === 5) Concatenar tudo ===
df_final_bauru = pd.concat(dfs_bauru, ignore_index=True)

# === 6) Salvar CSV final ===
df_final_bauru.to_csv("dados_bauru_unificado.csv", index=False)
print(f"\n✅ Arquivo final salvo: dados_bauru_unificado.csv | Total linhas: {len(df_final_bauru)}")
