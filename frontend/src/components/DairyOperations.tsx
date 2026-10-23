import React, { useEffect, useState } from 'react';
import { PixelIcon } from './PixelIcons';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
const today = () => new Date().toISOString().slice(0, 10);
const money = (value: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(Number(value || 0));

function MetricCard({ label, value, note }: { label: string; value: any; note: string }) {
  return <div className="metric card"><span>{label}</span><strong>{value ?? '—'}</strong><small>{note}</small></div>;
}

export default function DairyOperations() {
  const [summary, setSummary] = useState<any>(null);
  const [dashboard, setDashboard] = useState<any>(null);
  const [tasks, setTasks] = useState<any[]>([]);
  const [feed, setFeed] = useState<any>({ feeds: [] });
  const [specs, setSpecs] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [tab, setTab] = useState('Overview');
  const [message, setMessage] = useState('');
  const load = async () => {
    try {
      const responses = await Promise.all([
        fetch(API + '/dairy/summary'),
        fetch(API + '/dairy/dashboard'),
        fetch(API + '/dairy/tasks'),
        fetch(API + '/dairy/feed'),
        fetch(API + '/dairy/processing/specs')
      ]);
      setSummary(await responses[0].json());
      setDashboard(await responses[1].json());
      setTasks((await responses[2].json()).tasks || []);
      setFeed(await responses[3].json());
      setSpecs((await responses[4].json()).specs || []);
    } catch (error: any) {
      setMessage(error?.message || 'Dairy API unavailable');
    }
  };
  useEffect(() => { load(); }, []);
  const d = dashboard || summary?.dashboard || {};
  const herd = d.herd || {};
  const production = d.production || {};
  const finance = d.finance || {};
  const inventory = d.inventory || {};
  const animals = summary?.animals || [];
  const showMessage = (text: string) => { setMessage(text); window.setTimeout(() => setMessage(''), 3500); };
  const recordProduction = async (animalId: string, event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const quantity = Number(form.get('quantity'));
    const saleable = Number(form.get('saleable_quantity') || quantity);
    const withheld = Number(form.get('withheld_quantity') || 0);
    const result = await fetch(API + '/dairy/animals/' + animalId + '/production', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        production_date: form.get('production_date'), quantity, unit: 'liter',
        session_type: form.get('session_type'), saleable_quantity: saleable,
        withheld_quantity: withheld, withholding_reason: form.get('withholding_reason'),
        operator: form.get('operator'), notes: form.get('notes')
      })
    });
    showMessage(result.ok ? 'Milking session saved to SQLite.' : (await result.json()).detail || 'Could not save session.');
    if (result.ok) load();
  };
  const saveAnimal = async () => {
    if (!selected?.animal_id) return;
    const result = await fetch(API + '/dairy/animals/' + selected.animal_id, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tag: selected.tag, name: selected.name, breed: selected.breed, birth_date: selected.birth_date,
        sex: selected.sex || 'FEMALE', herd_category: selected.herd_category || 'LACTATING_COW',
        production_status: selected.production_status || 'MILKING', facility_id: selected.facility_id || 'facility-barn',
        notes: selected.notes
      })
    });
    showMessage(result.ok ? 'Animal profile saved.' : (await result.json()).detail || 'Could not save profile.');
    if (result.ok) load();
  };
  const collectMilk = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const result = await fetch(API + '/dairy/milk-collections', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        collection_date: form.get('collection_date'), source_scope: 'MILKING_HERD',
        quantity_collected: Number(form.get('quantity_collected')), unit: 'liter',
        approved_quantity: Number(form.get('approved_quantity')), withheld_quantity: Number(form.get('withheld_quantity') || 0),
        withholding_reason: form.get('withholding_reason'), storage_id: 'storage-barn',
        quality_status: form.get('quality_status'), sell_by_date: form.get('sell_by_date'),
        created_by: 'Farm owner'
      })
    });
    showMessage(result.ok ? 'Milk collection and inventory receipt saved.' : (await result.json()).detail || 'Collection failed.');
    if (result.ok) { event.currentTarget.reset(); load(); }
  };
  const completeTask = async (taskId: string) => {
    await fetch(API + '/dairy/tasks/' + taskId, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'COMPLETED', completion_notes: 'Completed by farm owner.' })
    });
    load();
  };
  const tabNames = ['Overview', 'Interactive Barn', 'Herd & Profiles', 'Milking & Production', 'Feed Management', 'Milk Inventory', 'Tasks & Weather'];
  return <div className="content dairy-page">
    <div className="page-intro">
      <div><span className="tag">DAIRY OPERATIONS · SYNTHETIC + OWNER RECORDS</span><h2>Run the dairy with clarity.</h2><p>Recorded milk, shared inventory, finance, weather, and animal identity stay connected. Medical information is never inferred.</p></div>
      <span className="status">{d.data_status || summary?.data_status || 'LOADING'}</span>
    </div>
    <div className="dairy-hero card"><PixelIcon kind="cow" size={72}/><div><h3>Green Valley dairy barn</h3><p>{herd.total || 0} animals · {herd.active_milking || 0} lactating · {herd.dry_cows || 0} dry · {production.today_liters || 0} L recorded today</p><span className="status">HEALTH: RECORDED EVENTS ONLY</span></div></div>
    <div className="metrics dairy-kpis">
      <MetricCard label="Total herd" value={herd.total} note="Database animals"/>
      <MetricCard label="Active milking" value={herd.active_milking} note="Lactating cows"/>
      <MetricCard label="Dry cows" value={herd.dry_cows} note="Mutually exclusive category"/>
      <MetricCard label="Today milk" value={(production.today_liters || 0) + ' L'} note="Recorded, not forecast"/>
      <MetricCard label="7-day milk" value={(production.seven_day_liters || 0) + ' L'} note="Recorded production"/>
      <MetricCard label="Cost / gallon" value={finance.cost_per_gallon_saleable_milk == null ? 'Unavailable' : money(finance.cost_per_gallon_saleable_milk)} note="Finance-linked"/>
      <MetricCard label="Raw milk available" value={(inventory.raw_milk_liters_available || 0) + ' L'} note="Shared inventory ledger"/>
      <MetricCard label="Tasks open" value={d.tasks?.active_count || 0} note="Dairy task records"/>
    </div>
    <div className="dairy-tabs">{tabNames.map(name => <button key={name} className={tab === name ? 'active' : ''} onClick={() => setTab(name)}>{name}</button>)}</div>
    {message && <div className="toast dairy-toast">{message}</div>}
    {tab === 'Overview' && <DairyOverview production={production} herd={herd} finance={finance}/>}
    {tab === 'Interactive Barn' && <BarnView animals={animals} onAnimal={(animal: any) => { setSelected(animal); setTab('Herd & Profiles'); }} onTab={setTab}/>}
    {tab === 'Herd & Profiles' && <HerdView animals={animals} selected={selected} setSelected={setSelected} save={saveAnimal}/>}
    {tab === 'Milking & Production' && <ProductionView animals={animals} records={summary?.production_records || []} onSubmit={recordProduction}/>}
    {tab === 'Feed Management' && <FeedView feed={feed} onSaved={load}/>}
    {tab === 'Milk Inventory' && <InventoryView inventory={inventory} specs={specs} onSubmit={collectMilk}/>}
    {tab === 'Tasks & Weather' && <TaskWeatherView tasks={tasks} weather={d.weather} onComplete={completeTask}/>}
  </div>;
}

