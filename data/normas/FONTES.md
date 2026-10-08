# Procedência do corpus

Registro de onde vem cada texto em `data/normas/`, para o leitor saber o que o `rag-normas` está citando.

## IN RFB nº 2.091/2022 — `in-rfb-2091-2022.txt`

| Item | Valor |
|---|---|
| Norma | Instrução Normativa RFB nº 2091, de 22 de junho de 2022 (DOU de 23/06/2022, seção 1, p. 60) |
| Versão | **Texto vigente (multivigente)**, com as alterações incorporadas |
| Alterada por | IN RFB nº 2122, de 15/12/2022 · IN RFB nº 2338, de 10/08/2026 |
| Fonte | Site de normas da Receita Federal; texto copiado pelo autor do projeto |
| Data da cópia | 07/10/2026 |

**Tratamento do texto:**

- Conteúdo normativo preservado como na fonte, inclusive um erro de pontuação no art. 13 ("art. 12., com").
- As marcações de alteração que o site mostra ao lado de cada dispositivo foram convertidas em colchetes ao
  fim do dispositivo, por exemplo `[Redação dada pela IN RFB nº 2338/2026]` e `[Incluído pela IN RFB nº 2122/2022]`.
- Ficaram de fora o cabeçalho de navegação do site e o histórico de alterações em lista.

**Limitação conhecida:** o **Anexo Único** (formulário de comunicação de alienação, citado no art. 12, § 1º)
não consta do texto copiado, então o assistente não consegue descrevê-lo.

## Lei nº 9.532/1997, arts. 64 e 64-A — `lei-9532-1997-arts-64-64a.txt`

| Item | Valor |
|---|---|
| Norma | Lei nº 9.532, de 10 de dezembro de 1997, apenas os arts. 64 e 64-A |
| Fonte | Portal da Legislação do Planalto: <https://www.planalto.gov.br/ccivil_03/leis/l9532.htm> |
| Data da cópia | 07/10/2026 |
| Alterada por | MP 2.158-35/2001, Lei 11.941/2009, Lei 12.973/2014, Lei 13.043/2014, LC 187/2021 |

**Tratamento do texto:**

- Extraído da página oficial por script, removendo o texto **riscado** (redações revogadas: o parágrafo único
  original do art. 64-A e a redação da MP 449/2008 para o § 1º do art. 64, que não vigora).
- Sobrou da página uma linha órfã do inciso II da MP 449/2008; foi removida à mão.
- As anotações de alteração do Planalto foram convertidas para colchetes no fim do dispositivo, como
  `[Incluído pela Lei nº 12.973/2014]`. Os dispositivos originais de 1997 ficam sem marcação.
- Os parágrafos foram unidos em uma linha cada (a página quebra o texto no meio das frases).

**Conferência pelo autor (08/10/2026):** § 1º do art. 64 (redação original, sobre o cônjuge) confirmado como o
vigente. O texto foi comparado com a impressão do Planalto de 03/12/2020: coincide, exceto pelo § 13 do art. 64
(fundações; LC 187/2021), que é posterior a essa impressão e está presente aqui por ter sido extraído da página
atual.

**Atenção — valor de corte:** o § 7º do art. 64 fala em R$ 500.000,00, mas o limite aplicado pela IN 2.091 é de
R$ 2.000.000,00 (art. 2º, II), elevado pelo Decreto nº 7.573/2011, que **faz parte do corpus** (ver abaixo).

## Decreto nº 7.573/2011 — `decreto-7573-2011.txt`

| Item | Valor |
|---|---|
| Norma | Decreto nº 7.573, de 29 de setembro de 2011 (DOU de 30/09/2011) |
| Efeito | Eleva para R$ 2.000.000,00 o limite do § 7º do art. 64 da Lei 9.532/1997 |
| Fonte | Portal da Legislação do Planalto (impressão de 03/12/2020), fornecida pelo autor do projeto |
| Data da cópia | 08/10/2026 |

**Tratamento do texto:** conteúdo normativo integral (2 artigos). Ficaram de fora a assinatura, a data de
Brasília e o aviso "Este texto não substitui o publicado no DOU".
