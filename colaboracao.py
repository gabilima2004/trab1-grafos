"""Consulta da rede de pesquisadores com correspondência exata dos nomes."""

import argparse
import json
import unicodedata

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


def ler_vertices_rede(nome_arquivo, grafo):
    nomes = [None] * (grafo.numero_vertices + 1)
    with open(nome_arquivo, encoding="utf-8-sig") as arquivo:
        for numero_linha, linha in enumerate(arquivo, 1):
            linha = linha.rstrip("\r\n")
            if not linha.strip():
                continue
            texto, virgula, nome = linha.partition(",")
            try:
                if not virgula:
                    raise ValueError("esperado 'índice,nome'.")
                indice = int(texto)
                grafo.validar_vertice(indice)
                if nomes[indice] is not None:
                    raise ValueError(f"índice {indice} repetido.")
            except ValueError as erro:
                raise ValueError(f"Linha {numero_linha}: {erro}") from erro
            nomes[indice] = unicodedata.normalize("NFC", nome)
    return nomes


def indices_exigidos(nomes_por_indice):
    procurados = {nome: [] for nome in (ORIGEM, *DESTINOS)}
    for indice, nome in enumerate(nomes_por_indice):
        if nome in procurados:
            procurados[nome].append(indice)
    for nome, indices in procurados.items():
        if not indices:
            raise ValueError(f"Pesquisador ausente (a grafia deve ser exata): {nome}")
        if len(indices) > 1:
            raise ValueError(f"Nome ambíguo: {nome} aparece nos vértices {indices}")
    return {nome: indices[0] for nome, indices in procurados.items()}


def estudo_colaboracao(grafo, nomes, nomes_por_indice=None, motor="python"):
    origem = nomes[ORIGEM]
    if motor == "c":
        from motor_c import dijkstra_c
        distancias, pais = dijkstra_c(grafo, origem)
    else:
        distancias, pais = dijkstra(grafo, origem)
    if nomes_por_indice is None:
        por_indice = {indice: nome for nome, indice in nomes.items()}
    else:
        por_indice = {v: nome for v, nome in enumerate(nomes_por_indice) if nome is not None}
    linhas = ["# Rede de colaboração", "", f"Origem: {ORIGEM} (vértice {origem})", "",
              "| pesquisador | vértice | distância | arestas | caminho mínimo |", "|---|---|---|---|---|"]
    indices = []
    for nome in DESTINOS:
        destino = nomes[nome]
        caminho = reconstruir_caminho(pais, origem, destino)
        rota = " → ".join(por_indice.get(v, f"vértice {v}") for v in caminho)
        arestas = len(caminho) - 1 if caminho else "-"
        linhas.append(f"| {nome} | {destino} | {formatar_distancia(distancias[destino])} | "
                      f"{arestas} | {rota or 'sem caminho'} |")
        indices.append(f"- {nome}: " + (" → ".join(map(str, caminho)) or "sem caminho"))
    linhas += ["", "Caminhos em índices de vértices:", "", *indices]
    return "\n".join(linhas) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("grafo")
    parser.add_argument("pesquisadores",
                        help='arquivo oficial ("índice,nome" por linha) ou JSON {nome: índice}')
    parser.add_argument("--motor", choices=("python", "c"), default="python",
                        help="o motor C usa a representação CSR")
    parser.add_argument("--saida", default="colaboracao_p2.md")
    args = parser.parse_args()
    grafo = ler_grafo(args.grafo, "csr" if args.motor == "c" else "lista", ponderado=True)
    if args.pesquisadores.endswith(".json"):
        nomes, por_indice = ler_pesquisadores(args.pesquisadores, grafo), None
    else:
        por_indice = ler_vertices_rede(args.pesquisadores, grafo)
        nomes = indices_exigidos(por_indice)
    resultado = estudo_colaboracao(grafo, nomes, por_indice, args.motor)
    with open(args.saida, "w", encoding="utf-8") as arquivo:
        arquivo.write(resultado)
    print(f"Resultados salvos em {args.saida}")


if __name__ == "__main__":
    main()
