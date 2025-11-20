'use client';

import React, { useCallback, useEffect, useState } from 'react';
import StockHeader from './StockHeader';
import TimePeriodTabs from './TimePeriodTabs';
import StockChart from './StockChart';
import StockDetails from './StockDetails';
import { motion, AnimatePresence } from 'framer-motion';
import { BsChevronDown } from 'react-icons/bs';
import { cn } from '@/lib/utils';
import StockSparkLines from './StockSparkLines';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import HistoricalIcon from '../icons/HistoricalIcon';
import PredictiveIcon from '../icons/PredictiveIcon';
import { toast } from 'sonner';
import ApiServices from '@/services/ApiServices';
import { IChartData } from '@/types/chart-data';
import StockChart2 from './StockChart2';
import { ArrowRight } from 'lucide-react';
import { axiosInstance } from '@/services/axiosInstance';
import useWindowDimension from '@/hooks/useWindowDimension';
export interface RealTimeData {
  symbol: string | null;
  currency: string | null;
  name: string | null;
  price: number | null;
  changesPercentage: number | null;
  change: number | null;
  dayLow: number | null;
  dayHigh: number | null;
  yearHigh: number | null;
  yearLow: number | null;
  marketCap: number | null;
  priceAvg50: number | null;
  priceAvg200: number | null;
  exchange: string | null;
  volume: number | null;
  avgVolume: number | null;
  open: number | null;
  previousClose: number | null;
  eps: number | null;
  pe: number | null;
  earningsAnnouncement: string | null;
  sharesOutstanding: number | null;
  timestamp: number | null;
}

interface HistoricalData {
  date: string;
  open: string;
  high: string;
  low: string;
  close: string;
  volume: string;
}

export interface IFinanceData {
  realtime: RealTimeData;
  historical: {
    data: HistoricalData[];
    source: string;
    period?: string[]; // Optional, if periods are available
    is_active?: boolean;
  };
  chart_session_id: string;
  is_active?: boolean;
}

export interface FinanceChartProps {
  messageId: string;
  chart_data: IFinanceData[];
  loading?: boolean;
  handleModalOpen?: (
    key: string,
    messageId: string,
    exchange: string,
    ticker: string,
    chart_session_id: string
  ) => void;
  isModalView?: boolean;
  setCurrentTickerSymbol?: React.Dispatch<React.SetStateAction<any>>;
  setShowSpecificChartLoader?: React.Dispatch<React.SetStateAction<any>>;
  openSpecificChart?: string[];
  handleOpenSpecificChart?: (key: string) => void;
  financeChartModal?: boolean;
  isChartInsightRoute?: boolean;
  setLoading?: React.Dispatch<React.SetStateAction<boolean>>;
}

interface IActiveTabInterface {
  symbol: string;
  activeTab: 'historical' | 'prediction';
}

interface IPredictedChartData {
  symbol: string;
  data: IChartData[];
}

export interface ISelectedPeriodData {
  symbol: string;
  activePeriod: string;
}

