import gzip
from grafo import Grafo


def ler_grafo(nome_arquivo, representacao="lista"):

    if nome_arquivo.endswith(".gz"):
        arquivo = gzip.open(nome_arquivo, "rt")
    else:
        arquivo = open(nome_arquivo, "r")

    with arquivo:
        numero_vertices = int(arquivo.readline())

        grafo = Grafo(numero_vertices, representacao)

        for linha in arquivo:
            linha = linha.strip()

            if linha == "":
                continue

            u, v = map(int, linha.split())

            grafo.adicionar_aresta(u, v)

    return grafo