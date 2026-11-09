# Segurança das skills (SkillSpector)

Toda skill do projeto (`.claude/skills/`) e todo `DESIGN.md` de consulta (`.claude/referencias/`) passa pelo
[SkillSpector](https://github.com/NVIDIA/SkillSpector), o verificador de segurança de skills da NVIDIA. Ele procura
instrução escondida para o agente, vazamento de dados, acesso a senhas e configurações, código perigoso e outros riscos.

- Roda sozinho no workflow [`skills-seguranca.yml`](../../.github/workflows/skills-seguranca.yml): a cada push, a cada
  PR, toda segunda-feira e à mão. Uma skill reprovada deixa o CI vermelho.
- Rodar à mão:
  ```
  pip install "skillspector @ git+https://github.com/NVIDIA/SkillSpector@e48d771a26f7398b36256ceb8d8f94adce3d5c44"
  python .claude/skillspector/verificar_skills.py
  ```
- Só a análise estática (`--no-llm`): não precisa de chave de API nem gasta dinheiro. Ela é rígida e dá alarmes falsos;
  por isso cada achado grave é lido por uma pessoa antes de ser aceito.

## Antes de instalar uma skill nova

1. Copie a skill da fonte oficial (repositório do autor), num commit fixo.
2. Rode `skillspector scan <pasta-da-skill> --no-llm`.
3. Passou (SAFE ou CAUTION): pode instalar.
4. Reprovou: leia cada achado `HIGH` e `CRITICAL`. Se todos forem alarme falso, aceite com
   `skillspector baseline .claude/skills/<skill> --no-llm -o .claude/skillspector/aceitos/<skill>.yaml --reason "<por quê>"`
   e anote abaixo. Se algum for risco de verdade, não instale.

Os achados aceitos valem para aquele texto exato da skill e para aquela versão do SkillSpector. Mudou a skill ou
a versão, o achado volta e precisa de nova revisão.

## Achados aceitos (revisão de 09/11/2026)

| Skill | Fonte | Achados aceitos | O que eram |
|---|---|---|---|
| `design-taste-frontend` | [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill) | 81 | Comentários HTML nos modelos de página lidos como "instrução escondida"; scripts e links que a análise não leu até o fim |
| `impeccable` | [pbakaus/impeccable](https://github.com/pbakaus/impeccable) | 50 | Regras de estilo ("nunca faça X") lidas como "anti-recusa"; leitura de configuração do próprio impeccable; endereços de exemplo |
| `improve-animations` | [emilkowalski/skills](https://github.com/emilkowalski/skills) | 6 | Espaço invisível usado para mostrar blocos de código dentro de blocos de código; a regra "nunca modifique o código-fonte" |
| `playwright-cli` | [microsoft/playwright-cli](https://github.com/microsoft/playwright-cli) (commit `ce9b41b`) | 20 | Links para outros arquivos da skill que a análise não leu até o fim; a dica "nunca grave arquivo de login no git" lida como "memória" |

## Reprovadas e não instaladas

| Skill | Fonte | Motivo |
|---|---|---|
| img2threejs | [img2threejs/img2threejs](https://github.com/img2threejs/img2threejs) | 218 achados (nota 100). O instalador muda a configuração do Claude (`~/.claude`, `permissions.additionalDirectories`) e cria `~/.img2`; a skill serve para modelos 3D, sem uso neste projeto |

## Material de consulta

`.claude/referencias/design-md/`: 84 fichas de visual de marcas, de
[VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md) (commit `fcc7028`, licença MIT). Todas
passaram (SAFE ou CAUTION). Não é skill: o agente só lê quando alguém pedir uma referência. O visual do site continua o
padrão gov.br (ver `CLAUDE.md`).
