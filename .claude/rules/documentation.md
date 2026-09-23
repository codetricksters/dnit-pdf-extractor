# Documentação

## README.md é a porta de entrada

O `README.md` é escrito para quem chega ao projeto sem contexto: o que a
aplicação faz, como colocá-la de pé numa máquina nova e como rodar os testes.
Ele é a única documentação que alguém lê antes de ter o projeto funcionando, por
isso precisa estar correto — um comando desatualizado ali custa a alguém uma hora
de depuração de um problema que não existe.

Seções obrigatórias, nesta ordem:

1. **O que a aplicação faz** — funcionalidades em prosa, do ponto de vista de
   quem usa, não da implementação.
2. **Telas** — os endereços que o usuário abre no navegador.
3. **Requisitos** — versões e dependências de sistema.
4. **Setup em um ambiente novo** — a sequência completa de comandos, do `uv sync`
   até o servidor respondendo, sem passos implícitos.
5. **Testes** — como subir o que eles precisam e como executá-los.
6. **Produção**, **Backups** e **Estrutura do projeto**.

Escreva em **português**, como o resto da documentação do projeto e as mensagens
de commit.

## Quando atualizar

O README entra **na mesma alteração** que muda o comportamento, nunca em uma
passada de documentação depois. Antes de fechar um trabalho, releia o README se a
alteração incluiu qualquer um destes:

| Mudou | O que revisar no README |
|---|---|
| Nova funcionalidade visível ao usuário | *O que a aplicação faz*, e *Telas* se abriu uma rota nova |
| Rota ou tela nova, renomeada ou removida | *Telas* |
| Dependência de sistema (OCR, cliente do banco, binário externo) | *Requisitos* |
| Passo novo para subir o projeto (banco, seed, variável obrigatória) | *Setup em um ambiente novo* |
| Variável de ambiente nova | `.env.example` **e** a tabela em [deployment.md](deployment.md) |
| Forma de rodar os testes (serviço, porta, banco, marcador) | *Testes* |
| Migração, volume, porta ou serviço do Compose | *Setup*, *Produção* ou *Estrutura do projeto* |
| Arquivo ou diretório de primeiro nível criado ou removido | *Estrutura do projeto* |

Mudança interna que não altera nenhum desses pontos — refatoração, correção de
cálculo, teste novo — não mexe no README.

## Como verificar

Os comandos do README são copiados e colados por quem nunca rodou o projeto, então
eles têm de funcionar nessa condição, não na máquina de quem os escreveu. Ao
alterar a seção de setup ou de testes, execute a sequência como está escrita — do
ambiente mais limpo que for possível — em vez de conferir apenas pela leitura.

Não descreva no README o que não existe: nenhum comando, variável, rota ou arquivo
deve aparecer ali sem estar no código. Se algo é planejado e não implementado, ou
fica fora do README, ou é marcado explicitamente como pendente.

## Os documentos de regras

As regras em `.claude/rules/` são documentação de implementação, com público
diferente do README: quem já tem o projeto rodando e vai mexer no código. Mesmo
critério de atualização — na mesma alteração que muda o comportamento — e mesma
proibição de descrever o que não existe. Quando um detalhe serve aos dois
públicos, ele fica na regra e o README aponta para lá, sem duplicar.
