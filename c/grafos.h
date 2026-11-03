/* Motor C da biblioteca de grafos (parte 2).
 *
 * Lê grafos ponderados (.txt ou .txt.gz) para o formato CSR e executa
 * Dijkstra com duas filas de prioridade intercambiáveis (vetor e heap
 * binário indexado) no mesmo laço. É chamado pelo Python em motor_c.py
 * (ctypes) sobre os mesmos vetores CSR de grafo_csr.py.
 *
 * Vértices são numerados de 1 a n; a posição 0 dos vetores não é usada.
 */
#ifndef GRAFOS_H
#define GRAFOS_H

#include <stddef.h>
#include <stdint.h>

enum {
    GR_OK = 0,
    GR_ERRO_ARQUIVO = 1,  /* não foi possível abrir ou descompactar */
    GR_ERRO_FORMATO = 2,  /* linha inválida; a mensagem traz o número da linha */
    GR_ERRO_MEMORIA = 3,
    GR_ERRO_ORIGEM = 4,
    GR_ERRO_FILA = 5
};

enum { GR_FILA_VETOR = 0, GR_FILA_HEAP = 1 };

/* Arestas lidas do arquivo, antes de montar o CSR. */
typedef struct GrLeitura GrLeitura;

/* Etapa 1 da leitura: lê o arquivo inteiro (texto ou gzip).
 * Devolve NULL em caso de erro, com o código em *codigo e a mensagem em erro. */
GrLeitura *gr_ler_arestas(const char *caminho, int *codigo, char *erro, size_t tamanho_erro);
int32_t gr_leitura_vertices(const GrLeitura *leitura);
int64_t gr_leitura_arestas(const GrLeitura *leitura);

/* Etapa 2: preenche vetores alocados pelo chamador, que fica dono da memória:
 * inicio com n + 2 posições; adjacentes e pesos com 2m posições.
 * Cada aresta aparece nas duas direções, na ordem do arquivo. */
int gr_montar_csr(const GrLeitura *leitura, int64_t *inicio, int32_t *adjacentes, double *pesos);
void gr_liberar_leitura(GrLeitura *leitura);

/* Dijkstra a partir de origem. dist e pai têm n + 1 posições. Inalcançáveis
 * ficam com dist = +inf; a origem e os inalcançáveis ficam com pai = 0.
 * Pesos negativos devem ser recusados antes da chamada (motor_c.py verifica
 * o grafo uma vez, ao montá-lo). Em empates, sai primeiro o menor vértice.
 *
 * limite_segundos > 0 interrompe a execução nesse prazo (execução parcial,
 * usada para estimar o tempo de execuções longas demais); 0 executa até o fim.
 * extracoes e segundos, se não forem NULL, recebem o número de vértices
 * extraídos da fila e o tempo medido dentro do C. */
int gr_dijkstra(int32_t n, const int64_t *inicio, const int32_t *adjacentes,
                const double *pesos, int32_t origem, int fila,
                double *dist, int32_t *pai, double limite_segundos,
                int64_t *extracoes, double *segundos);

/* Compilador e opções usadas no build (registrados com os resultados). */
const char *gr_compilacao(void);

#endif
