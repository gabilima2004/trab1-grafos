"""Caminhos mínimos ponderados com um único laço de Dijkstra."""

from math import inf
from prioridades import FilaVetor, HeapIndexado

MENSAGEM_PESO_NEGATIVO = "A biblioteca ainda não implementa caminhos mínimos com pesos negativos."
FILAS = {"vetor": FilaVetor, "heap": HeapIndexado}


def dijkstra(grafo, origem, implementacao="heap"):
    """Retorna (distancias, pais), vetores indexados pelos vértices 1..n.

    Inalcançáveis têm distância inf e pai None. A raiz tem pai None.
    Pesos zero são aceitos; qualquer peso negativo impede a execução.
    """
    grafo.validar_vertice(origem)
    if grafo.tem_peso_negativo:
        raise ValueError(MENSAGEM_PESO_NEGATIVO)
    criar_fila = implementacao
    if isinstance(implementacao, str):
        if implementacao not in FILAS:
            raise ValueError("Implementação deve ser 'vetor' ou 'heap'.")
        criar_fila = FILAS[implementacao]
    distancias = [inf] * (grafo.numero_vertices + 1)
    pais = [None] * (grafo.numero_vertices + 1)
    finalizado = bytearray(grafo.numero_vertices + 1)
    distancias[origem] = 0.0
    fila = criar_fila(distancias)
    fila.atualizar(origem)
    while True:
        u = fila.extrair_minimo()
        if u is None:
            break
        finalizado[u] = 1
        for v, peso in grafo.vizinhos_com_pesos(u):
            candidata = distancias[u] + peso
            if not finalizado[v] and candidata < distancias[v]:
                distancias[v] = candidata
                pais[v] = u
                fila.atualizar(v)
    return distancias, pais


def reconstruir_caminho(pais, origem, destino):
    """Retorna os vértices da rota ou [] quando não há caminho."""
    if not 1 <= origem < len(pais) or not 1 <= destino < len(pais):
        raise ValueError("Origem ou destino inválido.")
    caminho = []
    atual = destino
    while atual:
        caminho.append(int(atual))
        if atual == origem:
            return caminho[::-1]
        if len(caminho) >= len(pais):
            raise ValueError("Vetor de pais contém um ciclo.")
        atual = pais[atual]
    return []


def salvar_caminhos(nome_arquivo, origem, distancias, pais):
    """Salva a árvore de caminhos mínimos, incluindo os inalcançáveis."""
    with open(nome_arquivo, "w", encoding="utf-8") as arquivo:
        arquivo.write(f"# Dijkstra - origem {origem}\n# vertice pai distancia\n")
        for v in range(1, len(distancias)):
            arquivo.write(f"{v} {pais[v] if pais[v] is not None else 0} {distancias[v]}\n")
