from entrada_saida import ler_grafo
from estatisticas import (
    num_arestas,
    grau_min,
    grau_max,
    grau_medio,
    mediana
)
from busca import BFS, componentes


def main():
    #nome_arquivo = input("Digite o nome do arquivo do grafo: ")
    nome_arquivo = "teste1.txt"
    #print("\nEscolha a representação do grafo:")
    #print("1 - Lista de adjacência")
    #print("2 - Matriz de adjacência")

    '''opcao = int(input("Opção: "))

    if opcao == 1:
        representacao = "lista"
    elif opcao == 2:
        representacao = "matriz"
    else:
        print("Opção inválida.")
        return'''

    grafo = ler_grafo(nome_arquivo, "lista")

    print("\n--- Grafo ---")
    print("Número de vértices:", grafo.numero_vertices)
    print("Número de arestas:", num_arestas(grafo))

    print("\n--- Estatísticas ---")
    print("Grau mínimo:", grau_min(grafo))
    print("Grau máximo:", grau_max(grafo))
    print("Grau médio:", grau_medio(grafo))
    print("Mediana:", mediana(grafo))

    print("\n--- Representação escolhida ---")
    print(grafo.obter_representacao())

    v_inicial = int(input("\nDigite o vértice inicial da BFS: "))

    pai, nivel = BFS(grafo, v_inicial)

    print("\n--- BFS ---")
    print("Pai:", pai)
    print("Nível:", nivel)

    num_componentes, tamanhos, componentes_grafo = componentes(grafo)

    print("\n--- Componentes conexas ---")
    print("Número de componentes:", num_componentes)

    for i in range(num_componentes):
        print(
            f"Componente {i + 1}: "
            f"tamanho = {tamanhos[i]}, "
            f"vértices = {componentes_grafo[i]}"
        )


if __name__ == "__main__":
    main()