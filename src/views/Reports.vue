<template>
  <div class="page">
    <header class="page-header">
      <div class="title-block">
        <h1>Rapports</h1>
        <p class="subtitle">Analysez vos finances sur les 12 derniers mois.</p>
      </div>
      <button class="btn" :disabled="loading" @click="reload">
        <span v-if="!loading">↻ Rafraîchir</span>
        <span v-else>Chargement…</span>
      </button>
    </header>

    <div v-if="error" class="alert"><strong>Erreur :</strong> {{ error }}</div>

    <!-- Tabs -->
    <div class="tabs">
      <button :class="['tab', { active: tab === 'monthly' }]" @click="tab = 'monthly'">Mensuel</button>
      <button :class="['tab', { active: tab === 'category' }]" @click="tab = 'category'">Par catégorie</button>
    </div>

    <!-- Monthly report -->
    <div v-if="tab === 'monthly'">
      <div v-if="loading" class="empty">Chargement…</div>
      <div v-else-if="!monthly.length" class="empty">Aucune donnée.</div>
      <template v-else>
        <!-- Summary -->
        <div class="kpi-row">
          <div class="kpi-card">
            <div class="kpi-label">Revenus (12 mois)</div>
            <div class="kpi-value pos">{{ fmtAmount(totalIncome) }}</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">Dépenses (12 mois)</div>
            <div class="kpi-value neg">{{ fmtAmount(totalExpenses) }}</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">Net (12 mois)</div>
            <div class="kpi-value" :class="totalNet >= 0 ? 'pos' : 'neg'">{{ fmtAmount(totalNet) }}</div>
          </div>
        </div>

        <!-- Bar chart (CSS) -->
        <div class="chart-section">
          <h3>Revenus vs Dépenses</h3>
          <div class="bar-chart">
            <div v-for="m in monthly" :key="m.month" class="bar-group">
              <div class="bar-label">{{ m.label }}</div>
              <div class="bars">
                <div class="bar bar-income" :style="{ height: barHeight(m.income, maxVal) + 'px' }" :title="'Revenus : ' + fmtAmount(m.income)"></div>
                <div class="bar bar-expense" :style="{ height: barHeight(m.expenses, maxVal) + 'px' }" :title="'Dépenses : ' + fmtAmount(m.expenses)"></div>
              </div>
            </div>
          </div>
          <div class="legend">
            <span class="legend-dot income-dot"></span> Revenus
            <span class="legend-dot expense-dot"></span> Dépenses
          </div>
        </div>

        <!-- Table -->
        <table class="table">
          <thead>
            <tr>
              <th>Mois</th>
              <th class="num">Revenus</th>
              <th class="num">Dépenses</th>
              <th class="num">Net</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="m in [...monthly].reverse()" :key="m.month">
              <td>{{ m.label }}</td>
              <td class="num pos">{{ fmtAmount(m.income) }}</td>
              <td class="num neg">{{ fmtAmount(m.expenses) }}</td>
              <td class="num" :class="m.net >= 0 ? 'pos' : 'neg'">{{ fmtAmount(m.net) }}</td>
            </tr>
          </tbody>
        </table>
      </template>
    </div>

    <!-- Category report -->
    <div v-if="tab === 'category'">
      <div class="filters">
        <label>Du
          <input type="date" v-model="catFilter.start" />
        </label>
        <label>Au
          <input type="date" v-model="catFilter.end" />
        </label>
        <button class="btn btn-primary" @click="loadCategory">Appliquer</button>
      </div>

      <div v-if="loadingCat" class="empty">Chargement…</div>
      <div v-else-if="!catData.by_category?.length" class="empty">Aucune dépense sur cette période.</div>
      <template v-else>
        <div class="cat-total">Total dépenses : <strong>{{ fmtAmount(catData.total) }}</strong></div>

        <!-- Horizontal bars -->
        <div class="cat-bars">
          <div v-for="c in catData.by_category" :key="c.name" class="cat-row">
            <div class="cat-name">{{ c.name }}</div>
            <div class="cat-bar-wrap">
              <div class="cat-bar" :style="{ width: catPct(c.total) + '%' }"></div>
            </div>
            <div class="cat-amount">{{ fmtAmount(c.total) }}</div>
            <div class="cat-pct muted">{{ catPct(c.total).toFixed(1) }}%</div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const monthly = ref([])
const catData = ref({ by_category: [], total: 0 })
const loading = ref(false)
const loadingCat = ref(false)
const error = ref('')
const tab = ref('monthly')

const today = new Date().toISOString().slice(0, 10)
const monthStart = today.slice(0, 8) + '01'
const catFilter = ref({ start: monthStart, end: today })

function fmtAmount(v) {
  return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(v || 0)
}

const totalIncome = computed(() => monthly.value.reduce((s, m) => s + m.income, 0))
const totalExpenses = computed(() => monthly.value.reduce((s, m) => s + m.expenses, 0))
const totalNet = computed(() => totalIncome.value - totalExpenses.value)
const maxVal = computed(() => Math.max(...monthly.value.map(m => Math.max(m.income, m.expenses)), 1))

function barHeight(val, max) {
  return Math.round((val / max) * 120)
}

function catPct(val) {
  if (!catData.value.total) return 0
  return (val / catData.value.total) * 100
}

