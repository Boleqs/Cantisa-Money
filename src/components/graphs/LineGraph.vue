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

    <p v-if="!labels.length || !values.length" class="chart-status">
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
  values: {
    type: Array,
    required: true
  },
  /**
   * étiquette de la courbe (pour la légende / tooltip)
   */
  datasetLabel: {
    type: String,
    default: 'Série'
  },
  /**
   * couleur principale de la courbe
   */
  color: {
    type: String,
    default: '#6366f1'
  },
  /**
   * hauteur du graphique
   */
  height: {
    type: String,
    default: '180px'
  },
  /**
   * afficher la dernière valeur en haut à droite
   */
  showLastValue: {
    type: Boolean,
    default: true
  },
  /**
   * callback optionnel pour formater les valeurs de l’axe Y et du dernier total
   * ex: v => v.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })
   */
  formatValue: {
    type: Function,
    default: (v) =>
  v.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })
  }
})

const canvasRef = ref(null)
const chartInstance = ref(null)

const lastValue = computed(() => {
  if (!props.values.length) return null
  const v = props.values[props.values.length - 1]
  return props.formatValue ? props.formatValue(v) : v
})

const buildChart = () => {
  if (!canvasRef.value || !props.labels.length || !props.values.length) return

  // détruire l’ancien graphique si besoin
  if (chartInstance.value) {
    chartInstance.value.destroy()
  }

  const borderColor = props.color
  const backgroundColor = props.color + '33' // même couleur, faible opacité

  chartInstance.value = new Chart(canvasRef.value.getContext('2d'), {
    type: 'line',
    data: {
      labels: props.labels,
      datasets: [
        {
          label: props.datasetLabel,
          data: props.values,
          borderColor,
          backgroundColor,
          fill: true,
          tension: 0.3,
          pointRadius: 3,
          pointHoverRadius: 4
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: false
        },
        tooltip: {
          mode: 'index',
          intersect: false,
          callbacks: {
            label: (ctx) => {
              const v = ctx.parsed.y
              if (props.formatValue) {
                return props.formatValue(v)
              }
              return v
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
  () => [props.labels, props.values, props.color],
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