function DairyOverview({ production, herd, finance }: any) {
  const max = Math.max(1, ...(production.daily || []).map((row: any) => row.liters));
  return <><div className="grid-2"><section className="card dairy-chart"><div className="card-head"><h3>Daily milk output · last 30 days</h3><button>Recorded</button></div><div className="dairy-bars">{(production.daily || []).map((row: any) => <div className="dairy-bar" key={row.date}><i style={{ height: Math.min(100, row.liters / max * 100) + '%' }}/><small>{row.date.slice(5)}</small></div>)}</div></section><section className="card dairy-chart"><div className="card-head"><h3>Milk production by cow</h3><button>Last 30 days</button></div><div className="dairy-ranking">{(production.by_animal || []).map((row: any, index: number) => <div key={row.animal_id}><span>{row.name}</span><b><i style={{ width: Math.min(100, row.liters / Math.max(1, production.by_animal?.[0]?.liters || 1) * 100) + '%' }}/></b><strong>{row.liters} L</strong><em>{index === 0 ? 'Highest recorded output' : 'Recorded output'}</em></div>)}</div></section></div><div className="grid-2"><section className="card"><div className="card-head"><h3>Herd composition</h3><button>Current records</button></div><div className="herd-composition">{Object.entries(herd.composition || {}).map(([key, value]) => <div key={key}><span>{key.replace(/_/g, ' ')}</span><strong>{String(value)}</strong></div>)}</div></section><section className="card"><div className="card-head"><h3>Dairy profitability</h3><button>Recorded ledger</button></div><div className="dairy-profit-grid"><div><span>Revenue</span><strong>{money(finance.revenue_period || 0)}</strong></div><div><span>Costs</span><strong>{money(finance.total_dairy_cost_period || 0)}</strong></div><div><span>Gross profit</span><strong>{money(finance.gross_profit || 0)}</strong></div><div><span>Margin</span><strong>{finance.gross_margin_pct == null ? 'Unavailable' : finance.gross_margin_pct + '%'}</strong></div></div><small>Milk production is not revenue until a sale is recorded.</small></section></div><section className="card"><div className="card-head"><h3>Production cost breakdown</h3><button>Finance-linked</button></div><div className="cost-breakdown">{(finance.breakdown || []).map((row: any) => <div key={row.category}><span>{row.category}</span><b><i style={{ width: Math.min(100, row.amount / Math.max(1, finance.total_dairy_cost_period || 1) * 100) + '%' }}/></b><strong>{money(row.amount)}</strong></div>)}</div></section></>;
}

