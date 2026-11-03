import gzip
from grafo import Grafo


def ler_grafo(nome_arquivo, representacao="lista", ponderado=None):
    """Detecta duas ou três colunas; ponderado força o formato, se informado."""
    nome_arquivo = str(nome_arquivo)

    if nome_arquivo.endswith(".gz"):
        arquivo = gzip.open(nome_arquivo, "rt")
    else:
        arquivo = open(nome_arquivo, "r")

    with arquivo:
        numero_vertices = int(arquivo.readline())

        grafo = None
        formato = ponderado

        for numero_linha, linha in enumerate(arquivo, 2):
            linha = linha.strip()

            if linha == "":
                continue

            campos = linha.split()
            if formato is None:
                formato = len(campos) == 3
            if len(campos) != (3 if formato else 2):
                raise ValueError(f"Linha {numero_linha}: número de colunas inválido.")
            if grafo is None:
                grafo = Grafo(numero_vertices, representacao, formato)
            try:
                u, v = map(int, campos[:2])
                grafo.adicionar_aresta(u, v, float(campos[2]) if formato else None)
            except ValueError as erro:
                raise ValueError(f"Linha {numero_linha}: {erro}") from erro

    return grafo if grafo is not None else Grafo(numero_vertices, representacao, bool(formato))
