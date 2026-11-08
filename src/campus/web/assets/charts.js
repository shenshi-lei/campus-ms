const TEXT = "#64748b";
const MUTED = "#94a3b8";
const GRID_LINE = "#eef2f7";

const STATUS_COLORS = {
  出勤: "#3b82f6",
  迟到: "#f59e0b",
  缺勤: "#ef4444",
  请假: "#94a3b8",
};

const SCORE_COLORS = ["#ef4444", "#f59e0b", "#3b82f6", "#22c55e", "#0ea5e9"];

const instances = [];

function available() {
  return typeof window !== "undefined" && Boolean(window.echarts);
}

function init(dom, option) {
  if (!available()) {
    dom.innerHTML = '<div class="chart-fallback">图表组件加载失败，请刷新页面</div>';
    return null;
  }
  dom.innerHTML = "";
  const chart = window.echarts.init(dom, null, { renderer: "canvas" });
  chart.setOption(option);
  instances.push(chart);
  return chart;
}

function tooltip() {
  return {
    trigger: "axis",
    backgroundColor: "rgba(15, 23, 42, 0.88)",
    borderWidth: 0,
    padding: [8, 12],
    textStyle: { color: "#f8fafc", fontSize: 12 },
    axisPointer: { type: "shadow", shadowStyle: { color: "rgba(148, 163, 184, 0.12)" } },
  };
}

function axisLabel(extra = {}) {
  return { color: MUTED, fontSize: 11, ...extra };
}

function valueAxis(name = "") {
  return {
    type: "value",
    name,
    nameTextStyle: { color: MUTED, fontSize: 11 },
    splitLine: { lineStyle: { color: GRID_LINE, type: "dashed" } },
    axisLabel: axisLabel(),
    axisLine: { show: false },
    axisTick: { show: false },
  };
}

function categoryAxis(data) {
  return {
    type: "category",
    data,
    axisLine: { lineStyle: { color: "#e2e8f0" } },
    axisTick: { show: false },
    axisLabel: axisLabel(),
  };
}

function gradeGradient(value) {
  const echarts = window.echarts;
  if (value >= 90) return "#ef4444";
  if (value >= 70) return "#f59e0b";
  return new echarts.graphic.LinearGradient(0, 0, 1, 0, [
    { offset: 0, color: "#60a5fa" },
    { offset: 1, color: "#2dd4bf" },
  ]);
}

