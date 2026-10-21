export default function Sobre() {
  return (
    <section style={{ maxWidth: 720 }}>
      <h1>Como funciona</h1>
      <h2>De onde vêm os dados</h2>
      <p>Tudo vem de fontes oficiais e públicas, baixadas automaticamente todos os dias:</p>
      <ul>
        <li><a href="https://dadosabertos.camara.leg.br" target="_blank" rel="noreferrer">Dados Abertos da Câmara dos Deputados</a>: deputados, cota parlamentar (CEAP) e votações.</li>
        <li><a href="https://www12.senado.leg.br/dados-abertos" target="_blank" rel="noreferrer">Dados Abertos do Senado Federal</a>: senadores, cota (CEAPS) e votações.</li>
        <li>Receita Federal, base pública de CNPJ: dados das empresas e quadro de sócios. Consultada pelo espelho aberto <a href="https://minhareceita.org" target="_blank" rel="noreferrer">Minha Receita</a>.</li>
      </ul>
      <h2>O que é a cota parlamentar</h2>
      <p>É um valor mensal, além do salário, para pagar despesas do mandato: passagens, aluguel de escritório no estado, combustível, divulgação e outras. O parlamentar paga e pede reembolso com a nota fiscal. O valor muda conforme o estado, porque passagens para Brasília custam diferente.</p>
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
        <li>Salários da equipe do gabinete, deputados estaduais e governadores ainda não estão incluídos. Estão nas próximas etapas.</li>
        <li>Votações simbólicas e secretas não têm voto individual, então não aparecem.</li>
        <li>A Receita esconde parte do CPF dos sócios, então a ligação entre empresas do mesmo dono pode ter homônimos.</li>
      </ul>
    </section>
  );
}
