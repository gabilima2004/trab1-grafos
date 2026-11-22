import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import benchmark_p3 as bench
from distancias_amostrais_p3 import calcular


class BenchmarkParte3(TestCase):
    def argumentos(self, pasta, algoritmo="bellman_ford", fluxo=False):
        pasta = Path(pasta)
        grafo = pasta / "grafo.txt"
        grafo.write_text("100\n10 20 2\n20 30 -1\n30 100 4\n")
        return SimpleNamespace(grafo=grafo, algoritmo=algoritmo, fluxo=fluxo,
                               saida=pasta / f"{algoritmo}-{fluxo}.json",
                               destino=100, memoria_gib=0.5, confirmar_custo=False)

    def estado(self, args):
        return json.loads(args.saida.read_text(encoding="utf-8"))

    @patch.object(bench, "memoria_disponivel", return_value=2 * bench.GIB)
    def test_interrompe_e_retoma_sem_contar_rodada_incompleta(self, _):
        with TemporaryDirectory() as pasta:
            args = self.argumentos(pasta)
            executar = bench.bellman_ford
            reverso = bench.ler_grafo_csr(args.grafo, direcionado=True, transposto=True)
            primeira = executar(reverso, 100, transposto=reverso)
            with patch.object(bench, "bellman_ford", side_effect=[primeira, KeyboardInterrupt()]):
                self.assertEqual(bench.rodar(args), 130)
            interrompido = self.estado(args)
            self.assertEqual(interrompido["estado"], "interrompido")
            self.assertEqual(len(interrompido["tempos_s"]), 1)
            self.assertIsNone(interrompido["media_s"])
            with patch.object(bench, "bellman_ford", wraps=executar) as chamadas:
                self.assertEqual(bench.rodar(args), 0)
                self.assertEqual(chamadas.call_count, 9)
            final = self.estado(args)
            self.assertEqual(final["estado"], "concluido")
            self.assertEqual(final["tempos_s"][:1], interrompido["tempos_s"])
            self.assertEqual(len(final["tempos_s"]), 10)
            self.assertEqual(final["media_s"], bench.mean(final["tempos_s"]))
            self.assertEqual(len(final["eventos"]), 1)
            with patch.object(bench, "bellman_ford") as chamadas:
                self.assertEqual(bench.rodar(args), 0)
                chamadas.assert_not_called()
            args.grafo.write_text("100\n10 20 3\n")
            with self.assertRaisesRegex(ValueError, "Checkpoint incompativel"):
                bench.rodar(args)

    @patch.object(bench, "memoria_disponivel", return_value=2 * bench.GIB)
    def test_memoria_insuficiente_antes_de_carregar(self, _):
        with TemporaryDirectory() as pasta:
            args = self.argumentos(pasta, "floyd_warshall")
            args.grafo.write_text("25000\n")
            with patch.object(bench, "ler_grafo_csr") as ler:
                self.assertEqual(bench.rodar(args), 1)
                ler.assert_not_called()
            estado = self.estado(args)
            self.assertEqual(estado["eventos"][0]["tipo"], "MemoryError")
            self.assertEqual(estado["tempos_s"], [])
            self.assertIsNone(estado["media_s"])

    @patch.object(bench, "memoria_disponivel", return_value=2 * bench.GIB)
    def test_todos_os_pares_denso_e_em_fluxo(self, _):
        with TemporaryDirectory() as pasta:
            amostras = []
            for algoritmo, fluxo in (("floyd_warshall", False),
                                     ("bellman_ford_todos_pares", False),
                                     ("bellman_ford_todos_pares", True)):
                args = self.argumentos(pasta, algoritmo, fluxo)
                self.assertEqual(bench.rodar(args), 0)
                estado = self.estado(args)
                self.assertEqual(len(estado["tempos_s"]), 10)
                amostras.append(estado["amostra"])
            self.assertEqual(amostras[0], amostras[1])
            self.assertEqual(amostras[1], amostras[2])
            self.assertEqual(amostras[0]["matriz"][0][2], 1)
            self.assertEqual(amostras[0]["matriz"][2][0], "inf")


class DistanciasAmostraisParte3(TestCase):
    def test_bellman_ford_conferido_com_dijkstra(self):
        with TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "grafo.txt"
            arquivo.write_text("50\n10 20 2\n20 30 5\n10 30 9\n")
            tabela = calcular(arquivo, "python", None)
            self.assertEqual(len(tabela), 25)
            self.assertEqual(tabela[10, 30], (7, "dijkstra_python"))
            self.assertEqual(tabela[30, 10], (float("inf"), "dijkstra_python"))

    def test_certificado_confere_so_os_pares_afetados(self):
        with TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "grafo.txt"
            arquivo.write_text("50\n10 11 2\n11 12 -2\n12 11 1\n12 20 4\n")
            tabela = calcular(arquivo, "python", [11, 12, 11])
            self.assertEqual(tabela[10, 20], (float("-inf"), "ciclo_negativo_e_alcance"))
            self.assertEqual(tabela[20, 10], (float("inf"), "nenhuma"))
            with self.assertRaisesRegex(ValueError, "Arco ausente"):
                calcular(arquivo, "python", [11, 20, 11])