const FinanceChart: React.FC<FinanceChartProps> = ({
  messageId,
  chart_data,
  loading,
  handleModalOpen,
  isModalView,
  setCurrentTickerSymbol,
  setShowSpecificChartLoader,
  openSpecificChart,
  handleOpenSpecificChart,
  financeChartModal,
  isChartInsightRoute,
  setLoading,
}) => {
  const [selectedPeriodData, setSelectedPeriodData] = useState<ISelectedPeriodData[]>([]);
  const [currentLoadingSymbolData, setCurrentLoadingSymbolData] = useState<string | null>(null);
  const [predictedChartData, setPredictedChartData] = useState<IPredictedChartData[]>([]); // Adjust type as needed
  const [predictedChartDataLoading, setPredictedChartDataLoading] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState<IActiveTabInterface[]>([]);
  const [data, setData] = useState<IFinanceData[]>([]);
  const [selectedPeriod, setSelectedPeriod] = useState('1M');
  const [modalPeriodTrigger, setModalPeriodTrigger] = useState(false);
  const [isDelisted, setIsDelisted] = useState(false);
  const { windowDimension } = useWindowDimension();
  const { width: windowWidth } = windowDimension;
  const islg = windowWidth >= 1024;
  const isXl = windowWidth >= 1280;

  const heightOfStockChart =
    isChartInsightRoute && isXl
      ? '350px'
      : isChartInsightRoute && islg
        ? '300px'
        : isChartInsightRoute
          ? '200px'
          : '240px';

  const handleMonthlyStockChartData = useCallback(
    async (period: string, message_id: string, exchange: string, symbol: string) => {
      const key = `${message_id}-${symbol}`;

      if (setCurrentTickerSymbol) {
        setCurrentTickerSymbol(symbol);
      }
      if (setShowSpecificChartLoader) {
        setShowSpecificChartLoader((prev: any) => [...prev, key]);
      }

      try {
        if (setLoading) {
          setLoading(true);
        }

        const response = await axiosInstance.post('/stock_data', {
          period,
          message_id,
          exchange_symbol: exchange,
          ticker: symbol,
        });

        const existingItem = data.find((item) => item.realtime.symbol === symbol);
        const existingRealtime = existingItem?.realtime;
        if (!existingRealtime) return;

        const updatedFinanceData: IFinanceData = {
          realtime: existingRealtime,
          chart_session_id: chart_data?.[0].chart_session_id,
          historical: {
            data: response.data.stock_data.historical.data,
            source: 'custom',
            period: chart_data?.[0]?.historical?.period || [],
            // keep whatever the API told us previously about listing status
            is_active: existingItem?.historical?.is_active,
          },
        };

        setData((prevData) =>
          prevData.map((item) => (item.realtime.symbol === symbol ? updatedFinanceData : item))
        );
      } catch (error) {
        console.error('Error fetching monthly chart data:', error);
        toast.error('Failed to fetch updated historical data.');
      } finally {
        if (setCurrentTickerSymbol) {
          setCurrentTickerSymbol('');
        }
        setModalPeriodTrigger(false);
        if (setLoading) {
          setLoading(false);
        }
        if (setShowSpecificChartLoader) {
          setShowSpecificChartLoader((prev: any) => prev.filter((id: any) => id !== key));
        }
      }
    },
    [data, setCurrentTickerSymbol, setShowSpecificChartLoader]
  );

  useEffect(() => {
    setData(chart_data);
    setSelectedPeriod(chart_data?.[0]?.historical?.period?.[0] || '1M');
    setIsDelisted(chart_data?.[0]?.historical?.is_active === false);
  }, [chart_data]);

  useEffect(() => {
    if (!Array.isArray(data) || data.length === 0 || !data[0]?.realtime?.symbol) {
      return;
    }

    setActiveTab(() => {
      return data.map((item) => ({
        symbol: item.realtime.symbol ? item.realtime.symbol : '-',
        activeTab: 'historical', // Default to historical for all symbols
      }));
    });

    setSelectedPeriodData(() => {
      return data.map((item) => ({
        symbol: item.realtime.symbol ? item.realtime.symbol : '-',
        activePeriod: '1M', // Default to historical for all symbols
      }));
    });
  }, [data]);

  const handlePeriodChange = (period: string, symbol: string) => {
    setSelectedPeriod(period);
    setModalPeriodTrigger(true);
    setSelectedPeriodData((prev) => {
      const updatedSelectedPeriodData = [...prev];
      const currentPeriodIndex = updatedSelectedPeriodData.findIndex(
        (item) => item.symbol === symbol
      );
      updatedSelectedPeriodData[currentPeriodIndex] = {
        ...updatedSelectedPeriodData[currentPeriodIndex],
        activePeriod: period,
      };
      return updatedSelectedPeriodData;
    });
    const keySymbol = `${messageId}-${symbol}`;
    if (keySymbol) {
      setCurrentLoadingSymbolData(keySymbol);
    }
    handleMonthlyStockChartData(
      period,
      messageId,
      chart_data?.[0]?.realtime?.exchange || '',
      symbol
    );
  };

  // Format the date with time for the update timestamp
  const currentDate = new Date();
  const hours = currentDate.getHours();
  const minutes = currentDate.getMinutes();
  const formattedTime = `${hours.toString().padStart(2, '0')}:${minutes
    .toString()
    .padStart(2, '0')}`;
  const options: Intl.DateTimeFormatOptions = { month: 'short' };
  const month = new Intl.DateTimeFormat('en-US', options).format(currentDate);
  const formattedDate = `${currentDate.getDate()} ${month}, ${formattedTime} GMT+5:30`;

  const handlePredictiveChartData = async (
    symbol: string,
    exchange: string,
    companyName: string
  ) => {
    try {
      console.log('Fetching predictive chart data for symbol:', symbol, predictedChartData);
      if (predictedChartData.some((item) => item.symbol === symbol)) {
        return; // If data for this symbol is already fetched, do nothing
      } else {
        setPredictedChartDataLoading((prev) => [...prev, symbol]);
        const response = await ApiServices.getStockPredictionData(
          symbol,
          exchange,
          messageId,
          companyName
        );
        setPredictedChartData((prev) => [
          ...prev,
          { symbol: symbol, data: response.data.combined_chart || [] },
        ]);
      }
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || 'Failed to fetch predictive chart data');
    } finally {
      setPredictedChartDataLoading((prev) => prev.filter((item) => item !== symbol));
    }
  };

  const handleActiveTab = (
    value: string,
    symbol: string,
    exchange: string,
    companyName: string
  ) => {
    setActiveTab((prev) =>
      prev.map((tab) =>
        tab.symbol === symbol
          ? { ...tab, activeTab: value === 'historical' ? 'historical' : 'prediction' }
          : tab
      )
    );
    if (value === 'prediction') {
      handlePredictiveChartData(symbol, exchange, companyName);
    }
  };

  return (
    <div className="space-y-3 h-full">
      {Array.isArray(data) &&
        data.map((chartData, index) => {
          const isPositive = chartData.realtime.changesPercentage
            ? chartData.realtime.changesPercentage > 0
            : false;
          const realtimeData = chartData.realtime;
          const historicalData = chartData.historical?.data || [];
          const chart_session_id = chartData.chart_session_id;
          const key = `${messageId}-${chartData.realtime.symbol}`;
          const isOpen = isChartInsightRoute
            ? isChartInsightRoute
            : (openSpecificChart ?? []).includes(key);
          const periods = ['1M', '3M', '6M', 'YTD', '1Y', '5Y', 'MAX'];
          const periodsList = Array.isArray(chartData.historical?.period)
            ? chartData.historical?.period?.map((each) =>
                each.endsWith('o') ? each.slice(0, -1).toUpperCase() : each.toUpperCase()
              )
            : periods;

          const isActiveFlag = chartData.historical?.is_active ?? true;
          const isDelistedForThisChart = isActiveFlag === false;

          return (
            <div
              key={index}
              className={cn(
                'overflow-hidden rounded-xl mt-4 bg-[var(--primary-chart-bg)]',
                isChartInsightRoute && 'h-full'
              )}
            >
              <div
                onClick={() => handleOpenSpecificChart && handleOpenSpecificChart(key)}
                className="p-4 cursor-pointer flex justify-between items-center bg-[var(--primary-chart-bg)]"
              >
                <div
                  className={cn(
                    'flex items-center justify-between gap-x-3 text-sm font-semibold leading-normal tracking-normal text-black w-full',
                    !isOpen && 'flex-1 min-w-0'
                  )}
                >
                  {!isOpen && (
                    <div className="flex items-center gap-x-2">
                      <div
                        className={cn(
                          'flex xs:flex-row flex-col xs:text-sm text-xs gap-x-2 gap-y-1 xs:w-40 w-20',
                          isPositive ? 'text-green-500' : 'text-red-500'
                        )}
                      >
                        <p>
                          {chartData.realtime.price ? chartData.realtime.price.toFixed(2) : '-'}
                        </p>

                        <span className="font-normal">
                          {isPositive ? `+${chartData.realtime.change}` : chartData.realtime.change}{' '}
                          (
                          {chartData.realtime.changesPercentage
                            ? chartData.realtime.changesPercentage.toFixed(2)
                            : '-'}{' '}
                          %)
                        </span>
                      </div>

                      <StockSparkLines
                        data={historicalData
                            .filter((day) => day?.close)
                            .map((day) => parseFloat(day.close.replace(',', '')))}
                        fillColor={isPositive ? '#22c55e' : '#ef4444'}
                      />
                    </div>
                  )}
                  <h2
                    className={cn(
                      !isOpen && 'xs:text-sm text-xs truncate',
                      isChartInsightRoute &&
                        !islg &&
                        'text-[#0A0A0A] font-[500] text-[10px] leading-[12.704px]'
                    )}
                  >
                    {chartData.realtime.name}
                  </h2>
                  {isChartInsightRoute && (
                    <div className="flex justify-between items-start">
                      <div
                        className={cn(
                          'text-[#6B7280] font-schibstedGrotesk text-[8.25px] font-normal leading-[10.163px]',
                          islg && 'text-[12px]'
                        )}
                      >
                        Updated {formattedDate}
                      </div>
                    </div>
                  )}
                </div>

                {!isModalView && !isChartInsightRoute && (
                  <div>
                    <BsChevronDown
                      className={cn(
                        'text-black size-5 cursor-pointer transition-transform',
                        isOpen ? 'rotate-180' : ''
                      )}
                    />
                  </div>
                )}
              </div>

              <AnimatePresence>
                {isOpen && (
                  <motion.div
                    initial={{ height: 0 }}
                    animate={{ height: 'auto' }}
                    exit={{ height: 0 }}
                    transition={{ duration: 0.3, ease: 'easeInOut' }}
                    className="px-4 bg-[var(--primary-chart-bg)]"
                  >
                    <StockHeader
                      symbol={realtimeData.symbol || '-'}
                      exchange={realtimeData.exchange || '-'}
                      currency={realtimeData.currency || '-'}
                      name={realtimeData.name || '-'}
                      price={realtimeData.price || 0}
                      changesPercentage={realtimeData.changesPercentage || 0}
                      change={realtimeData.change || 0}
                      isChartInsightRoute={isChartInsightRoute}
                    />

                    <Tabs
                      value={activeTab.find((tab) => tab.symbol === realtimeData.symbol)?.activeTab}
                      onValueChange={(value) =>
                        handleActiveTab(
                          value,
                          realtimeData.symbol || '',
                          realtimeData.exchange || '',
                          realtimeData.name || ''
                        )
                      }
                      className="w-full mb-2"
                    >
                      <TabsList className="bg-[#E7EAD4] rounded-lg px-1.5 py-2">
                        <TabsTrigger
                          className={cn(
                            'data-[state=active]:text-white text-sm font-medium px-2 flex items-center gap-x-1',
                            isChartInsightRoute && !islg && 'text-[12px]'
                          )}
                          value={`historical`}
                        >
                          <HistoricalIcon
                            isActive={
                              activeTab.find((tab) => tab.symbol === realtimeData.symbol)
                                ?.activeTab === 'historical'
                            }
                            width={isChartInsightRoute ? 15 : 20}
                            height={isChartInsightRoute ? 15 : 20}
                          />{' '}
                          Live/historical Data
                        </TabsTrigger>

                        {!isDelistedForThisChart && (
                          <TabsTrigger
                            className={cn(
                              'data-[state=active]:text-white text-sm font-medium px-2 flex items-center gap-x-1',
                              isChartInsightRoute && !islg && 'text-[12px]'
                            )}
                            value={`prediction`}
                          >
                            <PredictiveIcon
                              isActive={
                                activeTab.find((tab) => tab.symbol === realtimeData.symbol)
                                  ?.activeTab === 'prediction'
                              }
                              width={20}
                              height={20}
                            />{' '}
                            Price Forecast
                          </TabsTrigger>
                        )}
                      </TabsList>
                      <TabsContent value="historical">
                        <TimePeriodTabs
                          symbol={realtimeData.symbol || '-'}
                          selectedPeriodData={selectedPeriodData}
                          selectedPeriod={selectedPeriod}
                          onPeriodChange={handlePeriodChange}
                          periodsList={periodsList}
                        />

                        <StockChart
                          data={historicalData}
                          isPositive={isPositive}
                          loading={
                            (loading &&
                              (financeChartModal
                                ? modalPeriodTrigger
                                : currentLoadingSymbolData === key)) ??
                            false
                          }
                          symbol={realtimeData.symbol || '-'}
                          period={selectedPeriod}
                          isModalView={isModalView ?? false}
                          heightOfStockChart={heightOfStockChart}
                        />
                      </TabsContent>

                      {!isDelistedForThisChart && (
                        <TabsContent value="prediction">
                          <StockChart2
                            data={
                              predictedChartData.find((item) => item.symbol === realtimeData.symbol)
                                ?.data || []
                            }
                            isPositive={isPositive}
                            loading={
                              realtimeData.symbol
                                ? predictedChartDataLoading.includes(realtimeData.symbol)
                                : false
                            }
                            symbol={realtimeData.symbol || '-'}
                            heightOfStockChart={heightOfStockChart}
                            // period={selectedPeriod}
                          />
                        </TabsContent>
                      )}
                    </Tabs>

                    <StockDetails
                      open={realtimeData.open || 0}
                      high={realtimeData.dayHigh || 0}
                      low={realtimeData.dayLow || 0}
                      marketCap={realtimeData.marketCap || 0}
                      peRatio={realtimeData.pe || 0}
                      volume={realtimeData.volume || 0}
                      yearHigh={realtimeData.yearHigh || 0}
                      yearLow={realtimeData.yearLow || 0}
                      exchange={realtimeData.exchange || '-'}
                      isChartInsightRoute={isChartInsightRoute}
                    />

                    {!isModalView && handleModalOpen && (
                      <div className="mb-4 flex items-center justify-center">
                        <button
                          onClick={() =>
                            handleModalOpen(
                              key,
                              messageId,
                              realtimeData?.exchange || '',
                              realtimeData?.symbol || '',
                              chart_session_id
                            )
                          }
                          className="text-[#4B9770] text-xs gap-x-1 flex items-center justify-center"
                        >
                          More about {realtimeData.symbol}
                          <ArrowRight size={20} />
                        </button>
                      </div>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          );
        })}
    </div>
  );
};

export default React.memo(FinanceChart);
