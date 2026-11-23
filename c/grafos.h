#ifndef GRAFOS_H
#define GRAFOS_H

#include <stddef.h>
#include <stdint.h>

enum {
    GR_OK = 0,
    GR_ERRO_ARQUIVO = 1,
    GR_ERRO_FORMATO = 2,
    GR_ERRO_MEMORIA = 3,
    GR_ERRO_ORIGEM = 4,
    GR_ERRO_FILA = 5
};

enum { GR_FILA_VETOR = 0, GR_FILA_HEAP = 1 };

typedef struct GrLeitura GrLeitura;

GrLeitura *gr_ler_arestas(const char *caminho, int *codigo, char *erro, size_t tamanho_erro);
int32_t gr_leitura_vertices(const GrLeitura *leitura);
int64_t gr_leitura_arestas(const GrLeitura *leitura);

int gr_montar_csr(const GrLeitura *leitura, int64_t *inicio, int32_t *adjacentes, double *pesos);
void gr_liberar_leitura(GrLeitura *leitura);

int gr_dijkstra(int32_t n, const int64_t *inicio, const int32_t *adjacentes,
                const double *pesos, int32_t origem, int fila,
                double *dist, int32_t *pai, double limite_segundos,
                int64_t *extracoes, int64_t *atualizacoes, double *segundos);

int gr_montar_csr_direcionado(const GrLeitura *leitura, int transposto, int64_t *inicio,
                              int32_t *adjacentes, double *pesos);

enum { GR_INF_INTEIRO = 0x3FFFFFFF, GR_NEG_INTEIRO = -0x3FFFFFFF };

int gr_floyd_warshall_classico(int32_t n, const int64_t *inicio, const int32_t *adjacentes,
                               const double *pesos, double *dist, int32_t *pred, int threads);

int gr_floyd_warshall_blocado(int32_t n, const int64_t *inicio, const int32_t *adjacentes,
                              const double *pesos, double escala, int32_t *dist, void *pred,
                              int pred16, int32_t bloco, int threads);

int gr_bellman_ford(int32_t n, const int64_t *inicio, const int32_t *adjacentes,
                    const double *pesos, int32_t destino, double *dist, int32_t *sucessor,
                    int32_t *ciclo);

int gr_bellman_ford_todos(int32_t n, const int64_t *inicio, const int32_t *adjacentes,
                          const double *pesos, double *dist, int32_t *ciclo, int threads);

int gr_johnson(int32_t n, const int64_t *inicio, const int32_t *adjacentes,
               const double *pesos, const double *potencial, double *dist, int32_t *pred,
               int threads);

const char *gr_compilacao(void);

#endif