function BarnView({ animals, onAnimal, onTab }: any) {
  return <section className="card barn-card"><div className="card-head"><h3>Interactive dairy barn</h3><button>Original SVG pixel art</button></div><svg viewBox="0 0 760 420" role="img" aria-label="Interactive dairy barn"><rect width="760" height="420" rx="16" fill="#dbe6c9"/><rect x="24" y="24" width="712" height="372" rx="12" fill="#ead5ad" stroke="#9b744d" strokeWidth="6"/><path d="M40 130h680M40 260h680M260 40v340M520 40v340" stroke="#bd9667" strokeWidth="4"/><text x="58" y="65" fill="#72533a" fontSize="16" fontWeight="700">GREEN VALLEY DAIRY BARN · SYNTHETIC RECORDS</text><g className="barn-target" onClick={() => onTab('Milk Inventory')}><rect x="570" y="285" width="120" height="70" rx="10" fill="#cbd9df" stroke="#617c84" strokeWidth="3"/><text x="580" y="330" fill="#42606b" fontSize="12">MILK TANK</text></g><g className="barn-target" onClick={() => onTab('Feed Management')}><rect x="50" y="285" width="130" height="70" rx="10" fill="#d5b36d" stroke="#8d6638" strokeWidth="3"/><text x="74" y="325" fill="#6d4e2e" fontSize="13">FEED STATION</text></g><g className="barn-target" onClick={() => onTab('Tasks & Weather')}><rect x="300" y="285" width="150" height="70" rx="10" fill="#fff5dc" stroke="#ab8a55" strokeWidth="3"/><PixelIcon kind="worker" size={32}/><text x="320" y="340" fill="#6d5739" fontSize="12">TASK BOARD</text></g>{animals.map((animal: any, index: number) => { const x = 90 + index % 4 * 160; const y = 105 + Math.floor(index / 4) * 105; return <g className="barn-animal" key={animal.animal_id} onClick={() => onAnimal(animal)}><rect x={x - 42} y={y - 35} width="84" height="74" rx="12" fill="#f7f2df" stroke="#d2b78c"/><PixelIcon kind="cow" size={42}/><text x={x - 30} y={y + 29} fill="#315c40" fontSize="11">{animal.name || animal.tag}</text></g>; })}</svg><p className="section-note">Click a cow for its database profile. The milk tank, feed station, and worker board open functional operations.</p></section>;
}

