"""Consulta da rede de pesquisadores com correspondência exata dos nomes."""

import argparse
import json

from caminhos_minimos import dijkstra, reconstruir_caminho
from entrada_saida import ler_grafo
from experimentos_p2 import formatar_distancia


ORIGEM = "Edsger W. Dijkstra"
DESTINOS = ("Alan M. Turing", "J. B. Kruskal", "Jon M. Kleinberg",
            "Éva Tardos", "Daniel R. Figueiredo")


def ler_pesquisadores(nome_arquivo, grafo):
    """Lê JSON {nome exato: índice}, independente do formato externo da disciplina."""
    def sem_duplicatas(pares):
        nomes = {}
        for nome, indice in pares:
            if nome in nomes:
                raise ValueError(f"Nome duplicado: {nome}")
            nomes[nome] = indice
        return nomes

    with open(nome_arquivo, encoding="utf-8-sig") as arquivo:
        nomes = json.load(arquivo, object_pairs_hook=sem_duplicatas)
    if not isinstance(nomes, dict):
        raise ValueError("O JSON deve ser um objeto {nome: índice}.")
    indices = set()
    for nome, indice in nomes.items():
        if not isinstance(nome, str) or type(indice) is not int:
            raise ValueError("Cada pesquisador deve ter nome textual e índice inteiro.")
        grafo.validar_vertice(indice)
        if indice in indices:
            raise ValueError(f"Índice duplicado: {indice}")
        indices.add(indice)
    for nome in (ORIGEM, *DESTINOS):
        if nome not in nomes:
            raise ValueError(f"Pesquisador ausente (a grafia deve ser exata): {nome}")
    return nomes


def estudo_colaboracao(grafo, nomes):
    origem = nomes[ORIGEM]
    distancias, pais = dijkstra(grafo, origem)
    por_indice = {indice: nome for nome, indice in nomes.items()}
    linhas = ["# Rede de colaboração", "", f"Origem: {ORIGEM}", "",
              "| pesquisador | distância | caminho mínimo |", "|---|---|---|"]
    for nome in DESTINOS:
        destino = nomes[nome]
        caminho = reconstruir_caminho(pais, origem, destino)
        rota = " → ".join(por_indice.get(v, f"vértice {v}") for v in caminho)
        linhas.append(f"| {nome} | {formatar_distancia(distancias[destino])} | {rota or 'sem caminho'} |")
    return "\n".join(linhas) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("grafo")
    parser.add_argument("pesquisadores", help="JSON UTF-8 no formato {nome: índice}")
    parser.add_argument("--saida", default="colaboracao_p2.md")
    args = parser.parse_args()
    grafo = ler_grafo(args.grafo, ponderado=True)
    nomes = ler_pesquisadores(args.pesquisadores, grafo)
    resultado = estudo_colaboracao(grafo, nomes)
    with open(args.saida, "w", encoding="utf-8") as arquivo:
        arquivo.write(resultado)
    print(f"Resultados salvos em {args.saida}")


if __name__ == "__main__":
    main()
