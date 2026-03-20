/**
 * Sentinel — SparklineChart Component
 *
 * Inline 60-second traffic sparkline using Recharts AreaChart.
 * Renders in a compact 120×32px area next to each port row.
 */

import React, { useMemo } from 'react';
import { AreaChart, Area, ResponsiveContainer } from 'recharts';
import type { SparklinePoint } from '../types';

interface SparklineChartProps {
  data: SparklinePoint[];
  width?: number;
  height?: number;
}

const SparklineChart: React.FC<SparklineChartProps> = ({
  data,
  width = 120,
  height = 32,
}) => {
  const chartData = useMemo(() => {
    return data.map(p => ({
      t: p.t,
      in: p.kbIn,
      out: p.kbOut,
    }));
  }, [data]);

  if (chartData.length < 2) {
    return (
      <div
        style={{ width, height, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
        className="sparkline-empty"
      >
        <span style={{ fontSize: '9px', color: 'var(--text-muted)', opacity: 0.4 }}>—</span>
      </div>
    );
  }

  return (
    <div style={{ width, height }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="sparkGradIn" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--accent-blue)" stopOpacity={0.6} />
              <stop offset="100%" stopColor="var(--accent-blue)" stopOpacity={0.05} />
            </linearGradient>
            <linearGradient id="sparkGradOut" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--accent-orange)" stopOpacity={0.6} />
              <stop offset="100%" stopColor="var(--accent-orange)" stopOpacity={0.05} />
            </linearGradient>
          </defs>
          <Area
            type="monotone"
            dataKey="in"
            stroke="var(--accent-blue)"
            strokeWidth={1.2}
            fill="url(#sparkGradIn)"
            isAnimationActive={false}
          />
          <Area
            type="monotone"
            dataKey="out"
            stroke="var(--accent-orange)"
            strokeWidth={1.2}
            fill="url(#sparkGradOut)"
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};

export default React.memo(SparklineChart);
