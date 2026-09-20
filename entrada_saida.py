from grafo import Grafo


def ler_grafo(nome_arquivo, representacao="lista"):
    with open(nome_arquivo, "r") as arquivo:
        numero_vertices = int(arquivo.readline())

        grafo = Grafo(numero_vertices, representacao)

        for linha in arquivo:
            linha = linha.strip()

            if linha == "":
                continue

            u, v = map(int, linha.split())

            grafo.adicionar_aresta(u, v)

    return grafo