import { MG } from "../recorte";

/** Como uma proposta vira lei: desenho do caminho (à esquerda) e a explicação de cada etapa (à direita; no celular,
 * embaixo). Os números do desenho são os mesmos da lista e da barra de etapas de cada cartão. */
const PASSOS = [
  { nome: "Apresentada", quem: "deputado, senador, presidente…", texto: "Um parlamentar, o presidente ou outro autor apresenta a proposta." },
  { nome: "Comissões", quem: "relator dá o parecer", texto: "Comissões temáticas estudam o texto. Um relator recomenda aprovar, mudar ou rejeitar." },
  { nome: "Plenário", quem: "todos da Casa votam", texto: "Todos os parlamentares da Casa votam." },
  { nome: "Outra Casa", quem: "Câmara ⇄ Senado", texto: "Aprovada numa Casa, segue para a outra (Câmara ou Senado), que pode mudar o texto. Se mudar, volta para a Casa onde começou dar a palavra final." },
  { nome: "Sanção ou promulgação", quem: "Presidente da República", texto: "O presidente sanciona (vira lei) ou veta. O Congresso pode derrubar o veto. Emendas à Constituição são promulgadas pelo próprio Congresso, sem passar pelo presidente." },
];

const Y0 = 34;
const PASSO = 78;

export default function CaminhoLei() {
  const yLei = Y0 + PASSOS.length * PASSO;
  return (
    <section className="card caminho" aria-labelledby="caminho-tit">
      <h2 id="caminho-tit" className="caminho-tit">Como uma proposta vira lei</h2>
      <div className="caminho-grade">
        <svg className="caminho-svg" viewBox={`0 0 432 ${yLei + 40}`} role="img"
          aria-label="Desenho do caminho: apresentada, comissões, plenário, outra Casa, sanção ou promulgação, e vira lei. Pode ser rejeitada no plenário, e o veto do presidente pode ser derrubado pelo Congresso.">
          <defs>
            <marker id="caminho-seta" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M0,0 L10,5 L0,10 z" className="caminho-ponta" />
            </marker>
          </defs>
          {/* linha que liga as etapas */}
          <line x1="40" y1={Y0} x2="40" y2={yLei} className="caminho-linha" />
          {/* "mudou o texto? volta": da etapa 4 para a 3, pela esquerda */}
          <path d={`M22,${Y0 + 3 * PASSO} C2,${Y0 + 3 * PASSO - 20} 2,${Y0 + 2 * PASSO + 20} 22,${Y0 + 2 * PASSO}`} className="caminho-volta" markerEnd="url(#caminho-seta)" />
          {PASSOS.map((p, i) => {
            const y = Y0 + i * PASSO;
            return (
              <g key={p.nome}>
                <circle cx="40" cy={y} r="18" className="caminho-bola" />
                <text x="40" y={y + 5} textAnchor="middle" className="caminho-num">{i + 1}</text>
                <text x="70" y={y - 3} className="caminho-nome">{p.nome}</text>
                <text x="70" y={y + 15} className="caminho-quem">{p.quem}</text>
              </g>
            );
          })}
          {/* desvios: rejeitada no plenário e veto do presidente */}
          <g>
            <line x1="252" y1={Y0 + 2 * PASSO} x2="276" y2={Y0 + 2 * PASSO} className="caminho-ramo" markerEnd="url(#caminho-seta)" />
            <rect x="280" y={Y0 + 2 * PASSO - 16} width="148" height="32" rx="16" className="caminho-pilula nao" />
            <text x="354" y={Y0 + 2 * PASSO + 5} textAnchor="middle" className="caminho-pil-txt">Rejeitada: arquivada</text>
          </g>
          <g>
            <line x1="252" y1={Y0 + 4 * PASSO} x2="276" y2={Y0 + 4 * PASSO} className="caminho-ramo" markerEnd="url(#caminho-seta)" />
            <rect x="280" y={Y0 + 4 * PASSO - 16} width="148" height="32" rx="16" className="caminho-pilula veto" />
            <text x="354" y={Y0 + 4 * PASSO + 5} textAnchor="middle" className="caminho-pil-txt">Veto: Congresso decide</text>
          </g>
          <circle cx="40" cy={yLei} r="20" className="caminho-lei" />
          <path d={`M31,${yLei} l6,7 l12,-14`} className="caminho-ok" />
          <text x="70" y={yLei - 3} className="caminho-nome">Vira lei</text>
          <text x="70" y={yLei + 15} className="caminho-quem">publicada no Diário Oficial</text>
        </svg>
        <div className="caminho-texto">
          <ol className="proj-como">
            {PASSOS.map((p) => <li key={p.nome}><b>{p.nome}.</b> {p.texto}</li>)}
          </ol>
          <p className="small muted">Em qualquer etapa a proposta pode ser rejeitada ou ficar parada. A seta curva no desenho mostra a volta para a Casa onde ela começou, quando a outra Casa muda o texto.</p>
          {MG && <p className="small muted">Na Assembleia de Minas o caminho é parecido, mas numa Casa só: depois das comissões e do Plenário, a proposta vai para o governador sancionar ou vetar.</p>}
          <p className="small muted">PL é projeto de lei, PLP é projeto de lei complementar, PEC muda a Constituição, MPV é medida provisória e PDL é projeto de decreto legislativo. Cada cartão explica o tipo em "Texto oficial e mais detalhes".</p>
        </div>
      </div>
    </section>
  );
}
