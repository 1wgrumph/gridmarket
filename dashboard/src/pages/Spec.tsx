import Panel from '../components/Panel';

const specUrl = 'https://github.com/1wgrumph/gridmarket/blob/main/spec/GridMarket-Specification.md';

export default function Spec() {
  return <section className="gm-page">
    <div className="gm-page-head"><h1>Specification</h1></div>
    <Panel title="Generated document">
      <p>The specification is generated from the repository's requirements, design, and verification records.</p>
      <p><a className="gm-views-link" href={specUrl}>Open GridMarket-Specification.md on GitHub ↗</a></p>
    </Panel>
  </section>;
}
