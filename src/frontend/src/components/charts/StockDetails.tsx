'use client';

import React from 'react';
import { cn, formatNumber } from '@/lib/utils';

interface StockDetailsProps {
  open: number;
  high: number;
  low: number;
  marketCap: number;
  peRatio: number;
  volume: number;
  yearHigh: number;
  yearLow: number;
  exchange: string; // Optional prop for exchange
  isChartInsightRoute?: boolean;
}

const StockDetails: React.FC<StockDetailsProps> = ({
  open,
  high,
  low,
  marketCap,
  peRatio,
  volume,
  yearHigh,
  yearLow,
  exchange,
  isChartInsightRoute,
}) => {
  return (
    <div className={cn('stock-details-grid', isChartInsightRoute && '!gap-[10px] !grid-cols-4')}>
      <div className="stock-detail-item">
        <span className="stock-detail-label">Open</span>
        <span className="stock-detail-value">{open ? open.toFixed(2) : '-'}</span>
      </div>

      <div className="stock-detail-item">
        <span className="stock-detail-label">High</span>
        <span className="stock-detail-value">{high ? high.toFixed(2) : '-'}</span>
      </div>

      <div className="stock-detail-item">
        <span className="stock-detail-label">Low</span>
        <span className="stock-detail-value">{low ? low.toFixed(2) : '-'}</span>
      </div>

      <div className="stock-detail-item">
        <span className="stock-detail-label">Market Cap</span>
        <span className="stock-detail-value">{marketCap ? formatNumber(marketCap) : '-'}</span>
      </div>

      {/* {exchange !== 'CRYPTO' && (
        <div className="stock-detail-item">
          <span className="stock-detail-label">P/E Ratio</span>
          <span className="stock-detail-value">{peRatio ? peRatio.toFixed(2) : '-'}</span>
        </div>
      )} */}

      <div className="stock-detail-item">
        <span className="stock-detail-label">Volume</span>
        <span className="stock-detail-value">{volume ? formatNumber(volume) : '-'}</span>
      </div>

      <div className="stock-detail-item">
        <span className="stock-detail-label">Year High</span>
        <span className="stock-detail-value">{yearHigh ? yearHigh.toFixed(2) : '-'}</span>
      </div>

      <div className="stock-detail-item">
        <span className="stock-detail-label">Year Low</span>
        <span className="stock-detail-value">{yearLow ? yearLow.toFixed(2) : '-'}</span>
      </div>
    </div>
  );
};

export default StockDetails;
