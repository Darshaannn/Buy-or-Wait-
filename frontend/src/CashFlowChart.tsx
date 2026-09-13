import React from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
} from 'recharts';
import type { ForecastDayPoint } from './types';

interface Props {
  data: ForecastDayPoint[];
  minBuffer: number;
  currency: string;
}

export const CashFlowChart: React.FC<Props> = ({ data, minBuffer, currency }) => {
  if (!data || data.length === 0) return null;

  // Format date for chart axis: e.g. "15 Sep"
  const formattedData = data.map((d) => {
    const dt = new Date(d.date);
    const day = dt.getDate();
    const month = dt.toLocaleString('en-US', { month: 'short' });
    return {
      ...d,
      displayDate: `${day} ${month}`,
    };
  });

  const minBal = Math.min(...data.map((d) => d.balance), minBuffer);
  const maxBal = Math.max(...data.map((d) => d.balance), minBuffer);
  const yMin = Math.floor(Math.max(0, minBal * 0.85));
  const yMax = Math.ceil(maxBal * 1.1);

  return (
    <div style={{ width: '100%', height: 320 }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={formattedData} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
          <defs>
            <linearGradient id="balanceGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#2563eb" stopOpacity={0.25} />
              <stop offset="95%" stopColor="#2563eb" stopOpacity={0.0} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="displayDate"
            stroke="#94a3b8"
            fontSize={11}
            tickLine={false}
            axisLine={{ stroke: '#e2e8f0' }}
            interval={14}
          />
          <YAxis
            stroke="#94a3b8"
            fontSize={11}
            tickLine={false}
            axisLine={false}
            domain={[yMin, yMax]}
            tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
          />
          <Tooltip
            content={({ active, payload }) => {
              if (active && payload && payload.length) {
                const pt = payload[0].payload as ForecastDayPoint & { displayDate: string };
                return (
                  <div
                    style={{
                      background: '#ffffff',
                      border: '1px solid #e2e8f0',
                      borderRadius: 8,
                      padding: '10px 14px',
                      boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)',
                      fontSize: 12,
                    }}
                  >
                    <div style={{ fontWeight: 700, color: '#0f172a', marginBottom: 4 }}>
                      {pt.displayDate}
                    </div>
                    <div style={{ color: '#2563eb', fontWeight: 600 }}>
                      Projected Balance: {currency} {Number(pt.balance).toLocaleString()}
                    </div>
                    <div style={{ color: '#ef4444', fontSize: 11, marginTop: 2 }}>
                      Safety Buffer Floor: {currency} {Number(minBuffer).toLocaleString()}
                    </div>
                    {pt.income_occurred && (
                      <div style={{ color: '#10b981', fontSize: 11, marginTop: 4 }}>
                        + Income / Cash inflow
                      </div>
                    )}
                    {pt.payment_occurred && (
                      <div style={{ color: '#f59e0b', fontSize: 11, marginTop: 2 }}>
                        - Purchase payment scheduled ({currency} {Number(pt.payment_amount).toLocaleString()})
                      </div>
                    )}
                  </div>
                );
              }
              return null;
            }}
          />
          <ReferenceLine
            y={minBuffer}
            stroke="#ef4444"
            strokeDasharray="4 4"
            label={{
              value: `Safety Floor (${currency} ${Number(minBuffer).toLocaleString()})`,
              position: 'insideBottomRight',
              fill: '#ef4444',
              fontSize: 11,
              fontWeight: 600,
            }}
          />
          <Area
            type="monotone"
            dataKey="balance"
            stroke="#2563eb"
            strokeWidth={2.5}
            fillOpacity={1}
            fill="url(#balanceGradient)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};
