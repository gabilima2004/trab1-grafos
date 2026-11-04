import gzip
import random
import tempfile
import unittest
from math import inf
from pathlib import Path

import numpy as np

import motor_c
from caminhos_minimos import FILAS, dijkstra, reconstruir_caminho, salvar_caminhos
from entrada_saida import ler_grafo
from grafo import Grafo
from grafo_csr import GrafoCSR, ler_grafo_csr, montar_csr

EXEMPLO_ENUNCIADO = "5\n1 2 0.1\n2 5 0.2\n5 3 5\n3 4 -9.5\n4 5 2.3\n1 5 1\n"
PESOS = (0, 0.25, 1, 2.5, 9)
precisa_c = unittest.skipUnless(motor_c.disponivel(), "motor C não compilado (rode make)")


def grafo_aleatorio(rng, n, m, pesos=PESOS):
    return [(rng.randint(1, n), rng.randint(1, n), rng.choice(pesos)) for _ in range(m)]


def montar_os_dois(n, arestas):
    lista = Grafo(n, "lista", ponderado=True)
    for u, v, peso in arestas:
        lista.adicionar_aresta(u, v, peso)
    if arestas:
        u, v, w = zip(*arestas)
    else:
        u = v = w = ()
    return lista, montar_csr(n, u, v, w)


def como_vetores(distancias, pais):
    return (np.array(distancias, dtype=np.float64),
            np.array([0 if p is None else p for p in pais], dtype=np.int32))


def bellman_ford(n, arestas, origem):
    distancias = [inf] * (n + 1)
    distancias[origem] = 0.0
    for _ in range(n - 1):
        for u, v, peso in arestas:
            distancias[v] = min(distancias[v], distancias[u] + peso)
            distancias[u] = min(distancias[u], distancias[v] + peso)
    return distancias


