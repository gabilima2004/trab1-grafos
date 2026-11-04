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

const char *gr_compilacao(void);

#endif
