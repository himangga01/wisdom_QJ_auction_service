import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { ApartmentSummary, TradeType } from '../../types/realEstate'
import { getTradeMetrics } from '../../utils/dashboard'
import { formatKoreanPrice, tradeTypeLabels } from '../../utils/formatters'

interface MarketChartsProps {
  apartment: ApartmentSummary
}

const tradeColors = ['#059669', '#2563eb', '#f59e0b']

export function MarketCharts({ apartment }: MarketChartsProps) {
  const tradeTypes: TradeType[] = ['sale', 'jeonse', 'monthly']
  const chartData = tradeTypes.map((tradeType) => {
    const metrics = getTradeMetrics(apartment, tradeType)
    return {
      tradeType,
      name: tradeType === 'monthly' ? '월세 보증금' : tradeTypeLabels[tradeType],
      average: Number((metrics.averagePrice / 100_000_000).toFixed(2)),
      count: metrics.count,
      monthlyRent: metrics.averageMonthlyRent,
    }
  })

  return (
    <section className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]" aria-label="선택 아파트 호가 현황">
      <article className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
        <h2 className="text-xl font-black text-slate-950">거래 유형별 평균 호가</h2>
        <p className="mt-1 text-sm text-slate-500">현재 선택한 아파트의 매매·전세·월세 보증금 평균입니다.</p>
        <div className="mt-6 h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 10, right: 10, left: -12, bottom: 8 }}>
              <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} />
              <YAxis axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <Tooltip cursor={{ fill: '#f8fafc' }} formatter={(value) => [`${value}억원`, '평균 호가']} />
              <Bar dataKey="average" radius={[10, 10, 0, 0]} maxBarSize={74}>{chartData.map((entry, index) => <Cell key={entry.tradeType} fill={tradeColors[index]} />)}</Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </article>

      <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
        {chartData.map((item, index) => (
          <article key={item.tradeType} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between"><p className="font-extrabold text-slate-600">{tradeTypeLabels[item.tradeType]}</p><span className="rounded-full px-2.5 py-1 text-xs font-extrabold" style={{ backgroundColor: `${tradeColors[index]}16`, color: tradeColors[index] }}>{item.count}건</span></div>
            <p className="mt-3 text-2xl font-black text-slate-950">{item.average ? formatKoreanPrice(item.average * 100_000_000) : '-'}</p>
            {item.tradeType === 'monthly' && item.monthlyRent ? <p className="mt-1 text-sm font-bold text-amber-700">월 {Math.round(item.monthlyRent / 10_000)}만원</p> : <p className="mt-1 text-xs text-slate-400">현재 매물 평균 호가</p>}
          </article>
        ))}
      </div>
    </section>
  )
}
