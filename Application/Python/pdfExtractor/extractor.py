import os
import pandas as pd
import camelot


def extrair_bauru_em_csvs(pasta_pdf: str, campus_alvo: str = "bauru", pasta_saida: str = "./saida") -> None:
    arquivos_pdf = sorted([f for f in os.listdir(pasta_pdf) if f.lower().endswith(".pdf")])

    ampla = []
    se = []
    isento = []

    # Índices fixos das tabelas para cada categoria
    indices_ampla = {0, 3, 6, 7}
    indices_se = {1, 4, 8, 9}
    indices_isento = {2, 5, 10, 11}

    for idx, arquivo in enumerate(arquivos_pdf):
        ano = 2015 + idx
        caminho = os.path.join(pasta_pdf, arquivo)
        print(f"📄 Processando: {arquivo} (ano: {ano})")

        try:
            tables = camelot.read_pdf(caminho, pages='all', flavor='stream')
            for i, t in enumerate(tables):
                df = t.df
                if df.empty:
                    continue

                primeira_coluna = df.columns[0]
                filtrado = df[df[primeira_coluna].str.contains(campus_alvo, case=False, na=False)].copy()

                if not filtrado.empty:
                    filtrado["tabela_origem"] = i + 1
                    filtrado["arquivo_origem"] = arquivo
                    filtrado["ano_origem"] = ano

                    if i in indices_ampla:
                        ampla.append(filtrado)
                    elif i in indices_se:
                        se.append(filtrado)
                    elif i in indices_isento:
                        isento.append(filtrado)

        except Exception as e:
            print(f"Erro ao processar {arquivo}: {e}")

    os.makedirs(pasta_saida, exist_ok=True)

    if ampla:
        pd.concat(ampla, ignore_index=True).to_csv(os.path.join(pasta_saida, "bauru_ampla.csv"), index=False)
    if se:
        pd.concat(se, ignore_index=True).to_csv(os.path.join(pasta_saida, "bauru_se.csv"), index=False)
    if isento:
        pd.concat(isento, ignore_index=True).to_csv(os.path.join(pasta_saida, "bauru_isento.csv"), index=False)

    print("✅ Arquivos salvos com sucesso!")
