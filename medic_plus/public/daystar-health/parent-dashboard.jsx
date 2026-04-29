// Dashboard
function Sparkline({ data, color = 'var(--accent)', height = 56, fill = true }) {
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const w = 100;
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * w},${height - ((v - min) / range) * (height - 6) - 3}`).join(' ');
  const area = `0,${height} ${pts} ${w},${height}`;
  const id = `spk-${Math.random().toString(36).slice(2, 7)}`;
  return (
    <svg viewBox={`0 0 ${w} ${height}`} preserveAspectRatio="none" style={{ width: '100%', height }}>
      {fill && <>
        <defs>
          <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor={color} stopOpacity="0.18" />
            <stop offset="1" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
        <polygon points={area} fill={`url(#${id})`} />
      </>}
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function StackBar({ values, colors, labels }) {
  const total = values.reduce((a, b) => a + b, 0);
  return (
    <div>
      <div style={{ display: 'flex', height: 8, borderRadius: 999, overflow: 'hidden', background: 'var(--bg-subtle)' }}>
        {values.map((v, i) => (
          <div key={i} style={{ width: `${(v / total) * 100}%`, background: colors[i] }} />
        ))}
      </div>
      <div style={{ display: 'flex', gap: 14, marginTop: 12, flexWrap: 'wrap' }}>
        {values.map((v, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: colors[i] }} />
            <span style={{ color: 'var(--text-muted)' }}>{labels[i]}</span>
            <span className="mono" style={{ fontWeight: 500 }}>{v}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function DashboardScreen({ go }) {
  const [range, setRange] = useState('30D');
  const products = window.DSM_DATA.PRODUCTS;
  const lowStock = products.filter(p => p.status === 'Low stock' || p.status === 'Out of stock');

  const kpis = [
    { label: 'Total inventory value', value: '$2.84M', delta: '+4.2%', up: true, trend: [62, 65, 68, 64, 70, 72, 75, 73, 78, 80, 82, 85] },
    { label: 'Units on hand', value: '14,762', delta: '+1.8%', up: true, trend: [50, 52, 55, 58, 56, 60, 62, 64, 63, 66, 68, 70] },
    { label: '30-day sell-through', value: '68.4%', delta: '+6.1%', up: true, trend: [40, 45, 48, 52, 55, 58, 60, 62, 65, 66, 68, 68] },
    { label: 'Low stock SKUs', value: '24', delta: '+3', up: false, trend: [10, 12, 14, 13, 16, 18, 20, 19, 22, 21, 23, 24] },
  ];

  // Sales activity chart
  const weeks = [
    { w: 'W1', sales: 28200, units: 1840 },
    { w: 'W2', sales: 31400, units: 2010 },
    { w: 'W3', sales: 26800, units: 1720 },
    { w: 'W4', sales: 38900, units: 2480 },
    { w: 'W5', sales: 42100, units: 2680 },
    { w: 'W6', sales: 39400, units: 2510 },
    { w: 'W7', sales: 45800, units: 2920 },
    { w: 'W8', sales: 48200, units: 3080 },
  ];

  return (
    <div className="page fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24, gap: 16, flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 600, margin: '0 0 4px', letterSpacing: '-0.02em' }}>Dashboard</h1>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: 0 }}>Overview of inventory, sell-through, and replenishment across 4 stores.</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <div className="segment">
            {['7D', '30D', '90D', 'YTD'].map(r => (
              <button key={r} className={range === r ? 'active' : ''} onClick={() => setRange(r)}>{r}</button>
            ))}
          </div>
          <button className="btn btn-secondary btn-sm"><window.Icons.Download size={14} /> Export</button>
          <button className="btn btn-primary btn-sm" onClick={() => go('products')}><window.Icons.Plus size={14} /> Add product</button>
        </div>
      </div>

      {/* KPI tiles */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 'var(--gap)', marginBottom: 'var(--gap)' }}>
        {kpis.map((k, i) => (
          <div key={i} className="kpi-tile">
            <div className="kpi-label">{k.label}</div>
            <div className="kpi-value">{k.value}</div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
              <span className={`kpi-delta ${k.up ? 'up' : 'down'}`}>
                {k.up ? <window.Icons.Up /> : <window.Icons.Down />} {k.delta}
              </span>
              <div style={{ width: 80, opacity: 0.8 }}>
                <Sparkline data={k.trend} color={k.up ? '#10b981' : '#ef4444'} height={28} />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Mid row */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 'var(--gap)', marginBottom: 'var(--gap)' }}>
        {/* Sales activity */}
        <div className="card">
          <div className="card-header">
            <div>
              <h3 className="card-title">Sales activity</h3>
              <div style={{ display: 'flex', gap: 24, marginTop: 8 }}>
                <div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 2 }}>Revenue</div>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                    <span className="mono" style={{ fontSize: 20, fontWeight: 600 }}>$300,800</span>
                    <span className="kpi-delta up"><window.Icons.Up /> 8.2%</span>
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 2 }}>Units sold</div>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                    <span className="mono" style={{ fontSize: 20, fontWeight: 600 }}>19,240</span>
                    <span className="kpi-delta up"><window.Icons.Up /> 5.4%</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div className="card-pad" style={{ paddingTop: 8 }}>
            <SalesChart weeks={weeks} />
          </div>
        </div>

        {/* Inventory health */}
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Inventory health</h3>
            <button className="btn btn-ghost btn-sm" onClick={() => go('products')}>See all</button>
          </div>
          <div className="card-pad">
            <div style={{ marginBottom: 18 }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>Total asset value</div>
              <div className="mono" style={{ fontSize: 28, fontWeight: 600, letterSpacing: '-0.02em' }}>$2,841,920</div>
            </div>
            <StackBar
              values={[78, 16, 6]}
              colors={['#10b981', '#f59e0b', '#ef4444']}
              labels={['In stock', 'Low stock', 'Out of stock']}
            />
            <div style={{ borderTop: '1px solid var(--border)', marginTop: 18, paddingTop: 14 }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 10, fontWeight: 500 }}>Needs replenishment</div>
              {lowStock.slice(0, 3).map(p => (
                <div key={p.id} onClick={() => go('product', p.id)} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0', borderBottom: '1px solid var(--border)', cursor: 'pointer' }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 12.5, fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{p.name}</div>
                    <div className="mono" style={{ fontSize: 10.5, color: 'var(--text-dim)' }}>{p.id}</div>
                  </div>
                  <span className="mono" style={{ fontSize: 12, color: 'var(--text-muted)' }}>Qty {p.stock}</span>
                  <button className="btn btn-secondary btn-sm" onClick={(e) => { e.stopPropagation(); }}>Order</button>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Bottom row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--gap)' }}>
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Top movers — last 30 days</h3>
            <button className="btn btn-ghost btn-sm">View all</button>
          </div>
          <div>
            {products.slice(0, 5).map((p, i) => (
              <div key={p.id} onClick={() => go('product', p.id)} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 20px', borderBottom: i < 4 ? '1px solid var(--border)' : 'none', cursor: 'pointer' }}>
                <div className="placeholder-img" style={{ width: 40, height: 40, fontSize: 0 }}></div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{p.name}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-dim)', display: 'flex', gap: 8 }}>
                    <span className="mono">{p.id}</span>
                    <span>•</span>
                    <span>{p.category}</span>
                  </div>
                </div>
                <div style={{ width: 80 }}>
                  <Sparkline data={p.trend} color="#10b981" height={26} />
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div className="mono" style={{ fontSize: 13, fontWeight: 500 }}>{p.sold30d.toLocaleString()}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-dim)' }}>units</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Open purchase orders</h3>
            <button className="btn btn-ghost btn-sm">All POs</button>
          </div>
          <div>
            {window.DSM_DATA.ORDERS.slice(0, 5).map((o, i) => (
              <div key={o.id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 20px', borderBottom: i < 4 ? '1px solid var(--border)' : 'none' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, fontFamily: 'var(--font-mono)' }}>{o.id}</div>
                  <div style={{ fontSize: 11.5, color: 'var(--text-dim)' }}>{o.vendor} · {o.items} items</div>
                </div>
                <span className={`badge ${o.status === 'Delivered' ? 'badge-success' : o.status === 'In transit' ? 'badge-info' : o.status === 'Cancelled' ? 'badge-danger' : 'badge-warn'}`}>{o.status}</span>
                <div className="mono" style={{ fontSize: 13, fontWeight: 500, minWidth: 80, textAlign: 'right' }}>${o.amount.toLocaleString()}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function SalesChart({ weeks }) {
  const w = 600, h = 200;
  const pad = { l: 36, r: 12, t: 12, b: 28 };
  const max = Math.max(...weeks.map(d => d.sales)) * 1.1;
  const x = i => pad.l + (i / (weeks.length - 1)) * (w - pad.l - pad.r);
  const y = v => h - pad.b - (v / max) * (h - pad.t - pad.b);
  const linePts = weeks.map((d, i) => `${x(i)},${y(d.sales)}`).join(' ');
  const areaPts = `${pad.l},${h - pad.b} ${linePts} ${x(weeks.length - 1)},${h - pad.b}`;
  const unitsPts = weeks.map((d, i) => `${x(i)},${y(d.units * 15)}`).join(' ');
  const grid = [0, 0.25, 0.5, 0.75, 1];
  return (
    <svg viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', height: 'auto' }}>
      <defs>
        <linearGradient id="salesg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#f97316" stopOpacity="0.22" />
          <stop offset="1" stopColor="#f97316" stopOpacity="0" />
        </linearGradient>
      </defs>
      {grid.map((g, i) => (
        <g key={i}>
          <line x1={pad.l} x2={w - pad.r} y1={pad.t + g * (h - pad.t - pad.b)} y2={pad.t + g * (h - pad.t - pad.b)} stroke="var(--border)" strokeDasharray="2 4" />
          <text x={pad.l - 8} y={pad.t + g * (h - pad.t - pad.b) + 4} textAnchor="end" fontSize="9" fill="var(--text-dim)" fontFamily="var(--font-mono)">${Math.round((max * (1 - g)) / 1000)}k</text>
        </g>
      ))}
      <polygon points={areaPts} fill="url(#salesg)" />
      <polyline points={linePts} fill="none" stroke="#f97316" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <polyline points={unitsPts} fill="none" stroke="#3b82f6" strokeWidth="1.5" strokeDasharray="4 3" strokeLinecap="round" />
      {weeks.map((d, i) => (
        <g key={i}>
          <circle cx={x(i)} cy={y(d.sales)} r="3" fill="#f97316" stroke="var(--surface)" strokeWidth="1.5" />
          <text x={x(i)} y={h - 10} textAnchor="middle" fontSize="10" fill="var(--text-dim)" fontFamily="var(--font-mono)">{d.w}</text>
        </g>
      ))}
      <g transform={`translate(${w - pad.r - 130}, ${pad.t + 4})`}>
        <rect width="130" height="36" fill="var(--surface)" stroke="var(--border)" rx="6" />
        <circle cx="10" cy="13" r="3" fill="#f97316" />
        <text x="20" y="17" fontSize="10" fill="var(--text-muted)">Revenue</text>
        <line x1="6" x2="14" y1="27" y2="27" stroke="#3b82f6" strokeDasharray="2 2" strokeWidth="1.5" />
        <text x="20" y="30" fontSize="10" fill="var(--text-muted)">Units</text>
      </g>
    </svg>
  );
}

window.DashboardScreen = DashboardScreen;
window.Sparkline = Sparkline;
