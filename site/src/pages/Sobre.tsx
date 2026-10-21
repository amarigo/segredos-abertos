export default function Sobre() {
  return (
    <section style={{ maxWidth: 720 }}>
      <h1>Como funciona</h1>
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
      <p>Somamos as notas fiscais que a Câmara e o Senado publicam, uma por uma, e mostramos cada ano separado, como nas páginas oficiais. No Senado, os totais batem exatamente. Na Câmara, a página de cada deputado às vezes mostra um valor maior que a soma das notas publicadas. Quando isso acontece, mostramos os dois valores na página do deputado. A diferença são despesas que a Câmara já contabilizou, mas cujas notas ainda não aparecem nos dados abertos.</p>
      <h2>Partidos: total e por parlamentar</h2>
      <p>O total soma os gastos de todos os membros atuais do partido. O valor por parlamentar divide esse total pelo número de membros, o que permite comparar partidos grandes e pequenos.</p>
      <h2>Empresas no mesmo endereço</h2>
      <p>Quando duas ou mais empresas que recebem de parlamentares estão registradas na Receita no mesmo endereço (mesmo CEP, número e complemento), avisamos na página da empresa. Isso pode indicar o mesmo dono ou o mesmo grupo, mas também pode ser só um prédio comercial ou um escritório de contabilidade. Filiais da mesma empresa não contam.</p>
      <h2>Os três grupos de gasto</h2>
      <ul>
        <li><strong>Com o próprio parlamentar:</strong> passagens, hospedagem, alimentação, combustível, aluguel de carro, táxi.</li>
        <li><strong>Com o gabinete:</strong> escritório, telefone, correio, material, assinaturas.</li>
        <li><strong>Com serviços contratados:</strong> divulgação do mandato, consultorias, pesquisas, segurança.</li>
      </ul>
      <h2>Como calculamos esquerda e direita</h2>
      <p>Não usamos o rótulo que o partido dá a si mesmo. Olhamos como cada parlamentar votou em todas as votações nominais do período e encontramos o eixo que mais separa os votos uns dos outros. É o mesmo princípio do <a href="https://voteview.com" target="_blank" rel="noreferrer">Voteview</a>, usado para o Congresso dos EUA. Votações quase unânimes são ignoradas, porque não dizem nada sobre lados. Para decidir qual ponta é a direita, usamos PL e NOVO como referência de um lado e PT e PSOL do outro; isso só define o sentido da régua, não a posição de ninguém.</p>
      <p>"Vota com o governo" compara o voto com a orientação do líder do governo, quando ela existe. Acima de 70% chamamos de base do governo; abaixo de 35%, de oposição.</p>
      <h2>Pontos de atenção</h2>
      <p>Algumas empresas recebem avisos automáticos: empresa aberta pouco antes do primeiro pagamento, situação irregular na Receita, ou capital social muito baixo para o valor recebido. Esses avisos não são acusação. Servem para indicar onde vale olhar com mais cuidado.</p>
      <h2>Limites</h2>
      <ul>
        <li>A Câmara não publica o salário de cada assessor na lista da equipe, só o total gasto com a verba de gabinete. O Senado não publica o custo total da equipe de cada senador.</li>
        <li>Deputados estaduais e governadores ainda não estão incluídos. Estão nas próximas etapas.</li>
        <li>Votações simbólicas e secretas não têm voto individual, então não aparecem.</li>
        <li>A Receita esconde parte do CPF dos sócios, então a ligação entre empresas do mesmo dono pode ter homônimos.</li>
      </ul>
    </section>
  );
}
