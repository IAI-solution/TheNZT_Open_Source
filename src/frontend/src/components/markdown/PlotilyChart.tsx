'use client';

import { useScreen } from '@/hooks/use-screen';
import useWindowDimension from '@/hooks/useWindowDimension';
import { PlotlyChartProps } from '@/types/ploytly-types';
import { CHART_COLOR_MAP, COLOR_PALETTE, getResponsiveConfig } from '@/utils/plotly';
import dynamic from 'next/dynamic';
import React from 'react';
const Plot = dynamic(
  () =>
    import('react-plotly.js/factory').then((mod) => {
      const Plotly = require('plotly.js-basic-dist');
      return mod.default(Plotly);
    }),
  { ssr: false }
);


const PlotlyChart: React.FC<PlotlyChartProps> = ({
  chartData,
  width = '100%',
  height = 550,
  chartType = null,
  showTitle = true,
  customColors = null,
  className = '',
}) => {
  const { screen: screenSize, containerWidth } = useScreen();
  const { windowDimension } = useWindowDimension();
  const { height: windowHeight } = windowDimension;
  const { chart_type, chart_title, x_label, y_label, data } = chartData;
  const activeChartType = chartType || chart_type;
  const colors = customColors || COLOR_PALETTE;
  const config = getResponsiveConfig(screenSize, windowHeight, height, showTitle);


  console.log('chart_type', chartData)



  // Validate props
  if (!chartData) {
    return (
      <div
        className={`w-full bg-gray-100 rounded-lg flex items-center justify-center ${className}`}
        style={{ height: `${config.dynamicHeight}px` }}
      >
        <p className="text-gray-500 text-sm sm:text-lg">No chart data available</p>
      </div>
    );
  }



  if (!data || data.length === 0) {
    return (
      <div
        className={`w-full bg-gray-100 rounded-lg flex items-center justify-center ${className}`}
        style={{ height: `${200}px` }}
      >
        <p className="text-gray-500 text-sm sm:text-lg">No chart data available</p>
      </div>
    );
  }

  // Truncate text for mobile displays
  const truncateText = (text: string, maxLength: number) => {
    if (!text) return '';
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
  };

  // Generate responsive layout
  let layout: any = {
    title:
      showTitle && chart_title
        ? {
          text: screenSize === 'mobile' ? truncateText(chart_title, 30) : chart_title,
          font: {
            size: config.titleFontSize,
            family: 'Inter, sans-serif',
            color: '#1F2937',
          },
          x: 0.5,
          xanchor: 'center',
        }
        : undefined,

    margin: config.margins,
    showlegend: true,
    responsive: true,
    autosize: true,

    paper_bgcolor: '#f1f1e2',
    plot_bgcolor: '#f1f1e2',

    font: {
      family: 'Inter, sans-serif',
      color: '#374151',
      size: config.tickFontSize,
    },
    dragmode: 'pan',

    // // Responsive modebar
    // modebar: {
    //   orientation: screenSize === 'mobile' ? 'h' : 'v',
    // }
  };

  // Set axis configuration for non-pie charts
  if (activeChartType !== 'pie') {
    const tickvals: number[] = [];
    const ticktext: string[] = [];

    const desiredTicks = 8;
    const totalDataPoints = data[0]?.x_axis_data?.length || 1;

    // Calculate the best interval to achieve the desired number of ticks.
    const tickSpacing = Math.max(1, Math.floor(totalDataPoints / desiredTicks));

    console.log(data[0].x_axis_data)

    if (data[0]?.x_axis_data) {
      data[0].x_axis_data.forEach((label: string, index: number) => {
        // Show a tick if it's on the interval OR if it's the very last one.
        const stringLabel=`${label}`
        if (index % tickSpacing === 0 || index === totalDataPoints - 1) {
          tickvals.push(index);
          const formattedLabel = stringLabel.replace(/\b\d{4}\b/, (year) => `${year.slice(-2)}`);
          ticktext.push(formattedLabel);
        }
      });
    }

    // Define the x-axis layout using our calculated ticks
    layout.xaxis = {
      title: {
        text: screenSize === 'mobile' ? truncateText(x_label || '', 15) : x_label,
        font: {
          color: '#374151',
          size: config.axisLabelFontSize,
          weight: 'bold',
        },
      },
      type: 'category',
      automargin: true,
      gridcolor: '#E5E7EB',
      linecolor: '#D1D5DB',
      tickangle: -45,
      tickfont: { size: config.tickFontSize },
      tickmode: 'array',
      tickvals: tickvals,
      ticktext: ticktext,
      range: [-0.5, totalDataPoints - 0.5],
    };

    layout.yaxis = {
      title: {
        text: screenSize === 'mobile' ? truncateText(y_label || '', 15) : y_label,
        font: {
          color: '#374151',
          size: config.axisLabelFontSize,
          weight: 'bold',
        },
      },
      automargin: true,
      gridcolor: '#E5E7EB',
      linecolor: '#D1D5DB',
      tickfont: { size: config.tickFontSize },
      // Reduce number of ticks on mobile
      nticks: screenSize === 'mobile' ? 5 : undefined,
      // rangemode: 'tozero',
      // zeroline: false,
    };

    layout.legend = config.legendConfig;
  }

  // Generate traces based on chart type with responsive adjustments
  let traces: any[] = [];

  switch (activeChartType) {
    case "lines":
      traces = data.map((series: any, index: number) => {
        const color =
          CHART_COLOR_MAP[series.legend_label] ||
          colors[index % colors.length];

        return {
          x: series.x_axis_data,
          y: series.y_axis_data,
          type: "scatter",
          mode: "lines+markers",
          name:
            screenSize === "mobile"
              ? truncateText(series.legend_label, 12)
              : series.legend_label,
          line: {
            width: screenSize === "mobile" ? 2 : 3,
            color,
          },
          marker: {
            size: screenSize === "mobile" ? 4 : 6,
            color,
            line: {
              color: "#FFFFFF",
              width: screenSize === "mobile" ? 1 : 2,
            },
          },
        };
      });
      break;


    case 'bar':
      traces = data.map((series: any, index: number) => ({
        x: series.x_axis_data,
        y: series.y_axis_data,
        type: 'bar',
        name: screenSize === 'mobile' ? truncateText(series.legend_label, 12) : series.legend_label,
        marker: {
          color: colors[index % colors.length],
          opacity: 0.8,
          line: {
            color: colors[index % colors.length],
            width: screenSize === 'mobile' ? 1 : 2,
          },
        },
      }));

      layout.bargap = screenSize === 'mobile' ? 0.2 : 0.1;
      layout.bargroupgap = screenSize === 'mobile' ? 0.15 : 0.2;
      break;

    case 'group_bar':
      traces = data.map((series: any, index: number) => {
        const color =
          CHART_COLOR_MAP[series.legend_label] ||
          colors[index % colors.length];

        return {
          x: series.x_axis_data,
          y: series.y_axis_data,
          type: 'bar',
          name:
            screenSize === 'mobile'
              ? truncateText(series.legend_label, 12)
              : series.legend_label,
          marker: {
            color: color,
            opacity: 0.8,
            line: {
              color: color,
              width: screenSize === 'mobile' ? 1 : 2,
            },
          },
        };
      });

      layout.barmode = 'group';
      // layout.bargap = screenSize === 'mobile' ? 0.1 : 0.2;
      layout.bargroupgap = 0.0125;
      break;


    case 'pie':
      const pieData = data[0];
      traces = [
        {
          values: pieData.y_axis_data,
          labels:
            screenSize === 'mobile'
              ? pieData.x_axis_data.map((label: string) => truncateText(label, 10))
              : pieData.x_axis_data,
          type: 'pie',
          name:
            screenSize === 'mobile' ? truncateText(pieData.legend_label, 12) : pieData.legend_label,
          hole: screenSize === 'mobile' ? 0.3 : 0.4,
          marker: {
            colors: pieData.y_axis_data.map(
              (_: any, index: number) => colors[index % colors.length]
            ),
            line: {
              color: '#FFFFFF',
              width: screenSize === 'mobile' ? 1 : 2,
            },
          },
          textinfo: screenSize === 'mobile' ? 'percent' : 'label+percent',
          textposition: screenSize === 'mobile' ? 'inside' : 'outside',
          textfont: {
            size: screenSize === 'mobile' ? 10 : 12,
            color: '#374151',
          },
          // Improve text positioning on mobile
          insidetextorientation: 'radial',
        },
      ];

      // Special legend config for pie charts
      layout.legend = {
        ...config.legendConfig,
        y: screenSize === 'mobile' ? -0.1 : -0.2,
      };
      break;

    default:
      console.warn(`Chart type "${activeChartType}" is not supported`);
      return (
        <div
          className={`w-full bg-gray-100 rounded-lg flex items-center justify-center ${className}`}
          style={{ height: `${config.dynamicHeight}px` }}
        >
          <p className="text-gray-500 text-sm sm:text-lg">
            Unsupported chart type: {activeChartType}
          </p>
        </div>
      );
  }

  const plotConfig = {
    responsive: true,
    displayModeBar: screenSize !== 'mobile', // Hide modebar on mobile to save space
    modeBarButtonsToRemove: [
      'lasso2d',
      'zoom2d',
      'select2d',
      'autoScale2d',
      'hoverClosestCartesian',
      'hoverCompareCartesian',
      'toggleSpikelines',
    ] as import('plotly.js').ModeBarDefaultButtons[],
    displaylogo: false,
    toImageButtonOptions: {
      format: 'png' as const,
      filename: chart_title ? chart_title.replace(/\s+/g, '_').toLowerCase() : 'chart',
      height: config.dynamicHeight,
      width: Math.max(containerWidth * 0.9, 600),
      scale: 1.5,
    },
    dragmode: 'pan',
  };

  return (
    <div className={`w-full bg-white rounded-lg shadow-sm border border-gray-200 ${className}`}>
      <div className="w-full p-2 sm:p-4 bg-[var(--primary-chart-bg)]">
        <Plot
          data={traces}
          layout={layout}
          config={plotConfig}
          style={{
            width: '100%',
            height: `${config.dynamicHeight}px`,
            minHeight: '200px',
          }}
          useResizeHandler={true}
          className="w-full"
          onRelayout={(eventData) => {
            // Handle layout changes for better mobile experience
            if (screenSize === 'mobile' && eventData) {
              // Prevent zooming out too much on mobile
              const { 'xaxis.range[0]': xMin, 'xaxis.range[1]': xMax } = eventData;
              if (xMin !== undefined && xMax !== undefined) {
                // You can add custom logic here if needed
              }
            }
          }}
        />
      </div>
    </div>
  );
};


export { PlotlyChart };
