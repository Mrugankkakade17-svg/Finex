import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useLocalSession } from '../context/LocalSessionContext';
import { DomainOutcome } from '../context/localS2Capabilities';
import { portfolioRequest } from '../services/localS2Client';
import { useLocalS2Tasks } from '../hooks/useLocalS2Tasks';
import { Catalog, decimalInput, Holding, HoldingList, LocalS2Response, Portfolio, PortfolioInput, PortfolioList, PortfolioMetrics } from '../services/localS2Models';
import './LocalS2.css';
interface PortfolioSnapshot {
  p: Portfolio;
  h: DomainOutcome<LocalS2Response<HoldingList>>;
  m: DomainOutcome<LocalS2Response<PortfolioMetrics>>;
}
type RemovalSnapshot = {
  detail: PortfolioSnapshot;
  list: null;
} | {
  detail: null;
  list: DomainOutcome<LocalS2Response<PortfolioList>>;
};
export function LocalPortfolioPage() {
  const { domain } = useLocalSession(), tasks = useLocalS2Tasks();
  const [catalog, setCatalog] = useState<Catalog | null>(null), [list, setList] = useState<PortfolioList | null>(null);
  const [selected, setSelected] = useState<Portfolio | null>(null), [holdings, setHoldings] = useState<HoldingList | null>(null);
  const [metrics, setMetrics] = useState<LocalS2Response<PortfolioMetrics> | null>(null);
  const [name, setName] = useState(''), [description, setDescription] = useState(''), [nullDescription, setNullDescription] = useState(true);
  const [editPortfolio, setEditPortfolio] = useState(false), [editHolding, setEditHolding] = useState<Holding | null>(null);
  const selectionIntent = useRef({ selected, editPortfolio });
  selectionIntent.current = { selected, editPortfolio };
  const [instrument, setInstrument] = useState(''), [quantity, setQuantity] = useState(''), [cost, setCost] = useState('');
  const [confirm, setConfirm] = useState<{
    entity: 'portfolio' | 'holding';
    id: string;
  } | null>(null);
  const [notice, setNotice] = useState(''), [portfolioReconcile, setPortfolioReconcile] = useState(false);
  const [holdingReconcile, setHoldingReconcile] = useState<Record<string, true>>({});
  const holdingMutationUnavailable = catalog === null || holdings === null;
  const reconcileHolding = (id: string) => setHoldingReconcile((old) => {
    const remaining = { ...old };
    delete remaining[id];
    return remaining;
  });
  const applyOwnedList = useCallback((currentList: PortfolioList) => {
    setList(currentList);
    const intent = selectionIntent.current;
    const previous = intent.selected;
    if (previous === null) {
      return;
    }
    const current = currentList.items.find(
      (item) => item.portfolio_id === previous.portfolio_id,
    );
    if (current !== undefined) {
      // The list confirms portfolio metadata, not a new holdings/valuation
      // read. Dirty edit controllers and last-confirmed snapshots stay intact.
      selectionIntent.current = { ...intent, selected: current };
      setSelected(current);
      return;
    }
    // Only a current, successful full owned-list read can remove this target.
    // Both callers run inside the existing mount/abort/work-epoch boundary.
    const vanishedId = previous.portfolio_id;
    selectionIntent.current = { selected: null, editPortfolio: false };
    setSelected(null);
    setHoldings(null);
    setMetrics(null);
    setConfirm(null);
    setEditHolding(null);
    setQuantity('');
    setCost('');
    setHoldingReconcile((old) => {
      const remaining = { ...old };
      delete remaining[vanishedId];
      return remaining;
    });
    setEditPortfolio(false);
    if (intent.editPortfolio) {
      // An edit belonged to the vanished target; a separate unsaved CREATE
      // does not, and must not lose its name/description on a read refresh.
      setName('');
      setDescription('');
      setNullDescription(true);
    }
  }, []);
  const load = useCallback(() => {
    setNotice('');
    setCatalog(null);
    void tasks.run(async (signal) => {
      const p = await domain.portfolios({ signal });
      if (p.status !== 'success')
        return p;
      const c = await domain.catalog({ signal });
      if (c.status === 'cancelled')
        return c;
      return { status: 'success' as const, value: { c, p: p.value.data } };
    }, ({ c, p }) => {
      applyOwnedList(p);
      if (c.status === 'success') {
        setCatalog(c.value.data);
        setInstrument((old) => old || c.value.data.items[0].instrument_id);
      }
      else
        tasks.fail(c.error);
    });
  }, [applyOwnedList, domain, tasks.run]);
  useEffect(load, [load]);
  async function snapshot(id: string, signal: AbortSignal): Promise<DomainOutcome<PortfolioSnapshot>> {
    const p = await domain.portfolio(id, { signal });
    if (p.status !== 'success')
      return p;
    const h = await domain.holdings(id, { signal });
    if (h.status === 'cancelled')
      return h;
    const m = await domain.metrics(id, { signal });
    if (m.status === 'cancelled')
      return m;
    return { status: 'success' as const, value: { p: p.value.data, h, m } };
  }
  function showSnapshot(value: PortfolioSnapshot) {
    setSelected(value.p);
    setHoldings(value.h.status === 'success' ? value.h.value.data : null);
    setMetrics(value.m.status === 'success' ? value.m.value : null);
    if (value.h.status === 'error')
      tasks.fail(value.h.error);
    else if (value.m.status === 'error')
      tasks.fail(value.m.error);
  }
  const open = (id: string) => {
    setNotice('');
    setSelected(null);
    setHoldings(null);
    setMetrics(null);
    setEditPortfolio(false);
    setEditHolding(null);
    setConfirm(null);
    void tasks.run((signal) => snapshot(id, signal), (value) => showSnapshot(value));
  };
  const resetHolding = () => {
    setEditHolding(null);
    setQuantity('');
    setCost('');
  };
  const refreshSelected = () => {
    if (!selected)
      return;
    setNotice('');
    setMetrics(null);
    void tasks.run((signal) => snapshot(selected.portfolio_id, signal), (value) => {
      showSnapshot(value);
      if (holdingReconcile[value.p.portfolio_id] && value.h.status === 'success') {
        reconcileHolding(value.p.portfolio_id);
        setNotice('Holdings refreshed; no POST repeated. Check the list before deliberately trying again.');
      }
    });
  };
  const refreshList = () => {
    setNotice('');
    void tasks.run((signal) => domain.portfolios({ signal }), (r) => {
      applyOwnedList(r.data);
      setPortfolioReconcile(false);
      setNotice('List refreshed; no POST repeated. Check your owned portfolios before deliberately trying again.');
    });
  };
  const savePortfolio = () => {
    setNotice('');
    let input: PortfolioInput;
    try {
      input = portfolioRequest({ portfolio_version: 'portfolio.v1', name, description: nullDescription ? null : description, currency: 'USD' });
    }
    catch (failure) {
      tasks.fail(failure);
      return;
    }
    if (!editPortfolio)
      setPortfolioReconcile(true);
    void tasks.run(async (signal) => {
      const saved = editPortfolio && selected ? await domain.updatePortfolio(selected.portfolio_id, input, { signal }) : await domain.createPortfolio(input, { signal });
      if (saved.status !== 'success')
        return saved;
      const refreshed = await domain.portfolios({ signal });
      if (refreshed.status === 'cancelled')
        return refreshed;
      const detail = await snapshot(saved.value.data.portfolio_id, signal);
      if (detail.status === 'cancelled')
        return detail;
      return { status: 'success' as const, value: { saved: saved.value.data, refreshed, detail } };
    }, (v) => {
      if (v.detail.status === 'success')
        showSnapshot(v.detail.value);
      else {
        setSelected(v.saved);
        setHoldings(null);
        setMetrics(null);
        tasks.fail(v.detail.error);
      }
      if (v.refreshed.status === 'success')
        setList(v.refreshed.value.data);
      else
        tasks.fail(v.refreshed.error);
      setPortfolioReconcile(false);
      setEditPortfolio(false);
      setName('');
      setDescription('');
      setNullDescription(true);
      setNotice('Portfolio saved on the backend.');
    });
  };
  const saveHolding = () => {
    if (!selected || holdingMutationUnavailable)
      return;
    const id = selected.portfolio_id;
    try {
      const input = { holding_version: 'holding.v1' as const, quantity: decimalInput(quantity, 6, true), average_cost: decimalInput(cost, 4, false), currency: 'USD' as const };
      setNotice('');
      setMetrics(null);
      if (!editHolding)
        setHoldingReconcile((old) => ({ ...old, [id]: true }));
      void tasks.run(async (signal) => {
        const saved = editHolding ? await domain.updateHolding(id, editHolding.holding_id, input, { signal }) : await domain.createHolding(id, { ...input, instrument_id: instrument }, { signal });
        if (saved.status !== 'success')
          return saved;
        const detail = await snapshot(id, signal);
        if (detail.status !== 'success')
          return detail;
        return { status: 'success' as const, value: detail.value };
      }, (v) => {
        showSnapshot(v);
        resetHolding();
        if (v.h.status === 'success')
          reconcileHolding(id);
        setNotice(v.m.status === 'success' ? 'Holding saved on the backend. Valuation refreshed from the server.' : 'Holding saved on the backend. Valuation remains unconfirmed; retry the read.');
      });
    }
    catch (failure) {
      tasks.fail(failure);
    }
  };
  const remove = () => {
    if (!confirm || !selected || (confirm.entity === 'holding' && holdingMutationUnavailable))
      return;
    const target = confirm, id = selected.portfolio_id;
    setNotice('');
    setMetrics(null);
    void tasks.run<RemovalSnapshot>(async (signal) => {
      if (target.entity === 'holding') {
        const removed = await domain.deleteHolding(id, target.id, { signal });
        if (removed.status !== 'success')
          return removed;
        const detail = await snapshot(id, signal);
        if (detail.status !== 'success')
          return detail;
        return { status: 'success' as const, value: { detail: detail.value, list: null } };
      }
      const removed = await domain.deletePortfolio(target.id, { signal });
      if (removed.status !== 'success')
        return removed;
      const refreshed = await domain.portfolios({ signal });
      if (refreshed.status === 'cancelled')
        return refreshed;
      return { status: 'success' as const, value: { detail: null, list: refreshed } };
    }, (v) => {
      if (v.detail)
        showSnapshot(v.detail);
      else {
        setSelected(null);
        setHoldings(null);
        setEditPortfolio(false);
        setName('');
        setDescription('');
        setNullDescription(true);
        reconcileHolding(target.id);
        if (v.list.status === 'success')
          setList(v.list.value.data);
        else if (v.list.status === 'error') {
          // This DELETE was confirmed even though a full-list refresh was not.
          setList((old) => {
            if (old === null)
              return null;
            const items = old.items.filter((p) => p.portfolio_id !== target.id);
            return { ...old, items, count: items.length };
          });
          tasks.fail(v.list.error);
        }
      }
      setConfirm(null);
      resetHolding();
      setNotice(target.entity === 'holding' ? v.detail?.m.status === 'success' ? 'Holding deletion confirmed. Valuation refreshed.' : 'Holding deletion confirmed. Valuation remains unconfirmed; retry the read.' : 'Portfolio and its manual holdings deletion confirmed.');
    });
  };
  return <section className="local-card local-s2"><p className="local-eyebrow">Sprint 2 · Owned manual practice</p><h1 tabIndex={-1}>Your manual portfolios</h1>
 <p className="local-lede">Manual records, USD only. Quotes are invented training fixtures, not market data. No broker positions, trades or suitability recommendation.</p>
 {tasks.busy && <p role="status">Confirming the portfolio operation on the local backend…</p>}
 {tasks.error && <div className="local-error" role="alert" tabIndex={-1} ref={tasks.errorRef}>{tasks.error.message}</div>}
 {notice && <p className="local-status" role="status">{notice}</p>}
 <div className="local-actions"><button className="btn-secondary" disabled={tasks.busy} onClick={load}>Reload catalogue and portfolios</button>
 <button className="btn-secondary" disabled={tasks.busy} onClick={refreshList}>{portfolioReconcile ? 'Refresh owned portfolios before retry' : 'Refresh owned portfolios'}</button></div>
 {portfolioReconcile && <p className="local-warning">Portfolio creation has not been fully confirmed. It may have committed. Refresh the owned portfolio list before a deliberate new POST; nothing is automatically repeated.</p>}
 {Object.keys(holdingReconcile).length > 0 && <p className="local-warning">A holding creation has not been fully confirmed. It may have committed. Open its original portfolio and refresh that holding list before a deliberate new POST; reading another portfolio does not reconcile it. Nothing is automatically repeated.</p>}
 {list && <>
 <form onSubmit={(e) => {
      e.preventDefault();
      savePortfolio();
    }}><h2>{editPortfolio ? 'Edit portfolio details' : 'Create a manual portfolio'}</h2>
  <fieldset disabled={tasks.busy || (!editPortfolio && portfolioReconcile)} className="local-s2-fieldset">
  <div className="local-field"><label htmlFor="portfolio-name">Portfolio name</label><input id="portfolio-name" type="text" value={name} maxLength={100} required onChange={(e) => setName(e.target.value)}/><p className="local-help">Use a nonsensitive learning label, not an account number.</p></div>
  <label className="local-checkbox"><input type="checkbox" checked={nullDescription} onChange={(e) => setNullDescription(e.target.checked)}/>No description (save null)</label>
  {!nullDescription && <div className="local-field"><label htmlFor="portfolio-description">Description</label><textarea id="portfolio-description" value={description} maxLength={500} onChange={(e) => setDescription(e.target.value)}/></div>}
  </fieldset>
  <div className="local-actions"><button className="btn-primary" disabled={tasks.busy || (!editPortfolio && portfolioReconcile)}>{editPortfolio ? 'Update portfolio' : 'Create portfolio'}</button>
  {editPortfolio && <button type="button" className="btn-secondary" disabled={tasks.busy} onClick={() => {
      setEditPortfolio(false);
      setName('');
      setDescription('');
      setNullDescription(true);
    }}>Cancel portfolio edit</button>}</div>
 </form>
 <section className="local-s2-section"><h2>Your owned portfolio list</h2>{list && (!list.items.length ? <p>No manual portfolios saved yet.</p> : <ul>{list.items.map((p) => <li key={p.portfolio_id}><button className="btn-secondary" disabled={tasks.busy} onClick={() => open(p.portfolio_id)}>Open {p.name}</button><p className="local-help">Created {p.created_at} · updated {p.updated_at}</p></li>)}</ul>)}</section>
 </>}
 {selected && <section className="local-s2-section"><h2 tabIndex={-1}>{selected.name}</h2><p>{selected.description ?? 'No saved description.'}</p>
 <p className="local-help">Portfolio details last saved: {selected.updated_at}. Holding changes do not change this timestamp.</p>
 <div className="local-actions"><button className="btn-secondary" disabled={tasks.busy} onClick={() => {
      setName(selected.name);
      setDescription(selected.description || '');
      setNullDescription(selected.description === null);
      setEditPortfolio(true);
    }}>Edit portfolio</button>
  <button className="btn-secondary" disabled={tasks.busy} onClick={() => setConfirm({ entity: 'portfolio', id: selected.portfolio_id })}>Delete portfolio</button>
  <button className="btn-secondary" disabled={tasks.busy} onClick={refreshSelected}>{holdingReconcile[selected.portfolio_id] ? 'Refresh owned holdings before retry' : 'Refresh holdings and valuation'}</button></div>
 {confirm && <section className="local-warning" aria-label="Deletion confirmation"><p>Delete this {confirm.entity}? {confirm.entity === 'portfolio' ? 'Only its own manual holdings will also be removed.' : 'The other manual holdings remain.'}</p>
  <div className="local-actions"><button className="btn-secondary" disabled={tasks.busy || (confirm.entity === 'holding' && holdingMutationUnavailable)} onClick={remove}>Confirm delete {confirm.entity}</button><button className="btn-secondary" disabled={tasks.busy} onClick={() => setConfirm(null)}>Cancel deletion</button></div></section>}
 {catalog && holdings !== null && <form onSubmit={(e) => {
        e.preventDefault();
        saveHolding();
      }}><h3>{editHolding ? 'Edit manual holding' : 'Add manual holding'}</h3>
  <fieldset className="local-s2-fieldset" disabled={tasks.busy || (!editHolding && holdingReconcile[selected.portfolio_id])}>
  <div className="local-field"><label htmlFor="holding-instrument">Synthetic instrument</label><select id="holding-instrument" disabled={editHolding !== null} value={instrument} onChange={(e) => setInstrument(e.target.value)}>
   {catalog.items.map((i) => <option key={i.instrument_id} value={i.instrument_id}>{i.display_name} · {i.instrument_id}</option>)}</select><p className="local-help">Supported manual catalogue, not market search. The instrument is immutable on an existing holding.</p></div>
  <div className="local-s2-grid"><div className="local-field"><label htmlFor="holding-quantity">Quantity</label><input id="holding-quantity" type="text" inputMode="decimal" required value={quantity} onChange={(e) => setQuantity(e.target.value)}/><p className="local-help">0.000001–1000000, up to six decimal places.</p></div>
   <div className="local-field"><label htmlFor="holding-cost">Average cost (USD per unit)</label><input id="holding-cost" type="text" inputMode="decimal" required value={cost} onChange={(e) => setCost(e.target.value)}/><p className="local-help">0–1000000, up to four decimal places. Cost never substitutes for a missing quote.</p></div></div>
  </fieldset><div className="local-actions"><button className="btn-primary" disabled={tasks.busy || (!editHolding && holdingReconcile[selected.portfolio_id])}>{editHolding ? 'Update holding' : 'Add holding'}</button>
  {editHolding && <button type="button" className="btn-secondary" disabled={tasks.busy} onClick={resetHolding}>Cancel holding edit</button>}</div></form>}
 <h3>Saved manual holdings</h3>{holdings === null ? <p>The current holding list has not been confirmed. Retry the read; no empty list is assumed.</p> : (!holdings.items.length ? <p>No manual holdings saved.</p> : holdings.items.map((h) => <article className="local-s2-row" key={h.holding_id}><h4>{h.display_name}</h4><p>{h.quantity} units · average cost USD {h.average_cost} · {h.asset_class} / {h.sector}</p>
  <p className="local-help">Saved {h.updated_at}</p><div className="local-actions"><button className="btn-secondary" disabled={tasks.busy || holdingMutationUnavailable} onClick={() => {
        setEditHolding(h);
        setInstrument(h.instrument_id);
        setQuantity(h.quantity);
        setCost(h.average_cost);
      }}>Edit {h.display_name}</button>
  <button className="btn-secondary" disabled={tasks.busy || holdingMutationUnavailable} onClick={() => setConfirm({ entity: 'holding', id: h.holding_id })}>Delete {h.display_name}</button></div></article>))}
 <section className="local-s2-section"><h3>Backend valuation snapshot</h3>{metrics ? <MetricsView response={metrics}/> : <p>No current valuation has been confirmed. Saved holding records remain available; retry the valuation.</p>}</section>
 </section>}
</section>;
}
function MetricsView({ response }: {
  response: LocalS2Response<PortfolioMetrics>;
}) {
  const m = response.data, t = m.totals;
  const amount = (value: string | null, suffix = '') => value === null ? 'Unavailable / not defined' : value + suffix;
  return <><p className={response.meta.dataStatus === 'UNAVAILABLE' ? 'local-warning' : 'local-status'}>Valuation: {m.valuation_status} · data status: {response.meta.dataStatus}</p>
 <p className="local-help">Source {m.source} · {m.source_type} · fixed fixture as-of {m.fixture_as_of}. Calculation time {m.calculated_at} is not quote freshness.</p>
 <p className="local-help">{m.formula_version} · {m.catalog_version} · {m.quote_snapshot_version} · confirmed data as-of {response.meta.dataAsOf ?? 'none'}</p>
 {m.missing_instrument_ids.length > 0 && <p className="local-warning">Missing synthetic prices: {m.missing_instrument_ids.join(', ')}. Overall valuation, weights and allocations remain unavailable.</p>}
 <dl><dt>Cost basis (USD)</dt><dd>{t.cost_basis}</dd><dt>Market value (USD)</dt><dd>{amount(t.market_value)}</dd><dt>Gain/loss (USD)</dt><dd>{amount(t.gain_loss)}</dd><dt>Gain/loss percentage</dt><dd>{amount(t.gain_loss_percent, '%')}</dd>
 <dt>Largest instrument weight</dt><dd>{amount(t.concentration_percent, '%')}</dd><dt>HHI</dt><dd>{amount(t.hhi)}</dd><dt>Educational allocation spread</dt><dd>{amount(t.educational_spread_percent, '%')}</dd></dl>
 {m.holdings.map((h) => <section key={h.holding_id} className="local-s2-row"><h4>{h.display_name}</h4><p>Quote: {h.quote.data_status} · unit USD {amount(h.quote.unit_price)} · as-of {h.quote.quote_as_of ?? 'none'} {h.quote.reason ?? ''}</p>
 <p>Cost USD {h.cost_basis} · value USD {amount(h.market_value)} · gain USD {amount(h.gain_loss)} · gain {amount(h.gain_loss_percent, '%')} · weight {amount(h.weight_percent, '%')}</p></section>)}
 {([['Asset class allocation', t.allocation_by_asset_class], ['Sector allocation', t.allocation_by_sector]] as const).map(([label, rows]) => <section key={label}><h4>{label}</h4>{rows === null ? <p>Unavailable; no priced-subset renormalization.</p> : !rows.length ? <p>No allocation rows (empty portfolio).</p> : <ul>{rows.map((r) => <li key={r.group}>{r.group}: USD {r.market_value} · {amount(r.weight_percent, '%')}</li>)}</ul>}</section>)}
 <p className="local-help">Spread describes allocation only, not correlation, financial risk or suitability. Displayed weights may sum to 99.99 or 100.01; the client never recalculates them.</p>
 <details><summary>Synthetic learning limitations</summary><ul>{m.limitations.map((code) => <li key={code}>{code.replace(/_/g, ' ')}</li>)}</ul></details>
</>;
}
