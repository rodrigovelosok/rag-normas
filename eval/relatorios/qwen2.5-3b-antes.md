# Avaliação das respostas — qwen2.5:3b

Data: 2026-10-08 · modelo de chat: `qwen2.5:3b` · k = 4 · constante do RRF: 60 · limiar de recusa: 0,52

| Grupo | Perguntas | Corretas | Itens | Citações | Busca | Recusas indevidas | Respostas indevidas | Citações inexistentes | Tempo médio (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Fatos pontuais | 5 | 4 | 90% | 100% | 100% | 0 | 0 | 0 | 66,6 |
| Listas e definições | 5 | 2 | 72% | 80% | 80% | 0 | 0 | 0 | 104,8 |
| Combinação de normas | 3 | 0 | 56% | 33% | 50% | 0 | 0 | 0 | 92,2 |
| Difíceis | 3 | 0 | 43% | 78% | 100% | 0 | 0 | 0 | 99,5 |
| Fora do corpus | 5 | 4 | — | — | — | 0 | 1 | 0 | 18,7 |
| Total | 21 | 10 | 69% | 77% | 84% | 0 | 1 | 0 | 72,7 |

**Legenda.** *Corretas*: respondeu com todos os itens do gabarito, citou todos os artigos esperados e não citou nenhum inexistente (nas perguntas fora do corpus: recusou). *Itens*: fração dos pontos do gabarito presentes na resposta. *Citações*: fração dos artigos esperados que o modelo citou. *Busca*: fração dos artigos esperados entre os recuperados. *Recusas indevidas*: recusou o que o corpus responde. *Respostas indevidas*: respondeu o que devia recusar.

## Falhas

- **Q01** (Combinação de normas): faltou: os dois limites ao mesmo tempo · citou 50% dos artigos esperados
- **Q04** (Listas e definições): faltou: bens da Fazenda pública e de autarquias/fundações; empresa com falência decretada; instituições em liquidação extrajudicial · citou 0% dos artigos esperados
- **Q06** (Listas e definições): faltou: ordem judicial
- **Q08** (Fatos pontuais): faltou: independe de autorização da RFB
- **Q09** (Listas e definições): faltou: intervalo mínimo de 1 ano
- **Q12** (Combinação de normas): faltou: no prazo de cinco dias · citou 0% dos artigos esperados
- **Q13** (Combinação de normas): faltou: o limite foi alterado por decreto; o limite atual é R$ 2 milhões · citou 50% dos artigos esperados
- **Q14** (Difíceis): faltou: bens de dependentes não entram; arrolam-se os adquiridos na constância da união; união estável: vale o contrato escrito por escritura pública · citou 33% dos artigos esperados
- **Q15** (Difíceis): faltou: o arrolado por solidariedade fica limitado ao débito; subsidiária (CTN 133, II): só bens do sucedido; subsidiária (CTN 134): bens do responsável só se insuficientes os do devedor
- **Q16** (Difíceis): faltou: vale mesmo que o principal não se enquadre nos requisitos; pode ser feito já no primeiro momento do arrolamento
- **Q20** (Fora do corpus): respondeu em vez de recusar (similaridade máxima 0,53)
