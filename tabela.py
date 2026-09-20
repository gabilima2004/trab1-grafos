"""Junta os arquivos resultados_*.txt em tabelas Markdown, com os
grafos nas linhas e as características medidas nas colunas.

Uso:
    python3 tabela.py
    python3 tabela.py --saida tabelas.md
"""

import argparse
import glob
import re


def procurar(texto, padrao, grupo=1, padrao_vazio="-"):
    achado = re.search(padrao, texto)

    return achado.group(grupo) if achado else padrao_vazio


def ler_resultado(caminho):
    texto = open(caminho).read()

    dados = {
        "grafo": procurar(texto, r"Estudos de caso - (\S+)"),
        "vertices": procurar(texto, r"Número de vértices: (\d+)"),
        "arestas": procurar(texto, r"Número de arestas: (\d+)"),
        "mem_lista": procurar(texto, r"lista\s+:\s+([\d.]+) MB"),
        "mem_matriz": procurar(texto, r"matriz\s+:\s+([\d.]+) MB"),
        "componentes": procurar(texto, r"componentes conexas: (\d+)"),
        "maior": procurar(texto, r"Maior componente: (\d+)"),
        "menor": procurar(texto, r"Menor componente: (\d+)"),
        "diam_aprox": procurar(texto, r"Diâmetro aproximado[^:]*: (\d+)"),
        "diam_exato": procurar(texto, r"Diâmetro exato: (\d+)"),
    }

    for nome, rep in (("bfs", "lista"), ("bfs", "matriz"),
                      ("dfs", "lista"), ("dfs", "matriz")):
        dados[f"{nome}_{rep}"] = procurar(
            texto, rf"{nome.upper()} - {rep}\s*:\s+([\d.]+) s"
        )

    for u, v in ((10, 20), (10, 30), (20, 30)):
        dados[f"d{u}_{v}"] = procurar(texto, rf"distância\({u}, {v}\) = (.+)")

    dados["pais"] = re.findall(r"^((?:BFS|DFS) a partir de .+)$",
                               texto, re.MULTILINE)

    return dados


def tabela(cabecalho, linhas):
    saida = ["| " + " | ".join(cabecalho) + " |",
             "|" + "|".join("---" for _ in cabecalho) + "|"]

    for linha in linhas:
        saida.append("| " + " | ".join(str(c) for c in linha) + " |")

    return "\n".join(saida)


def montar(resultados):
    blocos = []

    blocos.append("## Memória e tempo de execução\n")
    blocos.append(tabela(
        ["grafo", "vértices", "arestas", "memória lista (MB)",
         "memória matriz (MB)", "BFS lista (s)", "BFS matriz (s)",
         "DFS lista (s)", "DFS matriz (s)"],
        [[d["grafo"], d["vertices"], d["arestas"], d["mem_lista"],
          d["mem_matriz"], d["bfs_lista"], d["bfs_matriz"],
          d["dfs_lista"], d["dfs_matriz"]] for d in resultados]
    ))

    blocos.append("\n## Distâncias, componentes e diâmetro\n")
    blocos.append(tabela(
        ["grafo", "d(10,20)", "d(10,30)", "d(20,30)", "componentes",
         "maior componente", "menor componente", "diâmetro aprox.",
         "diâmetro exato"],
        [[d["grafo"], d["d10_20"], d["d10_30"], d["d20_30"],
          d["componentes"], d["maior"], d["menor"],
          d["diam_aprox"], d["diam_exato"]] for d in resultados]
    ))

    blocos.append("\n## Pai dos vértices 10, 20 e 30\n")

    for d in resultados:
        blocos.append(f"**{d['grafo']}**\n")

        for linha in d["pais"]:
            blocos.append(f"- {linha}")

        blocos.append("")

    return "\n".join(blocos)


def main():
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument("--padrao", default="resultados_*.txt")
    parser.add_argument("--saida", default="tabelas.md")

    args = parser.parse_args()

    arquivos = sorted(glob.glob(args.padrao))

    if not arquivos:
        print(f"Nenhum arquivo encontrado em {args.padrao}")
        return

    resultados = [ler_resultado(a) for a in arquivos]

    texto = montar(resultados)

    with open(args.saida, "w") as f:
        f.write(texto + "\n")

    print(texto)
    print(f"\nTabelas salvas em {args.saida}"
          f" ({len(arquivos)} grafo(s): {', '.join(arquivos)})")


if __name__ == "__main__":
    main()
