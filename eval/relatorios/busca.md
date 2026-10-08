# Avaliação da busca (sem modelo de chat)

Data: 2026-10-08 · k usado nas tabelas de falhas e de limiar: 4

## Recuperação dos artigos esperados, por k

| k | Fatos pontuais | Listas e definições | Combinação de normas | Difíceis | Total |
|---:|---:|---:|---:|---:|---:|
| 1 | 20% | 40% | 33% | 44% | 33% |
| 2 | 40% | 70% | 33% | 56% | 51% |
| 3 | 80% | 70% | 50% | 100% | 75% |
| 4 | 100% | 80% | 50% | 100% | 84% |
| 5 | 100% | 80% | 83% | 100% | 91% |
| 6 | 100% | 80% | 83% | 100% | 91% |
| 7 | 100% | 80% | 83% | 100% | 91% |
| 8 | 100% | 100% | 83% | 100% | 97% |

## Perguntas em que falta algum artigo esperado entre os k = 4 primeiros

- **Q01** (Combinação de normas): faltou Decreto 7.573/2011, art. 1º
- **Q04** (Listas e definições): faltou IN RFB 2.091/2022, art. 8º
- **Q12** (Combinação de normas): faltou IN RFB 2.091/2022, art. 12

## Similaridade máxima por pergunta (k = 4)

| Pergunta | Grupo | Deve | Similaridade |
|---|---|---|---:|
| Q09 | Listas e definições | responder | 0,746 |
| Q06 | Listas e definições | responder | 0,729 |
| Q16 | Difíceis | responder | 0,725 |
| Q15 | Difíceis | responder | 0,705 |
| Q03 | Listas e definições | responder | 0,699 |
| Q02 | Listas e definições | responder | 0,693 |
| Q07 | Fatos pontuais | responder | 0,692 |
| Q11 | Fatos pontuais | responder | 0,672 |
| Q04 | Listas e definições | responder | 0,670 |
| Q14 | Difíceis | responder | 0,642 |
| Q01 | Combinação de normas | responder | 0,636 |
| Q13 | Combinação de normas | responder | 0,629 |
| Q10 | Fatos pontuais | responder | 0,628 |
| Q05 | Fatos pontuais | responder | 0,626 |
| Q08 | Fatos pontuais | responder | 0,615 |
| Q12 | Combinação de normas | responder | 0,584 |
| Q20 | Fora do corpus | recusar | 0,535 |
| Q18 | Fora do corpus | recusar | 0,504 |
| Q17 | Fora do corpus | recusar | 0,490 |
| Q19 | Fora do corpus | recusar | 0,457 |
| Q21 | Fora do corpus | recusar | 0,358 |

## Limiar de recusa (k = 4)

| Limiar | Recusas indevidas | Respostas indevidas |
|---:|---:|---:|
| 0,40 | 0 de 16 | 4 de 5 |
| 0,42 | 0 de 16 | 4 de 5 |
| 0,44 | 0 de 16 | 4 de 5 |
| 0,46 | 0 de 16 | 3 de 5 |
| 0,48 | 0 de 16 | 3 de 5 |
| 0,50 | 0 de 16 | 2 de 5 |
| 0,52 | 0 de 16 | 1 de 5 |
| 0,54 | 0 de 16 | 0 de 5 |
| 0,56 | 0 de 16 | 0 de 5 |
| 0,58 | 0 de 16 | 0 de 5 |
| 0,60 | 1 de 16 | 0 de 5 |
| 0,62 | 2 de 16 | 0 de 5 |
| 0,64 | 6 de 16 | 0 de 5 |
| 0,66 | 7 de 16 | 0 de 5 |
| 0,68 | 9 de 16 | 0 de 5 |
| 0,70 | 12 de 16 | 0 de 5 |

Limiares sem nenhum erro: de 0,54 a 0,58.
