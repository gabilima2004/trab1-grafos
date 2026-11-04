"""Verificação com unittest da biblioteca e dos estudos de caso da parte 2."""

import gzip
import json
import random
import tempfile
import unittest
from math import inf, isclose
from pathlib import Path

from busca import BFS, componentes
from dfs import DFS
from grafo import Grafo
from entrada_saida import ler_grafo
from caminhos_minimos import dijkstra, reconstruir_caminho, salvar_caminhos
from prioridades import HeapIndexado
from experimentos_p2 import estudo_grafo
from colaboracao import ORIGEM, DESTINOS, ler_pesquisadores, estudo_colaboracao


class Parte2Test(unittest.TestCase):
    def test_exemplo_e_arvore(self):
        for representacao in ("lista", "matriz"):
            grafo = ler_grafo("exemplo_p2.txt", representacao)
            for metodo in ("vetor", "heap"):
                distancias, pais = dijkstra(grafo, 1, metodo)
                self.assertTrue(isclose(distancias[3], 4.1))
                self.assertEqual(reconstruir_caminho(pais, 1, 3), [1, 2, 5, 4, 3])
                self.assertEqual(distancias[6], inf)
                self.assertEqual(reconstruir_caminho(pais, 1, 6), [])
                self.assertEqual(reconstruir_caminho(pais, 1, 1), [1])
            self.assertEqual(set(BFS(grafo, 1)[1]), {1, 2, 3, 4, 5})
            self.assertEqual(set(DFS(grafo, 1)[1]), {1, 2, 3, 4, 5})
            self.assertEqual(componentes(grafo)[1], [5, 1])

    def test_heap_decrease_key_e_posicoes(self):
        rng = random.Random(242)
        distancias = [inf] * 101
        heap = HeapIndexado(distancias)
        ativos = set()
        for _ in range(1000):
            if ativos and rng.random() < 0.3:
                esperado = min(ativos, key=lambda v: (distancias[v], v))
                self.assertEqual(heap.extrair_minimo(), esperado)
                ativos.remove(esperado)
            else:
                v = rng.randint(1, 100)
                distancias[v] = rng.random() * 100 if v not in ativos else distancias[v] - rng.random()
                heap.atualizar(v)
                ativos.add(v)
            self.assertEqual(len(heap.heap), len(ativos))
            for i, v in enumerate(heap.heap):
                self.assertEqual(heap.posicao[v], i)
                if i:
                    self.assertLessEqual((distancias[heap.heap[(i - 1) // 2]], heap.heap[(i - 1) // 2]),
                                         (distancias[v], v))

    def test_contra_bellman_ford(self):
        # Oráculo independente: relaxa todas as arestas n-1 vezes.
        rng = random.Random(2026)
        for caso in range(20):
            n = 9
            arestas = [(rng.randint(1, n), rng.randint(1, n), rng.choice([0, 0.25, 1, 2.5, 9]))
                       for _ in range(caso + 1)]
            for representacao in ("lista", "matriz"):
                grafo = Grafo(n, representacao, ponderado=True)
                for u, v, peso in arestas:
                    grafo.adicionar_aresta(u, v, peso)
                for origem in range(1, n + 1):
                    esperado = [inf] * (n + 1)
                    esperado[origem] = 0.0
                    for _ in range(n - 1):
                        for u, v, peso in arestas:
                            esperado[v] = min(esperado[v], esperado[u] + peso)
                            esperado[u] = min(esperado[u], esperado[v] + peso)
                    for metodo in ("vetor", "heap"):
                        distancias, pais = dijkstra(grafo, origem, metodo)
                        self.assertEqual(distancias, esperado)
                        for destino in range(1, n + 1):
                            caminho = reconstruir_caminho(pais, origem, destino)
                            if esperado[destino] == inf:
                                self.assertEqual(caminho, [])
                            else:
                                soma = sum(min(p for vizinho, p in grafo.vizinhos_com_pesos(u) if vizinho == v)
                                           for u, v in zip(caminho, caminho[1:]))
                                self.assertEqual(soma, esperado[destino])

    def test_negativos_inclusive_componente_desconectada(self):
        for representacao in ("lista", "matriz"):
            grafo = Grafo(4, representacao, ponderado=True)
            grafo.adicionar_aresta(3, 4, -9.5)
            self.assertIn((4, -9.5), list(grafo.vizinhos_com_pesos(3)))
            for metodo in ("vetor", "heap"):
                with self.assertRaisesRegex(ValueError, "pesos negativos"):
                    dijkstra(grafo, 1, metodo)

    def test_leitura_validacao_e_compatibilidade(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "grafo.txt"
            arquivo.write_text("3\n1 2\n2 3\n", encoding="utf-8")
            grafo = ler_grafo(arquivo)
            self.assertFalse(grafo.ponderado)
            self.assertEqual(grafo.vizinhos(2), [1, 3])
            self.assertEqual(dijkstra(grafo, 1)[0][3], 2)
            for texto in ("3\n1 2 0\n2 3\n", "3\n1 4 2\n", "3\n1 2 nan\n", "3\n1 2 inf\n"):
                arquivo.write_text(texto, encoding="utf-8")
                with self.assertRaises(ValueError):
                    ler_grafo(arquivo)
            compactado = Path(pasta) / "grafo.txt.gz"
            with gzip.open(compactado, "wt") as saida:
                saida.write("3\n1 2 0\n2 3 0\n")
            grafo = ler_grafo(compactado, "matriz")
            self.assertEqual(dijkstra(grafo, 1)[0][3], 0)
            self.assertIn(2, grafo.vizinhos(1))
            for origem in (0, 4):
                with self.assertRaises(ValueError):
                    dijkstra(grafo, origem)
            with self.assertRaises(ValueError):
                dijkstra(grafo, 1, "inexistente")
            salvar_caminhos(arquivo, 1, *dijkstra(grafo, 1))
            self.assertIn("3 2 0.0", arquivo.read_text(encoding="utf-8"))

    def test_estudos_e_nomes_exatos(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "ponderado.txt"
            arquivo.write_text("60\n" + "".join(f"{i} {i+1} 0.5\n" for i in range(1, 60)), encoding="utf-8")
            resultado = estudo_grafo(arquivo, k=2)
            self.assertIn("| 10 | 20 | 5 |", resultado)
            self.assertIn("| vetor |", resultado)
            self.assertIn("| heap |", resultado)
            grafo = ler_grafo(arquivo)
            nomes = {nome: i for i, nome in enumerate((ORIGEM, *DESTINOS), 1)}
            pesquisadores = Path(pasta) / "nomes.json"
            pesquisadores.write_text(json.dumps(nomes, ensure_ascii=False), encoding="utf-8")
            lidos = ler_pesquisadores(pesquisadores, grafo)
            self.assertIn("Éva Tardos", estudo_colaboracao(grafo, lidos))
            nomes["Eva Tardos"] = nomes.pop("Éva Tardos")
            pesquisadores.write_text(json.dumps(nomes), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "grafia"):
                ler_pesquisadores(pesquisadores, grafo)


if __name__ == "__main__":
    unittest.main()
