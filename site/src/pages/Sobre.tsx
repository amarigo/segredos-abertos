import { MG, SITE } from "../recorte";

/* O que muda no Minas Nossa: o recorte de MG e as páginas das cidades */
function SobreMG() {
  return (
    <>
      <h2>O que é o Minas Nossa</h2>
      <p>É a parte de Minas Gerais do <a href={SITE.nacional}>Segredos Abertos Brasil</a>. Mostra os deputados federais e os senadores eleitos por Minas, com os mesmos dados e as mesmas contas do site nacional, e páginas para cada cidade acompanhada. Os deputados estaduais, o governador e as Câmaras Municipais entram nas próximas etapas.</p>
      <p>Nas votações, o resultado (aprovado ou rejeitado) e o placar são os da Casa inteira. Ao lado mostramos como votou a bancada de Minas. A posição de esquerda e direita de cada parlamentar continua calculada com todos os colegas da Casa, que é a régua certa para comparar.</p>
      <h2>Páginas das cidades</h2>
      <p>Usamos os resultados de todas as eleições desde 1996, publicados pelo <a href="https://dadosabertos.tse.jus.br" target="_blank" rel="noreferrer">Tribunal Superior Eleitoral (TSE)</a>: quem foi eleito prefeito, vice e vereador, por qual partido e coligação, com quantos votos, e como a cidade votou para presidente, governador, senador e deputados.</p>
      <p>Muitos partidos mudaram de nome ou se juntaram a outros: o PMDB virou MDB, o PFL virou DEM e depois União Brasil, o PR voltou a ser PL. Para saber de quem cobrar, mostramos a sigla do dia da eleição e, ao lado, o nome de hoje. As contas de "anos no comando" e "vereadores eleitos" juntam as siglas antigas com a de hoje.</p>
      <p>Os arquivos do TSE trazem CPF, e-mail e outros dados pessoais dos candidatos. Não lemos essas colunas: nada disso é guardado nem aparece no site.</p>
      <h2>Limites das páginas das cidades</h2>
      <ul>
        <li>O partido é o do dia da eleição. Trocas de partido no meio do mandato, cassações, renúncias e suplentes que assumiram não aparecem.</li>
        <li>Ter maioria na eleição não garante maioria o mandato todo: vereadores mudam de lado.</li>
        <li>Eleições suplementares (refeitas no meio do mandato) ficam de fora.</li>
        <li>Se o TSE estiver fora do ar, usamos a última cópia baixada. Se não houver cópia, a página avisa qual eleição ficou de fora.</li>
      </ul>
    </>
  );
}