function HerdView({ animals, selected, setSelected, save }: any) {
  return <div className="grid-2"><section className="card animal-card"><div className="card-head"><h3>My herd</h3><button>Database-backed</button></div><div className="animal-grid">{animals.map((animal: any) => <button className={selected?.animal_id === animal.animal_id ? 'animal-tile active' : 'animal-tile'} key={animal.animal_id} onClick={() => setSelected(animal)}><PixelIcon kind="cow" size={43}/><strong>{animal.name || animal.tag}</strong><small>{animal.breed} · {animal.herd_category || animal.production_status}</small></button>)}</div></section>{selected ? <section className="card animal-profile"><div className="card-head"><h3>{selected.name || 'Animal profile'}</h3><button>Owner editable</button></div><PixelIcon kind="cow" size={64}/><div className="mini-form"><label>Name<input value={selected.name || ''} onChange={e => setSelected({...selected, name: e.target.value})}/></label><label>Tag<input value={selected.tag || ''} onChange={e => setSelected({...selected, tag: e.target.value})}/></label><label>Breed<input value={selected.breed || ''} onChange={e => setSelected({...selected, breed: e.target.value})}/></label><label>Category<select value={selected.herd_category || 'LACTATING_COW'} onChange={e => setSelected({...selected, herd_category: e.target.value})}><option>LACTATING_COW</option><option>DRY_COW</option><option>PREGNANT_HEIFER</option><option>NONPREGNANT_HEIFER</option><option>CALF</option></select></label><label>Notes<textarea value={selected.notes || ''} onChange={e => setSelected({...selected, notes: e.target.value})}/></label></div><p className="section-note">Health data is recorded separately; this profile never infers clinical status.</p><button className="primary" onClick={save}>Save profile</button></section> : <div className="empty-panel card"><PixelIcon kind="cow" size={45}/><h3>Select an animal</h3><p>Open a persistent identity and production profile.</p></div>}</div>;
}

function ProductionView({ animals, records, onSubmit }: any) {
  const lactating = animals.filter((animal: any) => animal.herd_category === 'LACTATING_COW' || animal.production_status === 'MILKING');
  return <div className="grid-2"><section className="card"><div className="card-head"><h3>Record a milking session</h3><button>Owner entry</button></div>{lactating.map((animal: any) => <form className="milking-form" key={animal.animal_id} onSubmit={e => onSubmit(animal.animal_id, e)}><strong>{animal.name}</strong><input name="production_date" type="date" defaultValue={today()}/><select name="session_type"><option>MORNING</option><option>EVENING</option><option>ADDITIONAL</option></select><input name="quantity" type="number" step=".1" min=".1" placeholder="Produced liters" required/><input name="saleable_quantity" type="number" step=".1" min="0" placeholder="Approved saleable liters" required/><input name="withheld_quantity" type="number" step=".1" min="0" placeholder="Withheld liters"/><input name="withholding_reason" placeholder="Withholding reason if needed"/><input name="operator" placeholder="Operator"/><button className="secondary">Save session</button></form>)}</section><section className="card"><div className="card-head"><h3>Recent production</h3><button>Recorded rows</button></div><div className="animal-history">{records.slice(0, 30).map((record: any) => <div key={record.dairy_record_id}><span>{record.production_date} · {record.session_type || 'DAILY'} · {record.animal_id}</span><strong>{record.quantity} {record.unit}</strong></div>)}</div></section></div>;
}

