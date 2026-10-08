# Avaliação das respostas — qwen2.5:3b

Data: 2026-10-08 · modelo de chat: `qwen2.5:3b` · k = 4 · constante do RRF: 5 · limiar de recusa: 0,56

| Grupo | Perguntas | Corretas | Itens | Citações | Busca | Recusas indevidas | Respostas indevidas | Citações inexistentes | Tempo médio (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Fatos pontuais | 5 | 4 | 90% | 100% | 100% | 0 | 0 | 0 | 46,1 |
| Listas e definições | 5 | 3 | 84% | 90% | 100% | 0 | 0 | 0 | 57,2 |
| Combinação de normas | 3 | 0 | 56% | 67% | 83% | 0 | 0 | 0 | 76,5 |
| Difíceis | 3 | 0 | 43% | 78% | 100% | 0 | 0 | 0 | 74,0 |
| Fora do corpus | 5 | 5 | — | — | — | 0 | 0 | 0 | 0,0 |
| Total | 21 | 12 | 73% | 86% | 97% | 0 | 0 | 0 | 46,1 |

**Legenda.** *Corretas*: respondeu com todos os itens do gabarito, citou todos os artigos esperados e não citou nenhum inexistente (nas perguntas fora do corpus: recusou). *Itens*: fração dos pontos do gabarito presentes na resposta. *Citações*: fração dos artigos esperados que o modelo citou. *Busca*: fração dos artigos esperados entre os recuperados. *Recusas indevidas*: recusou o que o corpus responde. *Respostas indevidas*: respondeu o que devia recusar.

## Falhas

- **Q01** (Combinação de normas): faltou: os dois limites ao mesmo tempo · citou 50% dos artigos esperados
- **Q06** (Listas e definições): faltou: desapropriação; perda total do bem; expropriação judicial (arrematação, adjudicação); ordem judicial · citou 50% dos artigos esperados
- **Q08** (Fatos pontuais): faltou: independe de autorização da RFB
- **Q09** (Listas e definições): faltou: intervalo mínimo de 1 ano
- **Q12** (Combinação de normas): faltou: no prazo de cinco dias; sob pena de medida cautelar fiscal
- **Q13** (Combinação de normas): faltou: o limite foi alterado por decreto · citou 50% dos artigos esperados
- **Q14** (Difíceis): faltou: bens de dependentes não entram; arrolam-se os adquiridos na constância da união; união estável: vale o contrato escrito por escritura pública · citou 33% dos artigos esperados
- **Q15** (Difíceis): faltou: o arrolado por solidariedade fica limitado ao débito; subsidiária (CTN 133, II): só bens do sucedido; subsidiária (CTN 134): bens do responsável só se insuficientes os do devedor
- **Q16** (Difíceis): faltou: vale mesmo que o principal não se enquadre nos requisitos; pode ser feito já no primeiro momento do arrolamento