export default function Sobre() {
  return (
    <section style={{ maxWidth: 720 }}>
      <h1>Como funciona</h1>
      {MG && <SobreMG />}
      <h2>De onde vêm os dados</h2>
      <p>Tudo vem de fontes oficiais e públicas, baixadas automaticamente todos os dias:</p>
      <ul>
        <li><a href="https://dadosabertos.camara.leg.br" target="_blank" rel="noreferrer">Dados Abertos da Câmara dos Deputados</a>: deputados, cota parlamentar (CEAP) e votações.</li>
        <li><a href="https://www12.senado.leg.br/dados-abertos" target="_blank" rel="noreferrer">Dados Abertos do Senado Federal</a>: senadores, cota (CEAPS) e votações.</li>
        <li>Páginas oficiais de cada deputado (camara.leg.br/deputados) e de cada senador (Transparência do Senado): salário, verba de gabinete, equipe e benefícios.</li>
        <li>Receita Federal, base pública de CNPJ: dados das empresas e quadro de sócios. Consultada pelo espelho aberto <a href="https://minhareceita.org" target="_blank" rel="noreferrer">Minha Receita</a>.</li>
      </ul>
      <h2>O que é a cota parlamentar</h2>
      <p>É um valor mensal, além do salário, para pagar despesas do mandato: passagens, aluguel de escritório no estado, combustível, divulgação e outras. O parlamentar paga e pede reembolso com a nota fiscal. O valor muda conforme o estado, porque passagens para Brasília custam diferente.</p>
      <h2>Salário, equipe e benefícios</h2>
      <p>A cota é só uma parte do custo de um mandato. Cada deputado também recebe salário (R$ 46.366,19 brutos por mês desde fevereiro de 2025) e tem uma <strong>verba de gabinete</strong> para pagar até 25 assessores. Os senadores recebem o mesmo salário e têm equipe paga pelo Senado. Também mostramos se o parlamentar usa apartamento funcional, recebe auxílio-moradia ou tem passaporte diplomático. O "custo conhecido" soma salário, equipe, cota e outros gastos que os sites oficiais informam. Não inclui, por exemplo, o salário de servidores concursados que trabalham no gabinete.</p>
      <h2>Por que o total da cota pode ser diferente da página oficial</h2>
      <p>Comparamos todos os deputados e senadores de Minas Gerais com as páginas oficiais, e depois todos os parlamentares do país. No Senado, os totais de Minas batiam exatamente. Na Câmara, nossos valores estavam menores por dois motivos, já corrigidos:</p>
      <ul>
        <li><strong>Somávamos 2025 e 2026 juntos.</strong> As páginas oficiais mostram um ano por vez. Agora o site também mostra um ano por vez, com o seletor de ano no topo.</li>
        <li><strong>Faltavam passagens aéreas a partir de agosto de 2025.</strong> Desde então, os dados abertos da Câmara não trazem as passagens compradas pelo sistema da própria Câmara (SIGEPA), mas a página do deputado soma esses valores. Todas as outras despesas batiam centavo por centavo. Agora buscamos cada bilhete na lista oficial de despesas da Câmara, com a companhia, a data, o número do bilhete e o link para o detalhe. O pouco que ainda não aparece em nenhuma lista fica, mês a mês, numa categoria chamada "Despesas sem nota nos dados abertos", para o total bater com o oficial.</li>
      </ul>
      <p>A página oficial de cada deputado conta só os meses em que ele estava no cargo naquele mandato. Por isso ela não inclui janeiro de 2023 (que ainda era o mandato anterior) nem devoluções de passagens creditadas em meses em que o deputado estava licenciado, por exemplo para ser ministro. Nós mantemos esses valores na soma, porque foram pagos ou devolvidos de fato, e a página do deputado mostra quanto é e de quais meses. Nos meses que a página oficial mostra, os valores batem.</p>
      <p>No Senado, alguns senadores (cerca de 10 por ano) têm reembolsos publicados sem tipo de despesa. A página oficial do Senado não soma esses valores, mas eles foram pagos, então nós somamos e mostramos a diferença na página do senador.</p>
      <p>Se a página oficial for atualizada depois da nossa coleta diária, a página do parlamentar mostra os dois valores e a diferença.</p>
      <h2>Links das notas fiscais</h2>
      <p>Cada nota da Câmara vem com o link do PDF no site oficial. Conferimos esses links: cerca de 1 em cada 1.000 dá erro 404, porque a Câmara publicou a despesa sem o arquivo da nota. Nessas notas, o link "Ver detalhe (a Câmara não publicou o PDF)" abre a página oficial da despesa. Os links que deram erro são conferidos de novo a cada atualização, e voltam a abrir a nota se o PDF aparecer.</p>
      <h2>Temas das votações</h2>
      <p>Cada votação recebe um ou mais temas (mulheres, micro e pequenas empresas, saúde, educação, segurança, armas, meio ambiente, impostos, trabalho, agropecuária, crianças, indígenas e minorias, energia, eleições) quando a ementa da proposta tem palavras ligadas ao tema. Por exemplo, "MEI" e "Simples Nacional" marcam micro e pequenas empresas; "Maria da Penha" e "feminicídio" marcam mulheres. É uma classificação automática e pode errar. Votar Sim nem sempre significa ser a favor do tema, por isso mostramos cada votação para você conferir.</p>
      <h2>Partidos: total e por parlamentar</h2>
      <p>O total soma os gastos de todos os membros atuais do partido. O valor por parlamentar divide esse total pelo número de membros, o que permite comparar partidos grandes e pequenos.</p>
      <h2>Holdings e donos finais</h2>
      <p>Às vezes a sócia de uma empresa é outra empresa, como uma holding. Nesse caso buscamos os sócios dessa empresa na Receita, e depois os sócios dos sócios, até chegar às pessoas (no máximo 5 empresas no caminho). A página da empresa mostra o caminho completo, por exemplo: Gráfica → Holding X → Fulano. Também usamos esses donos finais para ligar empresas do mesmo dono. A busca para quando o sócio está no exterior, quando a Receita não lista os sócios (comum em sociedades anônimas) ou quando duas empresas são sócias uma da outra, e a página diz qual foi o motivo.</p>
      <h2>Empresas no mesmo endereço</h2>
      <p>Quando duas ou mais empresas que recebem de parlamentares estão registradas na Receita no mesmo endereço (mesmo CEP, número e complemento), avisamos na página da empresa. Isso pode indicar o mesmo dono ou o mesmo grupo, mas também pode ser só um prédio comercial ou um escritório de contabilidade. Filiais da mesma empresa não contam.</p>
      <h2>Os três grupos de gasto</h2>
      <ul>
        <li><strong>Com o próprio parlamentar:</strong> passagens, hospedagem, alimentação, combustível, aluguel de carro, táxi.</li>
        <li><strong>Com o gabinete:</strong> escritório, telefone, correio, material, assinaturas.</li>
        <li><strong>Com serviços contratados:</strong> divulgação do mandato, consultorias, pesquisas, segurança.</li>
      </ul>
      <h2>Como calculamos esquerda e direita</h2>
      <p>Não usamos o rótulo que o partido dá a si mesmo, porque nem todos se colocam num lado em documento oficial, como estatuto ou programa. Olhamos como cada parlamentar votou em todas as votações nominais do período e encontramos o eixo que mais separa os votos uns dos outros. É o mesmo princípio do <a href="https://voteview.com" target="_blank" rel="noreferrer">Voteview</a>, usado para o Congresso dos EUA. Votações quase unânimes são ignoradas, porque não dizem nada sobre lados. Para decidir qual ponta é a direita, usamos PL e NOVO como referência de um lado e PT e PSOL do outro; isso só define o sentido da régua, não a posição de ninguém.</p>
      <p>"Vota com o governo" compara o voto com a orientação do líder do governo, quando ela existe. Acima de 70% chamamos de base do governo; abaixo de 35%, de oposição.</p>
      <h2>Pontos de atenção</h2>
      <p>Algumas empresas recebem avisos automáticos: empresa aberta pouco antes do primeiro pagamento, situação irregular na Receita, ou capital social muito baixo para o valor recebido. Esses avisos não são acusação. Servem para indicar onde vale olhar com mais cuidado.</p>
      <h2>Limites</h2>
      <ul>
        <li>A Câmara não publica o salário de cada assessor na lista da equipe, só o total gasto com a verba de gabinete. O Senado não publica o custo total da equipe de cada senador.</li>
        <li>Deputados estaduais e governadores ainda não estão incluídos{MG ? "" : " (o Minas Nossa começa por Minas Gerais)"}. Estão nas próximas etapas.</li>
        <li>Votações simbólicas e secretas não têm voto individual, então não aparecem.</li>
        <li>A Receita esconde parte do CPF dos sócios, então a ligação entre empresas do mesmo dono pode ter homônimos.</li>
      </ul>
    </section>
  );
}
