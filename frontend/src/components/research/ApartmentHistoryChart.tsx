import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { ApartmentSummary } from '../../types/realEstate'

export function ApartmentHistoryChart({ apartment }: { apartment: ApartmentSummary }) {
  const data = apartment.history.map((point) => ({
    ...point,
    label: new Intl.DateTimeFormat('ko-KR', { month: 'numeric', day: 'numeric' }).format(new Date(point.collectedAt)),
  }))

  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 10, right: 15, left: -20, bottom: 0 }}>
          <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 11 }} />
          <YAxis allowDecimals={false} axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 11 }} />
          <Tooltip />
          <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
          <Line type="monotone" dataKey="saleCount" name="매매" stroke="#059669" strokeWidth={3} dot={{ r: 3 }} />
          <Line type="monotone" dataKey="jeonseCount" name="전세" stroke="#2563eb" strokeWidth={3} dot={{ r: 3 }} />
          <Line type="monotone" dataKey="monthlyCount" name="월세" stroke="#f59e0b" strokeWidth={3} dot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