export const charts = {
  dispose() {
    while (instances.length) {
      const chart = instances.pop();
      try {
        chart.dispose();
      } catch {
        // 已销毁的实例忽略
      }
    }
  },

  attendance(dom, data) {
    const series = (data?.series || []).map((item) => ({
      name: item.name,
      type: "bar",
      stack: "total",
      barMaxWidth: 16,
      itemStyle: { color: STATUS_COLORS[item.name] || "#3b82f6", borderRadius: [3, 3, 0, 0] },
      emphasis: { focus: "series" },
      data: item.data,
    }));
    return init(dom, {
      color: Object.values(STATUS_COLORS),
      tooltip: tooltip(),
      legend: {
        top: 0,
        right: 0,
        itemWidth: 9,
        itemHeight: 9,
        icon: "circle",
        textStyle: { color: TEXT, fontSize: 12 },
      },
      grid: { left: 4, right: 8, top: 36, bottom: 4, containLabel: true },
      xAxis: categoryAxis(data?.labels || []),
      yAxis: valueAxis("人次"),
      series,
    });
  },

  scores(dom, data) {
    const buckets = data?.buckets || [];
    return init(dom, {
      tooltip: tooltip(),
      grid: { left: 4, right: 8, top: 20, bottom: 4, containLabel: true },
      xAxis: categoryAxis(buckets.map((item) => item.label)),
      yAxis: valueAxis("人次"),
      series: [
        {
          type: "bar",
          barMaxWidth: 42,
          data: buckets.map((item, index) => ({
            value: item.count,
            itemStyle: {
              borderRadius: [8, 8, 0, 0],
              color: new window.echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: SCORE_COLORS[index] || "#3b82f6" },
                { offset: 1, color: `${SCORE_COLORS[index] || "#3b82f6"}66` },
              ]),
            },
          })),
          label: { show: true, position: "top", color: TEXT, fontSize: 11 },
        },
      ],
    });
  },

  fees(dom, data) {
    const paid = Number(data?.paid_amount || 0);
    const overdue = Number(data?.overdue_amount || 0);
    const pending = Math.max(0, Number(data?.unpaid_amount || 0) - overdue);
    return init(dom, {
      tooltip: {
        trigger: "item",
        backgroundColor: "rgba(15, 23, 42, 0.88)",
        borderWidth: 0,
        textStyle: { color: "#f8fafc", fontSize: 12 },
        formatter: (params) => `${params.name}<br/>¥${Number(params.value).toLocaleString("zh-CN")}`,
      },
      color: ["#22c55e", "#ef4444", "#f59e0b"],
      legend: {
        bottom: 0,
        left: "center",
        icon: "circle",
        itemWidth: 9,
        itemHeight: 9,
        textStyle: { color: TEXT, fontSize: 12 },
      },
      graphic: [
        {
          type: "text",
          left: "center",
          top: "38%",
          style: {
            text: `${Number(data?.collection_rate || 0)}%`,
            fill: "#0f172a",
            fontSize: 24,
            fontWeight: 700,
            textAlign: "center",
          },
        },
        {
          type: "text",
          left: "center",
          top: "50%",
          style: { text: "金额收缴率", fill: MUTED, fontSize: 11, textAlign: "center" },
        },
      ],
      series: [
        {
          type: "pie",
          radius: ["56%", "76%"],
          center: ["50%", "44%"],
          avoidLabelOverlap: true,
          itemStyle: { borderColor: "#ffffff", borderWidth: 3, borderRadius: 8 },
          label: { show: false },
          data: [
            { name: "已缴", value: paid },
            { name: "逾期", value: overdue },
            { name: "待缴", value: pending },
          ],
        },
      ],
    });
  },

  courseLoad(dom, items) {
    const rows = [...(items || [])].reverse();
    return init(dom, {
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        backgroundColor: "rgba(15, 23, 42, 0.88)",
        borderWidth: 0,
        textStyle: { color: "#f8fafc", fontSize: 12 },
        formatter: (params) => {
          const row = rows[params[0].dataIndex];
          return `${row.name}<br/>${row.enrolled}/${row.capacity} 人 · ${row.rate}%`;
        },
      },
      grid: { left: 4, right: 44, top: 12, bottom: 4, containLabel: true },
      xAxis: {
        type: "value",
        max: 100,
        splitLine: { lineStyle: { color: GRID_LINE, type: "dashed" } },
        axisLabel: { ...axisLabel(), formatter: "{value}%" },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      yAxis: {
        type: "category",
        data: rows.map((item) => item.name),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: axisLabel({ width: 110, overflow: "truncate" }),
      },
      series: [
        {
          type: "bar",
          barMaxWidth: 14,
          data: rows.map((item) => ({
            value: item.rate,
            itemStyle: { borderRadius: [0, 6, 6, 0], color: gradeGradient(item.rate) },
          })),
          label: {
            show: true,
            position: "right",
            color: TEXT,
            fontSize: 11,
            formatter: "{c}%",
          },
        },
      ],
    });
  },

  classComparison(dom, items) {
    return init(dom, {
      tooltip: tooltip(),
      legend: {
        top: 0,
        right: 0,
        icon: "circle",
        itemWidth: 9,
        itemHeight: 9,
        textStyle: { color: TEXT, fontSize: 12 },
      },
      grid: { left: 4, right: 8, top: 36, bottom: 4, containLabel: true },
      xAxis: categoryAxis((items || []).map((item) => item.name)),
      yAxis: { ...valueAxis(), min: 0, max: 100 },
      series: [
        {
          name: "平均分",
          type: "bar",
          barMaxWidth: 22,
          itemStyle: {
            borderRadius: [6, 6, 0, 0],
            color: new window.echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: "#3b82f6" },
              { offset: 1, color: "#93c5fd" },
            ]),
          },
          data: (items || []).map((item) => item.average_score),
        },
        {
          name: "出勤率",
          type: "line",
          smooth: true,
          symbolSize: 7,
          lineStyle: { width: 2.5, color: "#14b8a6" },
          itemStyle: { color: "#14b8a6" },
          data: (items || []).map((item) => item.attendance_rate),
        },
      ],
    });
  },
};

if (typeof window !== "undefined") {
  window.addEventListener("resize", () => {
    for (const chart of instances) chart.resize();
  });
}