async function loadMonthly() {
  loading.value = true
  error.value = ''
  try {
    const res = await axios.get('/api/reports/monthly')
    monthly.value = Array.isArray(res.data?.response_data) ? res.data.response_data : []
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    loading.value = false
  }
}

async function loadCategory() {
  loadingCat.value = true
  error.value = ''
  try {
    const res = await axios.get('/api/reports/by-category', {
      params: { start_date: catFilter.value.start, end_date: catFilter.value.end }
    })
    catData.value = res.data?.response_data || { by_category: [], total: 0 }
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    loadingCat.value = false
  }
}

async function reload() {
  await loadMonthly()
  await loadCategory()
}

onMounted(() => reload())
</script>

<style scoped>
.page {
  padding: 28px;
  color: #e5e7eb;
  background: #0b1220;
  min-height: 100vh;
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;
}
.page-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
  flex-wrap: wrap;
}
.title-block h1 { margin: 0; font-size: 28px; }
.subtitle { margin: 6px 0 0; color: #9ca3af; font-size: 14px; }

.btn {
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(15, 23, 42, 0.7);
  color: #e5e7eb;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
}
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-primary { background: linear-gradient(90deg, #2563eb, #4f46e5); border-color: transparent; color: #fff; }

.alert {
  border: 1px solid rgba(239, 68, 68, 0.5);
  background: rgba(239, 68, 68, 0.08);
  padding: 12px 14px;
  border-radius: 12px;
  margin-bottom: 16px;
  color: #fecaca;
}
.empty {
  padding: 18px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(15, 23, 42, 0.55);
  border-radius: 14px;
  color: #cbd5e1;
  margin-top: 16px;
}

.tabs { display: flex; gap: 8px; margin-bottom: 20px; }
.tab {
  padding: 8px 18px;
  border-radius: 8px;
  border: 1px solid rgba(148,163,184,0.2);
  background: transparent;
  color: #9ca3af;
  cursor: pointer;
  font-size: 14px;
}
.tab.active { background: rgba(37,99,235,0.2); border-color: #2563eb; color: #93c5fd; }

.kpi-row { display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 24px; }
.kpi-card {
  background: rgba(15,23,42,0.7);
  border: 1px solid rgba(148,163,184,0.18);
  border-radius: 14px;
  padding: 16px 22px;
  min-width: 160px;
}
.kpi-label { font-size: 12px; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.05em; }
.kpi-value { font-size: 22px; font-weight: 700; margin-top: 6px; }
.pos { color: #34d399; }
.neg { color: #f87171; }

.chart-section { margin-bottom: 28px; }
.chart-section h3 { font-size: 16px; margin: 0 0 14px; color: #cbd5e1; }
.bar-chart { display: flex; gap: 6px; align-items: flex-end; overflow-x: auto; padding-bottom: 4px; }
.bar-group { display: flex; flex-direction: column; align-items: center; gap: 4px; min-width: 52px; }
.bar-label { font-size: 10px; color: #6b7280; text-align: center; white-space: nowrap; }
.bars { display: flex; gap: 3px; align-items: flex-end; height: 130px; }
.bar { width: 18px; border-radius: 4px 4px 0 0; min-height: 2px; transition: height 0.3s ease; }
.bar-income { background: #34d399; }
.bar-expense { background: #f87171; }
.legend { display: flex; gap: 16px; font-size: 13px; color: #9ca3af; margin-top: 8px; align-items: center; }
.legend-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; margin-right: 4px; }
.income-dot { background: #34d399; }
.expense-dot { background: #f87171; }

.table { width: 100%; border-collapse: collapse; font-size: 14px; margin-top: 16px; }
.table th {
  text-align: left; padding: 10px 12px;
  border-bottom: 1px solid rgba(148,163,184,0.15);
  color: #9ca3af; font-weight: 500;
}
.table td { padding: 10px 12px; border-bottom: 1px solid rgba(148,163,184,0.08); }
.num { text-align: right; }

.filters { display: flex; gap: 12px; align-items: flex-end; margin-bottom: 20px; flex-wrap: wrap; }
.filters label { display: flex; flex-direction: column; gap: 4px; font-size: 13px; color: #9ca3af; }
.filters input {
  background: rgba(15,23,42,0.7);
  border: 1px solid rgba(148,163,184,0.25);
  border-radius: 8px;
  padding: 8px 10px;
  color: #e5e7eb;
  font-size: 14px;
}

.cat-total { font-size: 14px; color: #9ca3af; margin-bottom: 16px; }
.cat-bars { display: flex; flex-direction: column; gap: 10px; }
.cat-row { display: grid; grid-template-columns: 180px 1fr 100px 60px; align-items: center; gap: 10px; }
.cat-name { font-size: 14px; color: #e5e7eb; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cat-bar-wrap { background: rgba(148,163,184,0.1); border-radius: 4px; height: 10px; overflow: hidden; }
.cat-bar { height: 100%; background: linear-gradient(90deg, #f87171, #fb923c); border-radius: 4px; transition: width 0.4s ease; }
.cat-amount { text-align: right; font-size: 14px; color: #e5e7eb; }
.cat-pct { text-align: right; font-size: 13px; }
.muted { color: #9ca3af; }
</style>
