import json
import re
from pathlib import Path
from statistics import mean, stdev

RAIZ = Path(__file__).resolve().parent.parent
PASTA = Path(__file__).resolve().parent
RESULTADOS = RAIZ / "resultados_p3" / "todos_pares"
VERTICES = [10, 20, 30, 40, 50]
ORIGENS = [10, 20, 30]


def decimal(valor, casas):
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def distancia(valor):
    if isinstance(valor, str):
        return r"$-\infty$" if valor.startswith("-") else r"$\infty$"
    return decimal(valor + 0.0, 2)


def tempo(segundos):
    if segundos >= 100:
        return decimal(segundos, 0)
    if segundos >= 10:
        return decimal(segundos, 1)
    if segundos >= 1:
        return decimal(segundos, 2)
    return decimal(segundos, 3)


def media_dp(registro):
    tempos = registro["tempos"]
    texto = tempo(mean(tempos))
    if len(tempos) > 1:
        texto += r" {\scriptsize(" + tempo(stdev(tempos)) + ")}"
    return texto


def tabela(cabecalho, alinhamento, linhas):
    corpo = "\n".join(" & ".join(linha) + r" \\" for linha in linhas)
    return (rf"\begin{{tabular}}{{{alinhamento}}}" + "\n\\toprule\n" + " & ".join(cabecalho)
            + " \\\\\n\\midrule\n" + corpo + "\n\\bottomrule\n\\end{tabular}")


def comando(nome, conteudo):
    return rf"\newcommand{{\{nome}}}{{%" + "\n" + conteudo + "%\n}\n"


def carregar(numero):
    return json.loads((RESULTADOS / f"grafo_W_{numero}.txt.gz.json").read_text(encoding="utf-8"))


def matriz(amostra):
    linhas = [[str(u)] + [distancia(x) for x in linha] for u, linha in zip(VERTICES, amostra)]
    return tabela([""] + [str(v) for v in VERTICES], "lrrrrr", linhas)


def matrizes_antigas():
    texto = (PASTA / "dados.tex").read_text(encoding="utf-8")
    antigas = {}
    for nome in ("MatrizTres", "MatrizQuatro", "MatrizCinco"):
        achado = re.search(r"\\newcommand\{\\" + nome + r"\}\{%\n(.*?)%?\n\}\n", texto, re.S)
        antigas[nome] = achado.group(1).rstrip("%")
    return antigas