class GrafoCSRTest(unittest.TestCase):
    def test_csr_igual_a_lista_de_adjacencia(self):
        rng = random.Random(7)
        for caso in range(30):
            n = rng.randint(1, 12)
            arestas = grafo_aleatorio(rng, n, rng.randint(0, 30))
            lista, csr = montar_os_dois(n, arestas)
            self.assertEqual(csr.numero_arestas, len(arestas))
            for u in range(1, n + 1):
                self.assertEqual(list(csr.vizinhos_com_pesos(u)), list(lista.vizinhos_com_pesos(u)))
                self.assertEqual(csr.vizinhos(u), lista.vizinhos(u))
                self.assertEqual(csr.grau(u), lista.grau(u))

    def test_dijkstra_python_identico_nas_duas_estruturas(self):
        rng = random.Random(11)
        for _ in range(20):
            n = rng.randint(1, 15)
            arestas = grafo_aleatorio(rng, n, rng.randint(0, 40))
            lista, csr = montar_os_dois(n, arestas)
            for origem in range(1, n + 1):
                for metodo in ("vetor", "heap"):
                    self.assertEqual(dijkstra(csr, origem, metodo), dijkstra(lista, origem, metodo))

    def test_leitura_e_compatibilidade(self):
        grafo = ler_grafo("exemplo_p2.txt", "csr")
        self.assertIsInstance(grafo, GrafoCSR)
        self.assertEqual((grafo.numero_vertices, grafo.numero_arestas), (6, 7))
        distancias, pais = dijkstra(grafo, 1)
        self.assertEqual(reconstruir_caminho(pais, 1, 3), [1, 2, 5, 4, 3])
        self.assertEqual(distancias[6], inf)
        self.assertEqual(grafo.bytes_ocupados(), 8 * 8 + 14 * 12)
        with self.assertRaises(TypeError):
            grafo.adicionar_aresta(1, 2, 1.0)
        with self.assertRaises(ValueError):
            ler_grafo("exemplo_p2.txt", "csr", ponderado=False)
        with self.assertRaises(ValueError):
            GrafoCSR(2, [0, 0, 1, 1], [3], [1.0])

    def test_negativo_do_enunciado_recusado(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "enunciado.txt"
            arquivo.write_text(EXEMPLO_ENUNCIADO, encoding="utf-8")
            leitores = [lambda: ler_grafo(arquivo, "lista"), lambda: ler_grafo(arquivo, "matriz"),
                        lambda: ler_grafo_csr(arquivo)]
            if motor_c.disponivel():
                leitores.append(lambda: ler_grafo_csr(arquivo, "c"))
            for ler in leitores:
                grafo = ler()
                self.assertTrue(grafo.tem_peso_negativo)
                for metodo in ("vetor", "heap"):
                    with self.assertRaisesRegex(ValueError, "pesos negativos"):
                        dijkstra(grafo, 1, metodo)
                    if isinstance(grafo, GrafoCSR) and motor_c.disponivel():
                        with self.assertRaisesRegex(ValueError, "pesos negativos"):
                            motor_c.dijkstra_c(grafo, 1, metodo)


class GuardaDeTomadaTest(unittest.TestCase):
    def test_espera_a_tomada_e_repete_medicao_que_pegou_bateria(self):
        import threading
        import time
        from experimentos_p2 import GuardaDeTomada
        with tempfile.TemporaryDirectory() as pasta:
            online = Path(pasta) / "online"
            online.write_text("1\n")
            avisos = []
            guarda = GuardaDeTomada(online, avisar=lambda *a, **k: avisos.append(a[0]), intervalo=0.05)
            self.assertEqual(guarda.medir(lambda: 42, "rápida"), 42)
            self.assertEqual(guarda.repeticoes, 0)

            chamadas = []

            def medicao_com_queda():
                chamadas.append(1)
                if len(chamadas) == 1:
                    online.write_text("0\n")
                    time.sleep(1.3)
                    online.write_text("1\n")
                return len(chamadas)

            self.assertEqual(guarda.medir(medicao_com_queda, "longa"), 2)
            self.assertEqual(guarda.repeticoes, 1)

            online.write_text("0\n")
            threading.Timer(0.2, lambda: online.write_text("1\n")).start()
            self.assertEqual(guarda.medir(lambda: "ok", "após espera"), "ok")
            self.assertTrue(any("pausadas" in aviso for aviso in avisos))


@precisa_c
class MotorCTest(unittest.TestCase):
    def test_c_igual_ao_python_e_a_bellman_ford(self):
        rng = random.Random(2026)
        for caso in range(40):
            n = rng.randint(1, 12)
            arestas = grafo_aleatorio(rng, n, rng.randint(0, 35))
            lista, csr = montar_os_dois(n, arestas)
            for origem in range(1, n + 1):
                esperado = bellman_ford(n, arestas, origem)
                referencia = como_vetores(*dijkstra(lista, origem, "heap"))
                for metodo in ("vetor", "heap"):
                    distancias, pais = motor_c.dijkstra_c(csr, origem, metodo)
                    self.assertEqual(distancias.tolist(), esperado)
                    self.assertTrue(np.array_equal(distancias, referencia[0]))
                    self.assertTrue(np.array_equal(pais, referencia[1]))
                    for destino in range(1, n + 1):
                        caminho = reconstruir_caminho(pais, origem, destino)
                        if esperado[destino] == inf:
                            self.assertEqual(caminho, [])
                            continue
                        soma = 0.0
                        for u, v in zip(caminho, caminho[1:]):
                            soma += min(p for w, p in csr.vizinhos_com_pesos(u) if w == v)
                        self.assertEqual(soma, distancias[destino])

    def test_grafo_maior_com_empates(self):
        rng = random.Random(5)
        n = 3000
        arestas = grafo_aleatorio(rng, n, 12000, pesos=(0, 1, 2, 3))
        _, csr = montar_os_dois(n, arestas)
        for origem in rng.sample(range(1, n + 1), 3):
            referencia = como_vetores(*dijkstra(csr, origem, "heap"))
            self.assertTrue(all(np.array_equal(a, b) for a, b in
                                zip(referencia, como_vetores(*dijkstra(csr, origem, "vetor")))))
            for metodo in ("vetor", "heap"):
                resultado = motor_c.dijkstra_c(csr, origem, metodo)
                self.assertTrue(all(np.array_equal(a, b) for a, b in zip(referencia, resultado)))

    def test_contagem_de_operacoes_igual_ao_python(self):
        class Contadora:
            def __init__(self, classe):
                self.classe, self.atualizacoes, self.extracoes = classe, 0, 0

            def __call__(self, distancias):
                fila = self.classe(distancias)
                atualizar, extrair = fila.atualizar, fila.extrair_minimo

                def contando_atualizar(v):
                    self.atualizacoes += 1
                    atualizar(v)

                def contando_extrair():
                    v = extrair()
                    self.extracoes += v is not None
                    return v

                fila.atualizar, fila.extrair_minimo = contando_atualizar, contando_extrair
                return fila

        rng = random.Random(17)
        for _ in range(15):
            n = rng.randint(1, 40)
            _, csr = montar_os_dois(n, grafo_aleatorio(rng, n, rng.randint(0, 120), pesos=(0, 1, 2, 3)))
            for origem in range(1, n + 1):
                for metodo in ("vetor", "heap"):
                    contadora = Contadora(FILAS[metodo])
                    dijkstra(csr, origem, contadora)
                    execucao = motor_c.executar_c(csr, origem, metodo, contar=True)
                    self.assertEqual((execucao.extracoes, execucao.atualizacoes),
                                     (contadora.extracoes, contadora.atualizacoes))

    def test_leitores_produzem_o_mesmo_csr(self):
        rng = random.Random(3)
        with tempfile.TemporaryDirectory() as pasta:
            texto = "50\n" + "".join(f"{u} {v} {rng.uniform(0, 10)!r}\n"
                                     for u, v, _ in grafo_aleatorio(rng, 50, 400))
            texto += "\n   \n7\t8\t0.5\r\n"
            simples = Path(pasta) / "g.txt"
            simples.write_text(texto, encoding="utf-8")
            compactado = Path(pasta) / "g.txt.gz"
            with gzip.open(compactado, "wt") as saida:
                saida.write(texto)
            referencia = ler_grafo_csr(simples).obter_representacao()
            for arquivo, leitor in ((compactado, "numpy"), (simples, "c"), (compactado, "c")):
                lido = ler_grafo_csr(arquivo, leitor).obter_representacao()
                for a, b in zip(lido, referencia):
                    self.assertTrue(np.array_equal(a, b))
            lista = ler_grafo(simples, "lista")
            csr = ler_grafo_csr(simples, "c")
            for u in range(1, 51):
                self.assertEqual(list(csr.vizinhos_com_pesos(u)), list(lista.vizinhos_com_pesos(u)))

    def test_erros_de_leitura_com_numero_da_linha(self):
        casos = {
            "3\n1 2 0.5\n\n2 3\n": "Linha 4: número de colunas inválido",
            "3\n1 2 0.5\n2 3 1 9\n": "Linha 3: número de colunas inválido",
            "3\n1 2 0.5\n2 4 1\n": "Linha 3: Vértice 4 fora do intervalo 1..3",
            "3\n0 2 0.5\n": "Linha 2: Vértice 0 fora do intervalo 1..3",
            "3\n1 2 nan\n": "Linha 2: O peso deve ser um número real finito",
            "3\n1 2 0.5\n1 3 inf\n": "Linha 3: O peso deve ser um número real finito",
            "3\n1 2 x\n": "Linha 2:",
            "3\n1.5 2 1\n": "Linha 2:",
            "x\n1 2 1\n": "Linha 1:",
        }
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "invalido.txt"
            for texto, mensagem in casos.items():
                arquivo.write_text(texto, encoding="utf-8")
                for leitor in ("numpy", "c"):
                    with self.subTest(texto=texto, leitor=leitor):
                        with self.assertRaisesRegex(ValueError, mensagem):
                            ler_grafo_csr(arquivo, leitor)
            with self.assertRaises(OSError):
                ler_grafo_csr(Path(pasta) / "inexistente.txt", "c")
            arquivo.write_text("4\n", encoding="utf-8")
            for leitor in ("numpy", "c"):
                grafo = ler_grafo_csr(arquivo, leitor)
                self.assertEqual((grafo.numero_vertices, grafo.numero_arestas), (4, 0))
                distancias, pais = motor_c.dijkstra_c(grafo, 2)
                self.assertEqual(distancias.tolist(), [inf, inf, 0.0, inf, inf])
                self.assertEqual(reconstruir_caminho(pais, 2, 3), [])

    def test_validacoes_e_arvore_salva(self):
        grafo = ler_grafo_csr("exemplo_p2.txt", "c")
        for origem in (0, 7):
            with self.assertRaises(ValueError):
                motor_c.dijkstra_c(grafo, origem)
        with self.assertRaises(ValueError):
            motor_c.dijkstra_c(grafo, 1, "inexistente")
        with self.assertRaises(TypeError):
            motor_c.dijkstra_c(ler_grafo("exemplo_p2.txt"), 1)
        distancias, pais, segundos, extracoes, atualizacoes = motor_c.executar_c(grafo, 1, "vetor")
        self.assertGreaterEqual(segundos, 0.0)
        self.assertEqual(extracoes, 5)
        self.assertIsNone(atualizacoes)
        self.assertEqual(reconstruir_caminho(pais, 1, 3), [1, 2, 5, 4, 3])
        self.assertEqual(reconstruir_caminho(pais, 1, 1), [1])
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "arvore.txt"
            salvar_caminhos(arquivo, 1, distancias, pais)
            python = Path(pasta) / "arvore_python.txt"
            salvar_caminhos(python, 1, *dijkstra(grafo, 1))
            self.assertEqual(arquivo.read_text(encoding="utf-8"), python.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
