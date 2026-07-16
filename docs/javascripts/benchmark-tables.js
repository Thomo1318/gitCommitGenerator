document.addEventListener('DOMContentLoaded', async () => {
  console.log("Initializing Benchmark Tables with DataTables & ECharts...");
  
  // Create a container for the chart
  const container = document.querySelector('article');
  if (!container) return;
  
  const chartDiv = document.createElement('div');
  chartDiv.id = 'benchmark-chart';
  chartDiv.style.width = '100%';
  chartDiv.style.height = '400px';
  chartDiv.style.marginBottom = '2rem';
  
  // Find the benchmark table (we assume it has a specific class or id, 
  // or just take the first table for the purpose of the demo)
  const table = document.querySelector('table.benchmark-table') || document.querySelector('table');
  if (!table) return;
  
  table.parentNode.insertBefore(chartDiv, table);
  
  // Attempt to load ECharts (assume it's injected via Zensical template or CDN)
  let chart = null;
  if (window.echarts) {
      chart = window.echarts.init(chartDiv);
      chart.setOption({
          title: { text: 'Tokens per Second (TPS)' },
          tooltip: {},
          xAxis: { type: 'category', data: [] },
          yAxis: { type: 'value' },
          series: [{ type: 'bar', data: [] }]
      });
  }

  // Attempt to load DataTables
  let dataTable = null;
  if (window.jQuery && window.jQuery.fn.DataTable) {
      dataTable = window.jQuery(table).DataTable({
          paging: false,
          searching: true,
          info: false,
          order: [[4, 'desc']] // default sort on TPS if it's the 5th column
      });
  }
  
  // Fetch Lite JSON asynchronously to hydrate chart
  try {
      const response = await fetch('/data/benchmark_lite.json');
      if (response.ok) {
          const data = await response.json();
          console.log("Fetched benchmark_lite.json", data);
          
          if (chart && data.length > 0) {
              const xAxisData = data.map(d => `${d.model} (${d.engine})`);
              const yAxisData = data.map(d => d.metrics.tokens_per_second);
              chart.setOption({
                  xAxis: { data: xAxisData },
                  series: [{ data: yAxisData }]
              });
          }
      }
  } catch (error) {
      console.warn("Could not fetch benchmark_lite.json:", error);
  }
  
  // Event Delegation for row selection
  if (dataTable) {
      window.jQuery(table.querySelector('tbody')).on('click', 'tr', function () {
          window.jQuery(this).toggleClass('selected');
          
          if (!chart) return;
          // Refresh chart based on selected rows
          const selectedRows = dataTable.rows('.selected').data();
          if (selectedRows.length > 0) {
              const xData = [];
              const yData = [];
              for (let i = 0; i < selectedRows.length; i++) {
                  xData.push(selectedRows[i][0]); // Assumes col 0 is Model
                  yData.push(parseFloat(selectedRows[i][4])); // Assumes col 4 is TPS
              }
              chart.setOption({
                  xAxis: { data: xData },
                  series: [{ data: yData }]
              });
          } else {
              // Reset to all if none selected
              // (In practice, we might re-fetch from lite_json)
          }
      });
  }
});
