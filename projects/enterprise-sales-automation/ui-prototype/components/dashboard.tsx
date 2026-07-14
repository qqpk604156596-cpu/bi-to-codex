"use client";

import { useMemo, useState } from "react";
import { BarChart3, CalendarDays, ChevronDown, CircleHelp, RotateCcw, Search, TrendingUp } from "lucide-react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { baseline, countrySales, customerSales, monthlySales, productSales } from "@/lib/fixture";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

const pages = ["Executive Overview", "Product & Trend Analysis", "Customer & Country Analysis"] as const;
type PageName = (typeof pages)[number];

function moneyCompact(value: number) {
  if (value >= 1_000_000) return `£${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `£${Math.round(value / 1_000)}K`;
  return `£${value.toFixed(2)}`;
}

function numberCompact(value: number) {
  return value >= 1_000_000 ? `${(value / 1_000_000).toFixed(1)}M` : `${Math.round(value / 1_000)}K`;
}

function Kpi({ label, value, hint, testId }: { label: string; value: string; hint: string; testId?: string }) {
  return (
    <Card className="kpi-card" data-testid={testId}>
      <div className="kpi-topline">
        <span>{label}</span>
        <TrendingUp aria-hidden="true" size={16} />
      </div>
      <strong>{value}</strong>
      <small>{hint}</small>
    </Card>
  );
}

function NativeSelect({ label, value, values, onChange }: { label: string; value: string; values: string[]; onChange: (value: string) => void }) {
  return (
    <label className="select-field">
      <span>{label}</span>
      <select aria-label={label} value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="All">All</option>
        {values.map((item) => <option key={item} value={item}>{item}</option>)}
      </select>
    </label>
  );
}

function PeriodFilter({ selected, onApply }: { selected: string[]; onApply: (months: string[]) => void }) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(selected);
  const label = selected.length === 0 ? "All periods" : selected.length === 1 ? selected[0] : `${selected.length} months`;

  function toggle(month: string) {
    setDraft((current) => current.includes(month) ? current.filter((item) => item !== month) : [...current, month]);
  }

  return (
    <div className="period-filter">
      <span className="filter-label">YearMonth</span>
      <Button className="filter-trigger" aria-label="YearMonth filter" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span><CalendarDays aria-hidden="true" size={15} />{label}</span><ChevronDown aria-hidden="true" size={16} />
      </Button>
      {open && (
        <div className="filter-popover">
          <div className="filter-search"><Search aria-hidden="true" size={15} /><span>Choose one or more months</span></div>
          <div className="month-options">
            {monthlySales.map(({ month }) => (
              <label key={month}>
                <input type="checkbox" aria-label={month} checked={draft.includes(month)} onChange={() => toggle(month)} />
                <span>{month}</span>
              </label>
            ))}
          </div>
          <div className="filter-actions">
            <Button className="button-ghost" onClick={() => setDraft([])}>All</Button>
            <Button className="button-primary" aria-label="Apply YearMonth" onClick={() => { onApply(draft); setOpen(false); }}>Apply</Button>
          </div>
        </div>
      )}
    </div>
  );
}

function HorizontalBars({ title, data, onSelect }: { title: string; data: { label: string; value: number }[]; onSelect?: (label: string) => void }) {
  const max = Math.max(...data.map((item) => item.value));
  return (
    <Card className="chart-card">
      <div className="chart-heading"><div><span className="eyebrow">RANKING</span><h2>{title}</h2></div><span className="chart-unit">Net Sales</span></div>
      <div className="bar-list">
        {data.map((item, index) => (
          <button key={item.label} type="button" className="bar-row" aria-label={onSelect ? `Filter ${item.label}` : item.label} onClick={() => onSelect?.(item.label)}>
            <span className="bar-rank">{String(index + 1).padStart(2, "0")}</span>
            <span className="bar-label">{item.label}</span>
            <span className="bar-track"><span className="bar-fill" style={{ width: `${Math.max(4, item.value / max * 100)}%` }} /></span>
            <strong>{moneyCompact(item.value)}</strong>
          </button>
        ))}
      </div>
    </Card>
  );
}

function TrendChart() {
  return (
    <Card className="chart-card trend-card">
      <div className="chart-heading"><div><span className="eyebrow">PERFORMANCE</span><h2>Monthly Net Sales</h2></div><span className="trend-legend"><i />Net Sales</span></div>
      <div className="line-chart" role="img" aria-label="Monthly net sales line chart">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={monthlySales} margin={{ left: 0, right: 12, top: 12, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="#e7eaf0" strokeDasharray="3 3" />
            <XAxis dataKey="month" tick={{ fill: "#647084", fontSize: 10 }} interval={3} axisLine={false} tickLine={false} />
            <YAxis tickFormatter={(value) => `£${(value / 1_000_000).toFixed(1)}M`} tick={{ fill: "#647084", fontSize: 10 }} axisLine={false} tickLine={false} width={48} />
            <Tooltip formatter={(value) => moneyCompact(Number(value))} contentStyle={{ borderRadius: 10, borderColor: "#dfe3ea" }} />
            <Line type="monotone" dataKey="netSales" stroke="#0e7490" strokeWidth={3} dot={false} activeDot={{ r: 5, fill: "#0e7490" }} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

export function Dashboard() {
  const [page, setPage] = useState<PageName>(pages[0]);
  const [months, setMonths] = useState<string[]>([]);
  const [country, setCountry] = useState("All");
  const [stockCode, setStockCode] = useState("All");
  const [customerId, setCustomerId] = useState("All");

  const scale = useMemo(() => {
    const countryScale = country === "All" ? 1 : (countrySales.find((item) => item.country === country)?.netSales ?? 0) / baseline.netSales;
    const periodScale = months.length === 0 ? 1 : months.reduce((sum, month) => sum + (monthlySales.find((item) => item.month === month)?.netSales ?? 0), 0) / baseline.netSales;
    return Math.max(countryScale * periodScale, 0);
  }, [country, months]);

  const selectedMonth = months.length === 1 ? monthlySales.findIndex((item) => item.month === months[0]) : -1;
  const current = selectedMonth >= 0 ? monthlySales[selectedMonth] : undefined;
  const previous = selectedMonth > 0 ? monthlySales[selectedMonth - 1] : undefined;
  const priorYear = selectedMonth >= 12 ? monthlySales[selectedMonth - 12] : undefined;
  const mom = current && previous ? `${((current.netSales / previous.netSales - 1) * 100).toFixed(1)}%` : "--";
  const yoy = current && priorYear ? `${((current.netSales / priorYear.netSales - 1) * 100).toFixed(1)}%` : "--";

  function clearFilters() {
    setMonths([]);
    setCountry("All");
    setStockCode("All");
    setCustomerId("All");
  }

  const headerFilters = (
    <div className="filters" aria-label="Report filters">
      <PeriodFilter selected={months} onApply={setMonths} />
      <NativeSelect label="Country" value={country} values={countrySales.map((item) => item.country)} onChange={setCountry} />
      {page === "Product & Trend Analysis" && <NativeSelect label="StockCode" value={stockCode} values={productSales.map((item) => item.label)} onChange={setStockCode} />}
      {page === "Customer & Country Analysis" && <NativeSelect label="CustomerID" value={customerId} values={customerSales.map((item) => item.label)} onChange={setCustomerId} />}
      <Button className="clear-button" aria-label="Clear filters" onClick={clearFilters}><RotateCcw aria-hidden="true" size={15} />Reset</Button>
    </div>
  );

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-mark"><BarChart3 aria-hidden="true" size={20} /></div>
        <div><strong>Northstar Retail</strong><span>Business Intelligence</span></div>
        <div className="data-status"><i />Validated aggregate fixture · 24 months</div>
        <Button className="help-button" aria-label="About this prototype"><CircleHelp aria-hidden="true" size={18} /></Button>
      </header>

      <nav className="page-tabs" role="tablist" aria-label="Report pages">
        {pages.map((name, index) => (
          <button key={name} role="tab" aria-selected={page === name} className={page === name ? "active" : ""} onClick={() => setPage(name)}>
            <span>{String(index + 1).padStart(2, "0")}</span>{name}
          </button>
        ))}
      </nav>

      <main>
        <div className="page-header">
          <div><span className="eyebrow">ENTERPRISE SALES · DECISION WORKSPACE</span><h1>{page}</h1><p>Track revenue health, identify commercial drivers, and focus the next management action.</p></div>
          {headerFilters}
        </div>

        {page === "Executive Overview" && (
          <>
            <section className="kpi-grid three">
              <Kpi label="Net Sales" value={moneyCompact(baseline.netSales * scale)} hint="Recognised sales after cancellations" testId="kpi-net-sales" />
              <Kpi label="Order Count" value={numberCompact(baseline.orderCount * scale)} hint="Distinct non-cancelled invoices" />
              <Kpi label="Units Sold" value={numberCompact(baseline.unitsSold * scale)} hint="Positive quantity sold" />
              <Kpi label="Active Customers" value={numberCompact(baseline.activeCustomers * scale)} hint="Known purchasing customers" />
              <Kpi label="Average Order Value" value={moneyCompact(baseline.averageOrderValue * Math.max(scale, 0.35))} hint="Net sales per order" />
              <Kpi label="Cancellation Rate" value={`${(baseline.cancellationRate * 100).toFixed(2)}%`} hint="Cancelled orders as share of all orders" />
            </section>
            <section className="visual-grid"><TrendChart /><HorizontalBars title="Net Sales by Country" data={countrySales.map((item) => ({ label: item.country, value: item.netSales }))} onSelect={setCountry} /></section>
          </>
        )}

        {page === "Product & Trend Analysis" && (
          <>
            <section className="kpi-grid product">
              <Kpi label="Net Sales" value={moneyCompact(baseline.netSales * scale)} hint="Filtered commercial value" testId="kpi-net-sales" />
              <Kpi label="Units Sold" value={numberCompact(baseline.unitsSold * scale)} hint="Positive quantity sold" />
              <Kpi label="Cancelled Sales" value={moneyCompact(baseline.cancelledSales * scale)} hint="Value removed by cancellations" />
              <Kpi label="Sales MoM %" value={mom} hint="Single-month comparison only" testId="kpi-sales-mom-pct" />
              <Kpi label="Sales YoY %" value={yoy} hint="Single-month comparison only" testId="kpi-sales-yoy-pct" />
            </section>
            <section className="visual-grid"><TrendChart /><HorizontalBars title="Net Sales by Product" data={productSales} /></section>
          </>
        )}

        {page === "Customer & Country Analysis" && (
          <>
            <section className="kpi-grid customer">
              <Kpi label="Net Sales" value={moneyCompact(baseline.netSales * scale)} hint="Filtered commercial value" testId="kpi-net-sales" />
              <Kpi label="Active Customers" value={numberCompact(baseline.activeCustomers * scale)} hint="Known purchasing customers" />
              <Kpi label="Average Order Value" value={moneyCompact(baseline.averageOrderValue * Math.max(scale, 0.35))} hint="Net sales per order" />
              <Kpi label="Cancellation Rate" value={`${(baseline.cancellationRate * 100).toFixed(2)}%`} hint="Cancelled order share" />
            </section>
            <section className="visual-grid equal"><HorizontalBars title="Net Sales by Country" data={countrySales.slice(0, 5).map((item) => ({ label: item.country, value: item.netSales }))} onSelect={setCountry} /><HorizontalBars title="Net Sales by Customer" data={customerSales} /></section>
            <aside className="rls-note"><strong>Security scope:</strong> Dynamic country RLS is simulated with public data. Power BI Service identity validation remains unverified.</aside>
          </>
        )}
      </main>
    </div>
  );
}
