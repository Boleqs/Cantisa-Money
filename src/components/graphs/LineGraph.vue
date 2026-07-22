<template>
  <div class="card chart-card">
    <div class="chart-header">
      <div>
        <h2>{{ title }}</h2>
        <p v-if="subtitle" class="subtitle">
          {{ subtitle }}
        </p>
      </div>
      <span v-if="showLastValue && lastValue !== null" class="chart-total">
        {{ lastValue }}
      </span>
    </div>

    <div class="chart-wrapper">
      <canvas ref="canvasRef"></canvas>
    </div>

    <p v-if="!hasData" class="chart-status">
      Aucune donnée à afficher.
    </p>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, computed } from 'vue'
import { Chart } from 'chart.js/auto'

const props = defineProps({
  title: {
    type: String,
    required: true
  },
  subtitle: {
    type: String,
    default: ''
  },
  labels: {
    type: Array,
    required: true
  },
  /**
   * Mode simple (une seule courbe) : values + datasetLabel + color. Ignoré si `series` est fourni.
   */
  values: {
    type: Array,
    default: () => []
  },
  datasetLabel: {
    type: String,
    default: 'Série'
  },
  color: {
    type: String,
    default: '#6366f1'
  },
  /**
   * Mode multi-courbes (prioritaire sur values/datasetLabel/color) : [{ label, values, color }, ...],
   * toutes alignées sur `labels`. La légende Chart.js s'affiche automatiquement dans ce mode.
   */
  series: {
    type: Array,
    default: () => []
  },
  /**
   * hauteur du graphique
   */
  height: {
    type: String,
    default: '180px'
  },
  /**
   * afficher la dernière valeur en haut à droite (mode simple uniquement — ambigu en multi-courbes)
   */
  showLastValue: {
    type: Boolean,
    default: true
  },
  /**
   * callback optionnel pour formater les valeurs de l'axe Y et du dernier total. Composant
   * générique : par défaut, nombre brut sans devise supposée — ex: v => `${v.toLocaleString('fr-FR')} USD`
   * (ne pas utiliser style: 'currency', qui affiche un symbole localisé, ex: "$US" pour USD en
   * fr-FR, différent du code stocké en base).
   */
  formatValue: {
    type: Function,
    default: (v) => v.toLocaleString('fr-FR', { maximumFractionDigits: 2 })
  }
})

const canvasRef = ref(null)
const chartInstance = ref(null)

const isMulti = computed(() => props.series.length > 0)
const hasData = computed(() => {
  if (!props.labels.length) return false
  return isMulti.value ? props.series.some(s => s.values?.length) : props.values.length > 0
})

const lastValue = computed(() => {
  if (isMulti.value || !props.values.length) return null
  const v = props.values[props.values.length - 1]
  return props.formatValue ? props.formatValue(v) : v
})

const buildChart = () => {
  if (!canvasRef.value || !hasData.value) return

  // détruire l’ancien graphique si besoin
  if (chartInstance.value) {
    chartInstance.value.destroy()
  }

  const datasets = isMulti.value
    ? props.series.map(s => ({
        label: s.label,
        data: s.values,
        borderColor: s.color,
        backgroundColor: s.color + '33',
        fill: false,
        tension: 0.3,
        pointRadius: 2,
        pointHoverRadius: 4
      }))
    : [{
        label: props.datasetLabel,
        data: props.values,
        borderColor: props.color,
        backgroundColor: props.color + '33',
        fill: true,
        tension: 0.3,
        pointRadius: 3,
        pointHoverRadius: 4
      }]

  chartInstance.value = new Chart(canvasRef.value.getContext('2d'), {
    type: 'line',
    data: {
      labels: props.labels,
      datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          display: isMulti.value,
          position: 'bottom',
          labels: { color: '#9ca3af', boxWidth: 12, font: { size: 11 } }
        },
        tooltip: {
          mode: 'index',
          intersect: false,
          callbacks: {
            label: (ctx) => {
              const v = ctx.parsed.y
              const label = isMulti.value ? `${ctx.dataset.label} : ` : ''
              return label + (props.formatValue ? props.formatValue(v) : v)
            }
          }
        }
      },
      scales: {
        x: {
          ticks: { color: '#9ca3af', maxRotation: 0 },
          grid: { display: false }
        },
        y: {
          ticks: {
            color: '#9ca3af',
            callback: (value) =>
              props.formatValue ? props.formatValue(value) : value
          },
          grid: {
            color: 'rgba(55,65,81,0.4)'
          }
        }
      }
    }
  })
}

onMounted(buildChart)

onBeforeUnmount(() => {
  if (chartInstance.value) {
    chartInstance.value.destroy()
  }
})

// si les données changent → on reconstruit
watch(
  () => [props.labels, props.values, props.color, props.series],
  () => {
    buildChart()
  },
  { deep: true }
)
</script>

<style scoped>
.card.chart-card {
  border-radius: 14px;
  border: 1px solid #1f2937;
  background: #020617;
  padding: 10px 12px 12px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.35);
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.chart-header h2 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}
.subtitle {
  margin: 2px 0 0;
  font-size: 12px;
  color: #9ca3af;
}
.chart-total {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
}

.chart-wrapper {
  margin-top: 8px;
  height: v-bind(height);
}


.chart-status {
  margin-top: 6px;
  font-size: 12px;
  color: #9ca3af;
}
</style>
