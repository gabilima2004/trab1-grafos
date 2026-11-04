import os

for _variavel in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_variavel, "1")

import argparse
import ctypes
import gc
import json
import resource
import subprocess
import sys
from pathlib import Path
from time import perf_counter

from caminhos_minimos import FILAS, dijkstra
from experimentos_p2 import FilaComPrazo, ambiente, contar_alcancados, sem_coleta_de_lixo


def status_kb(campo):
    with open("/proc/self/status", encoding="ascii") as arquivo:
        for linha in arquivo:
            if linha.startswith(campo + ":"):
                return int(linha.split()[1])
    raise RuntimeError(f"{campo} ausente em /proc/self/status")


def zerar_pico_de_memoria():
    with open("/proc/self/clear_refs", "w", encoding="ascii") as arquivo:
        arquivo.write("5")


def devolver_memoria_livre():
    try:
        ctypes.CDLL(None).malloc_trim(0)
    except (OSError, AttributeError):
        pass


def medir(nome, motor, fila, origem, prazo):
    from grafo_csr import ler_grafo_csr
    grafo = ler_grafo_csr(nome, "c")
    gc.collect()
    devolver_memoria_livre()
    base = status_kb("VmRSS")
    zerar_pico_de_memoria()
    uso_antes = resource.getrusage(resource.RUSAGE_THREAD)
    with sem_coleta_de_lixo():
        inicio = perf_counter()
        if motor == "c":
            from motor_c import executar_c
            execucao = executar_c(grafo, origem, fila, limite_segundos=prazo)
            extracoes = execucao.extracoes
            completa = prazo == 0 or execucao.segundos < prazo
        elif prazo:
            fabrica = FilaComPrazo(FILAS[fila], prazo)
            dijkstra(grafo, origem, fabrica)
            extracoes, completa = fabrica.extracoes, not fabrica.interrompida
        else:
            distancias, _ = dijkstra(grafo, origem, fila)
            extracoes, completa = contar_alcancados(distancias), True
        parede = perf_counter() - inicio
    uso_depois = resource.getrusage(resource.RUSAGE_THREAD)
    pico = status_kb("VmHWM")

    def diferenca(campo):
        return getattr(uso_depois, campo) - getattr(uso_antes, campo)

    return {"motor": motor, "fila": fila, "origem": origem, "prazo": prazo, "completa": completa,
            "extracoes": extracoes, "parede": parede, "cpu_usuario": diferenca("ru_utime"),
            "cpu_sistema": diferenca("ru_stime"), "pico_mb": (pico - base) / 1024,
            "residente_antes_mb": base / 1024, "trocas_voluntarias": diferenca("ru_nvcsw"),
            "trocas_involuntarias": diferenca("ru_nivcsw"), "faltas_menores": diferenca("ru_minflt"),
            "faltas_maiores": diferenca("ru_majflt")}


def contar_operacoes(nome, origens):
    import numpy as np
    from grafo_csr import ler_grafo_csr
    from motor_c import executar_c
    grafo = ler_grafo_csr(nome, "c")
    graus = np.diff(grafo.inicio)
    contagens = []
    for origem in origens:
        execucao = executar_c(grafo, origem, "heap", contar=True)
        alcancados = np.isfinite(execucao.distancias)
        contagens.append({"origem": origem, "extracoes": execucao.extracoes,
                          "atualizacoes": execucao.atualizacoes,
                          "arcos_examinados": int(graus[alcancados].sum())})
    return grafo.numero_vertices, grafo.numero_arestas, contagens


def perfil_grafo(nome, pasta_resultados, prazo, origens_contagem):
    titulo = Path(nome).name
    estudo = json.loads((Path(pasta_resultados) / f"{titulo}.json").read_text(encoding="utf-8"))
    origens = estudo["origens"]
    n, m, contagens = contar_operacoes(nome, origens[:origens_contagem])
    print(f"{titulo}: operações contadas em {len(contagens)} origens", flush=True)
    medidas = []
    for configuracao in estudo["configuracoes"]:
        prazo_cfg = 0.0 if configuracao["tempos"] else prazo
        comando = [sys.executable, __file__, "--medir", nome, configuracao["motor"], configuracao["fila"],
                   str(origens[0]), str(prazo_cfg)]
        saida = subprocess.run(comando, capture_output=True, text=True, check=True)
        medida = json.loads(saida.stdout.strip().splitlines()[-1])
        medidas.append(medida)
        print(f"{titulo} [{medida['motor']}-{medida['fila']}] pico {medida['pico_mb']:.0f} MB, "
              f"CPU {medida['cpu_usuario'] + medida['cpu_sistema']:.2f} s de {medida['parede']:.2f} s, "
              f"{'completa' if medida['completa'] else 'parcial'}", flush=True)
    return {"grafo": titulo, "vertices": n, "arestas": m, "contagens": contagens,
            "medidas": medidas, "ambiente": ambiente()}


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--medir":
        nome, motor, fila, origem, prazo = sys.argv[2:7]
        print(json.dumps(medir(nome, motor, fila, int(origem), float(prazo))))
        return
    parser = argparse.ArgumentParser()
    parser.add_argument("grafos", nargs="+")
    parser.add_argument("--prazo", type=float, default=20,
                        help="segundos das execuções parciais (configurações estimadas)")
    parser.add_argument("--origens-contagem", type=int, default=5)
    parser.add_argument("--cpu", type=int, default=None, help="núcleo fixo (herdado pelos filhos)")
    parser.add_argument("--resultados", default="resultados_p2")
    args = parser.parse_args()
    if args.cpu is not None:
        os.sched_setaffinity(0, {args.cpu})
    pasta = Path(args.resultados) / "perfil"
    pasta.mkdir(parents=True, exist_ok=True)
    for nome in args.grafos:
        resultado = perfil_grafo(nome, args.resultados, args.prazo, args.origens_contagem)
        destino = pasta / f"{Path(nome).name}.json"
        destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"Perfil em {destino}", flush=True)


if __name__ == "__main__":
    main()
