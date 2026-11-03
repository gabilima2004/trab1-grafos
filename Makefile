# Motor C (c/libgrafos.so), carregado por motor_c.py via ctypes.
#   make          compila a biblioteca
#   make testes   roda os testes com o Python do ambiente virtual
#   make limpar   apaga a biblioteca compilada
#
# -march=native otimiza para o processador local (inclui instruções SIMD);
# -ffp-contract=off impede que somas virem operações fundidas, mantendo as
# distâncias idênticas às do Python bit a bit; -fopenmp-simd ativa o
# "#pragma omp simd" da varredura do vetor (sem threads nem runtime OpenMP).

CC ?= gcc
CFLAGS ?= -O2 -march=native
OPCOES = -std=gnu11 -Wall -Wextra -fPIC -ffp-contract=off -fopenmp-simd
PYTHON ?= .venv/bin/python

c/libgrafos.so: c/grafos.c c/grafos.h
	$(CC) $(CFLAGS) $(OPCOES) -DGR_OPCOES='"$(CFLAGS) $(OPCOES)"' -shared -o $@ c/grafos.c -lz -lm

.PHONY: testes limpar
testes: c/libgrafos.so
	$(PYTHON) -m unittest -v test_parte2 test_motor_c

limpar:
	rm -f c/libgrafos.so