def main():
    antigas = matrizes_antigas()
    grafos = {numero: carregar(numero) for numero in range(1, 6)}
    saida = []

    linhas = []
    for numero, dados in grafos.items():
        algoritmos = dados["algoritmos"]
        distancias = algoritmos["bellman_ford_c"]["resultado"]["distancias"]
        linhas.append([f"W{numero}"] + [distancia(distancias[str(u)]) for u in ORIGENS]
                      + [media_dp(algoritmos["bellman_ford_py"]), media_dp(algoritmos["bellman_ford_c"])])
    saida.append(comando("TabelaDestino", tabela(
        ["Grafo", "$10$", "$20$", "$30$", "Python (s)", "C (s)"], "lrrrrr", linhas)))

    saida.append(comando("MatrizUm", matriz(grafos[1]["algoritmos"]["fw_blocado_c"]["resultado"]["amostra"])))
    saida.append(comando("MatrizDois", matriz(grafos[2]["algoritmos"]["fw_blocado_c"]["resultado"]["amostra"])))
    for nome, conteudo in antigas.items():
        saida.append(comando(nome, conteudo))

    linhas = []
    for numero, dados in grafos.items():
        algoritmos = dados["algoritmos"]
        linha = [f"W{numero}", media_dp(algoritmos["bellman_ford_py"]), media_dp(algoritmos["bellman_ford_c"])]
        for chave in ("fw_blocado_c", "fw_classico_c"):
            linha.append(media_dp(algoritmos[chave]) if "tempos" in algoritmos[chave] else "---")
        linhas.append(linha)
    saida.append(comando("TabelaTempos", tabela(
        ["Grafo", "BF Python", "BF C", "FW C blocado", "FW C clássico"], "lrrrr", linhas)))

    linhas = []
    for numero in (1, 2):
        algoritmos = grafos[numero]["algoritmos"]
        johnson = media_dp(algoritmos["johnson_c"])
        if algoritmos["johnson_c"]["resultado"]["amostra"] is None:
            johnson += r"\textsuperscript{*}"
        linhas.append([f"W{numero}", media_dp(algoritmos["bf_todos_c"]), johnson,
                       media_dp(algoritmos["fw_blocado_c"]), media_dp(algoritmos["fw_classico_c"])])
    saida.append(comando("TabelaTodosPares", tabela(
        ["Grafo", r"BF $\times n$", "Johnson", "FW blocado", "FW clássico"], "lrrrr", linhas)))

    sinteticos = json.loads((RESULTADOS / "sinteticos.json").read_text(encoding="utf-8"))["casos"]
    colunas = [("fw_classico_py",), ("fw_blocado_py",), ("fw_classico_c_1t", "fw_classico_c"),
               ("fw_blocado_c_1t", "fw_blocado_c"), ("bf_todos_py", "bf_todos_c"), ("johnson_py", "johnson_c")]
    linhas = []
    for n, caso in sinteticos.items():
        algoritmos = caso["algoritmos"]
        linhas.append([decimal(int(n), 0)] + [" / ".join(tempo(algoritmos[c]["media_s"]) for c in grupo)
                                               for grupo in colunas])
    saida.append(comando("TabelaSinteticos", tabela(
        ["$n$", "FW Py clás.", "FW Py bloc.", "FW C clás. 1T/8T", "FW C bloc. 1T/8T",
         r"BF$\times n$ Py/C", "Johnson Py/C"], "rrrrrrr", linhas)))

    pontos = {}
    for chave in ("fw_classico_py", "fw_classico_c", "fw_blocado_c", "bf_todos_c", "johnson_c"):
        pontos[chave] = " ".join(f"({n},{caso['algoritmos'][chave]['media_s']:.4f})"
                                 for n, caso in sinteticos.items())
    for chave, nome in (("fw_classico_py", "PontosFwPy"), ("fw_classico_c", "PontosFwClassico"),
                        ("fw_blocado_c", "PontosFwBlocado"), ("bf_todos_c", "PontosBfTodos"),
                        ("johnson_c", "PontosJohnson")):
        saida.append(rf"\newcommand{{\{nome}}}{{{pontos[chave]}}}" + "\n")

    valores = {
        "TempoFwBlocadoUm": tempo(mean(grafos[1]["algoritmos"]["fw_blocado_c"]["tempos"])),
        "TempoFwBlocadoDois": tempo(mean(grafos[2]["algoritmos"]["fw_blocado_c"]["tempos"])),
        "TempoFwClassicoUm": tempo(mean(grafos[1]["algoritmos"]["fw_classico_c"]["tempos"])),
        "TempoFwClassicoDois": tempo(mean(grafos[2]["algoritmos"]["fw_classico_c"]["tempos"])),
        "TempoBfTodosUm": tempo(mean(grafos[1]["algoritmos"]["bf_todos_c"]["tempos"])),
        "TempoBfTodosDois": tempo(mean(grafos[2]["algoritmos"]["bf_todos_c"]["tempos"])),
        "TempoJohnsonDois": tempo(mean(grafos[2]["algoritmos"]["johnson_c"]["tempos"])),
    }
    for nome, valor in valores.items():
        saida.append(rf"\newcommand{{\{nome}}}{{{valor}}}" + "\n")

    (PASTA / "dados.tex").write_text("\n".join(saida), encoding="utf-8")


if __name__ == "__main__":
    main()
