# Avaliação das respostas — qwen2.5:7b

Data: 2026-10-08 · modelo de chat: `qwen2.5:7b` · k = 4 · constante do RRF: 5 · limiar de recusa: 0,56

| Grupo | Perguntas | Corretas | Itens | Citações | Busca | Recusas indevidas | Respostas indevidas | Citações inexistentes | Tempo médio (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Fatos pontuais | 5 | 4 | 90% | 100% | 100% | 0 | 0 | 0 | 115,6 |
| Listas e definições | 5 | 2 | 83% | 100% | 100% | 0 | 0 | 0 | 188,6 |
| Combinação de normas | 3 | 1 | 56% | 67% | 83% | 0 | 0 | 0 | 171,3 |
| Difíceis | 3 | 0 | 65% | 78% | 100% | 0 | 0 | 0 | 183,6 |
| Fora do corpus | 5 | 5 | — | — | — | 0 | 0 | 0 | 0,0 |
| Total | 21 | 12 | 77% | 90% | 97% | 0 | 0 | 0 | 123,1 |

**Legenda.** *Corretas*: respondeu com todos os itens do gabarito, citou todos os artigos esperados e não citou nenhum inexistente (nas perguntas fora do corpus: recusou). *Itens*: fração dos pontos do gabarito presentes na resposta. *Citações*: fração dos artigos esperados que o modelo citou. *Busca*: fração dos artigos esperados entre os recuperados. *Recusas indevidas*: recusou o que o corpus responde. *Respostas indevidas*: respondeu o que devia recusar.

## Falhas

- **Q01** (Combinação de normas): faltou: 30% do patrimônio conhecido; os dois limites ao mesmo tempo · citou 50% dos artigos esperados
- **Q03** (Listas e definições): faltou: a ordem pode ser alterada por ato fundamentado
- **Q14** (Difíceis): faltou: bens de dependentes não entram; arrolam-se os adquiridos na constância da união · citou 33% dos artigos esperados
- **Q15** (Difíceis): faltou: o arrolado por solidariedade fica limitado ao débito; subsidiária (CTN 133, II): só bens do sucedido
- **Q16** (Difíceis): faltou: pode ser feito já no primeiro momento do arrolamento
- **Q02** (Listas e definições): faltou: PF: exclui bens de dependentes; PF: inclui bens do cônjuge/companheiro
- **Q08** (Fatos pontuais): faltou: independe de autorização da RFB
- **Q09** (Listas e definições): faltou: petição com laudo ou parecer de avaliação
- **Q13** (Combinação de normas): faltou: o limite foi alterado por decreto; o limite atual é R$ 2 milhões · citou 50% dos artigos esperados