function FeedView({ feed, onSaved }: any) {
  const save = async (event: React.FormEvent<HTMLFormElement>) => { event.preventDefault(); const form = new FormData(event.currentTarget); await fetch(API + '/dairy/feed/purchases', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ feed_type: form.get('feed_type'), quantity: Number(form.get('quantity')), unit: form.get('unit'), cost_per_unit: Number(form.get('cost_per_unit')), dry_matter_pct: Number(form.get('dry_matter_pct')) || null, received_date: form.get('received_date'), supplier: form.get('supplier') }) }); onSaved(); };
  return <div className="grid-2"><section className="card"><div className="card-head"><h3>Feed inventory</h3><button>Dry matter is explicit</button></div><div className="feed-list">{(feed.feeds || []).map((item: any) => <div className="feed-row" key={item.feed_id}><PixelIcon kind="crate" size={28}/><span><strong>{item.feed_type}</strong><small>{item.quantity} {item.unit} · {item.dry_matter_pct == null ? 'DM unknown' : (item.dry_matter_pct * 100).toFixed(0) + '% DM'}</small></span><b>{money(item.cost_per_unit)}/{item.unit}</b></div>)}</div></section><section className="card"><div className="card-head"><h3>Record feed purchase</h3><button>Creates finance expense</button></div><form className="mini-form" onSubmit={save}><label>Feed type<input name="feed_type" defaultValue="Hay"/></label><label>Quantity<input name="quantity" type="number" step=".1" required/></label><label>Unit<input name="unit" defaultValue="lb"/></label><label>Cost per unit<input name="cost_per_unit" type="number" step=".01" required/></label><label>Dry matter fraction<input name="dry_matter_pct" type="number" step=".01" min="0" max="1" defaultValue=".85"/></label><label>Received date<input name="received_date" type="date" defaultValue={today()}/></label><label>Supplier<input name="supplier"/></label><button className="primary">Save purchase</button></form></section></div>;
}

function InventoryView({ inventory, specs, onSubmit }: any) {
  return <div className="grid-2"><section className="card"><div className="card-head"><h3>Milk collection</h3><button>Shared inventory ledger</button></div><form className="mini-form" onSubmit={onSubmit}><label>Collection date<input name="collection_date" type="date" defaultValue={today()}/></label><label>Total collected (L)<input name="quantity_collected" type="number" step=".1" required/></label><label>Approved (L)<input name="approved_quantity" type="number" step=".1" required/></label><label>Withheld (L)<input name="withheld_quantity" type="number" step=".1" defaultValue="0"/></label><label>Quality status<select name="quality_status"><option>PENDING</option><option>RELEASED</option><option>HOLD</option></select></label><label>Sell-by date<input name="sell_by_date" type="date"/></label><button className="primary">Create collection lot</button></form></section><section className="card"><div className="card-head"><h3>Dairy inventory</h3><button>No competing ledger</button></div><div className="inventory-mini">{(inventory.lots || []).map((lot: any) => <div key={lot.lot_id}><PixelIcon kind="milk" size={26}/><span><strong>{lot.product_name}</strong><small>{lot.lot_id} · {lot.available} {lot.quantity_unit} · sell-by {lot.sell_by_date || 'not recorded'}</small></span><b>{lot.lot_status}</b></div>)}</div><h4>Processing assumptions</h4>{specs.map((spec: any) => <p className="section-note" key={spec.spec_id}>{spec.product_name}: {spec.input_quantity_per_output} L input → 1 {spec.output_unit} output · {spec.shelf_life_days} day shelf life.</p>)}</section></div>;
}

function TaskWeatherView({ tasks, weather, onComplete }: any) {
  return <div className="grid-2"><section className="card"><div className="card-head"><h3>Dairy task board</h3><button>Owner-controlled</button></div><div className="task-list">{tasks.map((task: any) => <div className="task-row" key={task.task_id}><PixelIcon kind={task.category === 'MILKING' ? 'milk' : 'worker'} size={26}/><span><strong>{task.title}</strong><small>{task.priority} · due {task.due_date} · {task.assigned_worker || 'Unassigned'}</small></span>{task.status !== 'COMPLETED' && <button className="secondary" onClick={() => onComplete(task.task_id)}>Complete</button>}</div>)}</div></section><section className="card"><div className="card-head"><h3>Outdoor herd weather risk</h3><button>{weather?.data_status || 'Unavailable'}</button></div><div className="dairy-weather-box"><strong>{weather?.temperature_f ?? 'N/A'}°F · RH {weather?.relative_humidity_pct ?? 'N/A'}%</strong><b>THI {weather?.thi ?? 'N/A'} · {weather?.thi_status || 'INSUFFICIENT_DATA'}</b><p>{weather?.note || 'Weather data unavailable; no live value is substituted.'}</p><small>Source: {weather?.source || 'Unavailable'} · {weather?.source_timestamp || '—'}</small></div></section></div>;
}
