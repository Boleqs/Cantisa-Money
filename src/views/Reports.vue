<template>
  <div class="page">
    <header class="page-header">
      <div class="title-block">
        <h1>Rapports</h1>
        <p class="subtitle">Analysez vos finances en détail.</p>
      </div>
      <button class="btn" :disabled="loading" @click="reload">
        <span v-if="!loading">↻ Rafraîchir</span>
        <span v-else>Chargement…</span>
      </button>
    </header>

    <div v-if="error" class="alert"><strong>Erreur :</strong> {{ error }}</div>

    <!-- Tabs -->
    <div class="tabs">
      <button :class="['tab', { active: tab === 'monthly' }]"  @click="tab = 'monthly'">Mensuel</button>
      <button :class="['tab', { active: tab === 'category' }]" @click="tab = 'category'">Par catégorie</button>
      <button :class="['tab', { active: tab === 'tag' }]"      @click="tab = 'tag'; loadTag()">Par tag</button>
      <button :class="['tab', { active: tab === 'account' }]"  @click="tab = 'account'">Par compte</button>
      <button :class="['tab', { active: tab === 'savings' }]"  @click="tab = 'savings'">Épargne</button>
      <button v-if="hasPermission('Planification')" :class="['tab', { active: tab === 'budgets' }]" @click="tab = 'budgets'; loadBudgets()">Budgets</button>
      <button v-if="hasPermission('Planification')" :class="['tab', { active: tab === 'subscriptions' }]" @click="tab = 'subscriptions'; loadSubscriptions()">Abonnements</button>
      <button v-if="hasPermission('Patrimoine')" :class="['tab', { active: tab === 'wealth' }]" @click="tab = 'wealth'; loadWealth()">Patrimoine</button>
      <button v-if="hasPermission('Patrimoine')" :class="['tab', { active: tab === 'portfolio' }]" @click="tab = 'portfolio'; loadWealth()">Portefeuille</button>
    </div>

    <!-- ── MENSUEL ─────────────────────────────────────────────────────── -->
    <div v-if="tab === 'monthly'">
      <div v-if="loading" class="empty">Chargement…</div>
      <div v-else-if="!monthly.length" class="empty">Aucune donnée.</div>
      <template v-else>

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
          <div class="kpi-card">
            <div class="kpi-label">Taux d'épargne moyen</div>
            <div class="kpi-value" :class="avgSavingsRate >= 0 ? 'pos' : 'neg'">
              {{ avgSavingsRate !== null ? avgSavingsRate.toFixed(1) + ' %' : '—' }}
            </div>
          </div>
        </div>

        <!-- Bar chart: Revenus vs Dépenses -->
        <div class="card">
          <div class="card-title">Revenus vs Dépenses</div>
          <div class="bar-chart">
            <div v-for="m in monthly" :key="m.month" class="bar-group">
              <div class="bars">
                <div class="bar bar-income"  :style="{ height: barHeight(m.income,  maxBarVal) + 'px' }" :title="'Revenus : ' + fmtAmount(m.income)"></div>
                <div class="bar bar-expense" :style="{ height: barHeight(m.expenses, maxBarVal) + 'px' }" :title="'Dépenses : ' + fmtAmount(m.expenses)"></div>
              </div>
              <div class="bar-label">{{ m.label.slice(0, 3) }}</div>
            </div>
          </div>
          <div class="legend">
            <span class="legend-dot income-dot"></span> Revenus
            <span class="legend-dot expense-dot"></span> Dépenses
          </div>
        </div>

        <!-- SVG: Net mensuel -->
        <div class="card">
          <div class="card-title">Net mensuel</div>
          <div class="svg-wrap">
            <svg :viewBox="`0 0 ${SW} ${SH}`" preserveAspectRatio="none" class="chart-svg">
              <!-- Baseline -->
              <line :x1="SP.l" :y1="midY" :x2="SW - SP.r" :y2="midY"
                stroke="rgba(148,163,184,0.3)" stroke-width="1" />
              <!-- Bars -->
              <g v-for="(b, i) in netBars" :key="i">
                <rect :x="b.x" :y="b.y" :width="b.w" :height="b.h" :fill="b.color" rx="2" />
              </g>
              <!-- Y labels -->
              <text :x="SP.l - 4" :y="SP.t + 8"         text-anchor="end" class="svg-label">{{ fmtShort(netMax) }}</text>
              <text :x="SP.l - 4" :y="SH - SP.b + 4"    text-anchor="end" class="svg-label">{{ fmtShort(-netMax) }}</text>
              <text :x="SP.l - 4" :y="midY + 4"          text-anchor="end" class="svg-label">0</text>
              <!-- X labels -->
              <text v-for="(b, i) in netBars" :key="'lbl'+i"
                :x="b.x + b.w / 2" :y="SH - 2"
                text-anchor="middle" class="svg-label">{{ monthly[i].label.slice(0, 3) }}</text>
            </svg>
          </div>
          <div class="legend">
            <span class="legend-dot income-dot"></span> Excédent
            <span class="legend-dot expense-dot"></span> Déficit
          </div>
        </div>

        <!-- Table -->
        <div class="card">
          <div class="card-title">Détail mensuel</div>
          <table class="table">
            <thead>
              <tr>
                <th>Mois</th>
                <th class="num">Revenus</th>
                <th class="num">Dépenses</th>
                <th class="num">Net</th>
                <th class="num">Épargne</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="m in [...monthly].reverse()" :key="m.month">
                <td>{{ m.label }}</td>
                <td class="num pos">{{ fmtAmount(m.income) }}</td>
                <td class="num neg">{{ fmtAmount(m.expenses) }}</td>
                <td class="num" :class="m.net >= 0 ? 'pos' : 'neg'">{{ fmtAmount(m.net) }}</td>
                <td class="num" :class="m.savings_rate !== null ? (m.savings_rate >= 0 ? 'pos' : 'neg') : ''">
                  {{ m.savings_rate !== null ? m.savings_rate.toFixed(1) + ' %' : '—' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

      </template>
    </div>

    <!-- ── PAR CATÉGORIE ────────────────────────────────────────────────── -->
    <div v-if="tab === 'category'">
      <div class="filters">
        <label>Du <input type="date" v-model="catFilter.start" /></label>
        <label>Au <input type="date" v-model="catFilter.end" /></label>
        <button class="btn btn-primary" @click="loadCategory">Appliquer</button>
      </div>

      <div v-if="loadingCat" class="empty">Chargement…</div>
      <div v-else-if="!catData.by_category?.length" class="empty">Aucune dépense sur cette période.</div>
      <template v-else>
        <div class="cat-layout">

          <!-- Donut SVG -->
          <div class="card donut-card">
            <div class="card-title">Répartition</div>
            <div class="donut-wrap">
              <svg viewBox="0 0 200 200" class="donut-svg">
                <g transform="rotate(-90, 100, 100)">
                  <circle v-for="seg in donutSegments" :key="seg.name"
                    cx="100" cy="100" r="70"
                    fill="none"
                    :stroke="seg.color"
                    stroke-width="28"
                    :stroke-dasharray="seg.dashArray"
                    :stroke-dashoffset="seg.dashOffset"
                  />
                </g>
                <text x="100" y="95"  text-anchor="middle" class="donut-label-sm">Total</text>
                <text x="100" y="115" text-anchor="middle" class="donut-label-lg">{{ fmtAmountShort(catData.total) }}</text>
              </svg>
            </div>
            <div class="donut-legend">
              <div v-for="seg in donutSegments" :key="seg.name" class="donut-legend-row">
                <span class="donut-dot" :style="{ background: seg.color }"></span>
                <span class="donut-legend-name">{{ seg.name }}</span>
                <span class="donut-legend-pct muted">{{ seg.pct }}%</span>
              </div>
            </div>
          </div>

          <!-- Barres horizontales -->
          <div class="card bars-card">
            <div class="card-title">Détail — Total : {{ fmtAmount(catData.total) }}</div>
            <div class="cat-bars">
              <div v-for="(c, i) in catData.by_category" :key="c.name" class="cat-row">
                <div class="cat-name">{{ c.name }}</div>
                <div class="cat-bar-wrap">
                  <div class="cat-bar" :style="{ width: catPct(c.total) + '%', background: DONUT_COLORS[i % DONUT_COLORS.length] }"></div>
                </div>
                <div class="cat-amount">{{ fmtAmount(c.total) }}</div>
                <div class="cat-pct muted">{{ catPct(c.total).toFixed(1) }}%</div>
              </div>
            </div>
          </div>

        </div>
      </template>
    </div>

    <!-- ── PAR TAG ─────────────────────────────────────────────────────── -->
    <div v-if="tab === 'tag'">
      <div class="filters">
        <label>Du <input type="date" v-model="tagFilter.start" /></label>
        <label>Au <input type="date" v-model="tagFilter.end" /></label>
        <button class="btn btn-primary" @click="loadTag">Appliquer</button>
      </div>

      <div v-if="loadingTag" class="empty">Chargement…</div>
      <div v-else-if="!tagData.by_tag?.length" class="empty">Aucune dépense taguée sur cette période.</div>
      <template v-else>
        <p class="hint">Un split peut porter plusieurs tags : les totaux peuvent se chevaucher (une dépense comptée sous plusieurs tags).</p>
        <div class="cat-layout">

          <div class="card donut-card">
            <div class="card-title">Répartition</div>
            <div class="donut-wrap">
              <svg viewBox="0 0 200 200" class="donut-svg">
                <g transform="rotate(-90, 100, 100)">
                  <circle v-for="seg in tagDonutSegments" :key="seg.name"
                    cx="100" cy="100" r="70"
                    fill="none"
                    :stroke="seg.color"
                    stroke-width="28"
                    :stroke-dasharray="seg.dashArray"
                    :stroke-dashoffset="seg.dashOffset"
                  />
                </g>
                <text x="100" y="95"  text-anchor="middle" class="donut-label-sm">Total tagué</text>
                <text x="100" y="115" text-anchor="middle" class="donut-label-lg">{{ fmtAmountShort(tagData.total) }}</text>
              </svg>
            </div>
            <div class="donut-legend">
              <div v-for="seg in tagDonutSegments" :key="seg.name" class="donut-legend-row">
                <span class="donut-dot" :style="{ background: seg.color }"></span>
                <span class="donut-legend-name">{{ seg.name }}</span>
                <span class="donut-legend-pct muted">{{ seg.pct }}%</span>
              </div>
            </div>
          </div>

          <div class="card bars-card">
            <div class="card-title">Détail — Total tagué : {{ fmtAmount(tagData.total) }}</div>
            <div class="cat-bars">
              <div v-for="(t, i) in tagData.by_tag" :key="t.name" class="cat-row">
                <div class="cat-name">{{ t.name }}</div>
                <div class="cat-bar-wrap">
                  <div class="cat-bar" :style="{ width: tagPct(t.total) + '%', background: DONUT_COLORS[i % DONUT_COLORS.length] }"></div>
                </div>
                <div class="cat-amount">{{ fmtAmount(t.total) }}</div>
                <div class="cat-pct muted">{{ tagPct(t.total).toFixed(1) }}%</div>
              </div>
            </div>
          </div>

        </div>
      </template>
    </div>

    <!-- ── PAR COMPTE ──────────────────────────────────────────────────── -->
    <div v-if="tab === 'account'">
      <div class="filters">
        <label>Du <input type="date" v-model="accFilter.start" /></label>
        <label>Au <input type="date" v-model="accFilter.end" /></label>
        <button class="btn btn-primary" @click="loadAccount">Appliquer</button>
      </div>

      <div v-if="loadingAcc" class="empty">Chargement…</div>
      <div v-else-if="!accData.by_account?.length" class="empty">Aucune activité sur cette période.</div>
      <template v-else>

        <!-- Barres horizontales : net par compte -->
        <div class="card">
          <div class="card-title">Net par compte</div>
          <div class="acc-bars">
            <div v-for="a in sortedByAbsNet" :key="a.id" class="acc-bar-row">
              <div class="acc-bar-name">
                <span>{{ a.name }}</span>
                <span class="acc-type-chip">{{ a.account_type }}</span>
              </div>
              <div class="acc-bar-track">
                <div class="acc-bar-fill"
                  :class="a.net >= 0 ? 'pos-fill' : 'neg-fill'"
                  :style="{ width: (Math.abs(a.net) / maxAbsNet * 100) + '%' }">
                </div>
              </div>
              <div class="acc-bar-val" :class="a.net >= 0 ? 'pos' : 'neg'">
                {{ a.net >= 0 ? '+' : '' }}{{ fmtAmount(a.net) }}
              </div>
            </div>
          </div>
        </div>

        <!-- Table -->
        <div class="card">
          <div class="card-title">Détail par compte</div>
          <table class="table">
            <thead>
              <tr>
                <th>Compte</th>
                <th>Type</th>
                <th class="num">Crédits</th>
                <th class="num">Débits</th>
                <th class="num">Net</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="a in accData.by_account" :key="a.id">
                <td>{{ a.name }}</td>
                <td><span class="type-chip">{{ a.account_type }}</span></td>
                <td class="num pos">+{{ fmtAmount(a.credits) }}</td>
                <td class="num neg">-{{ fmtAmount(a.debits) }}</td>
                <td class="num" :class="a.net >= 0 ? 'pos' : 'neg'">
                  {{ a.net >= 0 ? '+' : '' }}{{ fmtAmount(a.net) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

      </template>
    </div>

    <!-- ── ÉPARGNE ─────────────────────────────────────────────────────── -->
    <div v-if="tab === 'savings'">
      <div v-if="loading" class="empty">Chargement…</div>
      <div v-else-if="!validSavings.length" class="empty">Pas assez de données.</div>
      <template v-else>

        <div class="kpi-row">
          <div class="kpi-card">
            <div class="kpi-label">Taux moyen</div>
            <div class="kpi-value" :class="avgSavingsRate >= 0 ? 'pos' : 'neg'">
              {{ avgSavingsRate !== null ? avgSavingsRate.toFixed(1) + ' %' : '—' }}
            </div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">Meilleur mois</div>
            <div class="kpi-value pos">{{ bestMonth ? bestMonth.label + ' (' + bestMonth.savings_rate.toFixed(1) + '%)' : '—' }}</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">Pire mois</div>
            <div class="kpi-value neg">{{ worstMonth ? worstMonth.label + ' (' + worstMonth.savings_rate.toFixed(1) + '%)' : '—' }}</div>
          </div>
        </div>

        <!-- SVG: Taux d'épargne -->
        <div class="card">
          <div class="card-title">Évolution du taux d'épargne</div>
          <div class="svg-wrap">
            <svg :viewBox="`0 0 ${SW} ${SH}`" preserveAspectRatio="none" class="chart-svg">
              <defs>
                <linearGradient id="savGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="#34d399" stop-opacity="0.3"/>
                  <stop offset="100%" stop-color="#34d399" stop-opacity="0.02"/>
                </linearGradient>
              </defs>
              <!-- 0% baseline -->
              <line v-if="zeroSavY !== null"
                :x1="SP.l" :y1="zeroSavY" :x2="SW - SP.r" :y2="zeroSavY"
                stroke="rgba(148,163,184,0.4)" stroke-width="1" stroke-dasharray="4,3"/>
              <!-- 20% target -->
              <line v-if="targetSavY !== null"
                :x1="SP.l" :y1="targetSavY" :x2="SW - SP.r" :y2="targetSavY"
                stroke="rgba(251,191,36,0.4)" stroke-width="1" stroke-dasharray="4,3"/>
              <text v-if="targetSavY !== null"
                :x="SW - SP.r + 2" :y="targetSavY + 4"
                class="svg-label" fill="#fbbf24">20%</text>
              <!-- Area fill -->
              <polygon v-if="savingsAreaPoints" :points="savingsAreaPoints" fill="url(#savGrad)" />
              <!-- Line -->
              <polyline v-if="savingsLinePoints" :points="savingsLinePoints"
                fill="none" stroke="#34d399" stroke-width="1.8" stroke-linejoin="round"/>
              <!-- Points -->
              <circle v-for="(pt, i) in savingsPointCoords" :key="i"
                :cx="pt.x" :cy="pt.y" r="3"
                :fill="pt.rate >= 0 ? '#34d399' : '#f87171'"
                stroke="#0b1220" stroke-width="1.5">
                <title>{{ pt.label }} : {{ pt.rate.toFixed(1) }}%</title>
              </circle>
              <!-- Y labels -->
              <text :x="SP.l - 4" :y="SP.t + 8"      text-anchor="end" class="svg-label">{{ Math.round(savRateMax) }}%</text>
              <text :x="SP.l - 4" :y="SH - SP.b + 4"  text-anchor="end" class="svg-label">{{ Math.round(savRateMin) }}%</text>
              <!-- X labels -->
              <text v-for="(pt, i) in savingsPointCoords" :key="'xl'+i"
                :x="pt.x" :y="SH - 2" text-anchor="middle" class="svg-label">
                {{ pt.label.slice(0, 3) }}
              </text>
            </svg>
          </div>
          <div class="legend">
            <span style="color:#fbbf24">- - -</span> Objectif 20%
            <span style="color:rgba(148,163,184,0.6)">- - -</span> 0%
          </div>
        </div>

        <!-- Table -->
        <div class="card">
          <div class="card-title">Détail mensuel</div>
          <table class="table">
            <thead>
              <tr>
                <th>Mois</th>
                <th class="num">Revenus</th>
                <th class="num">Dépenses</th>
                <th class="num">Épargne nette</th>
                <th class="num">Taux</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="m in [...monthly].reverse()" :key="m.month">
                <td>{{ m.label }}</td>
                <td class="num">{{ fmtAmount(m.income) }}</td>
                <td class="num">{{ fmtAmount(m.expenses) }}</td>
                <td class="num" :class="m.net >= 0 ? 'pos' : 'neg'">{{ fmtAmount(m.net) }}</td>
                <td class="num" :class="m.savings_rate !== null ? (m.savings_rate >= 0 ? 'pos' : 'neg') : ''">
                  <template v-if="m.savings_rate !== null">
                    <span class="rate-bar-wrap">
                      <span class="rate-bar" :style="{ width: Math.min(Math.abs(m.savings_rate), 100) + '%', background: m.savings_rate >= 0 ? '#34d399' : '#f87171' }"></span>
                    </span>
                    {{ m.savings_rate.toFixed(1) }}%
                  </template>
                  <template v-else>—</template>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

      </template>
    </div>

    <!-- ── BUDGETS ─────────────────────────────────────────────────────── -->
    <div v-if="tab === 'budgets'">
      <div v-if="loadingBudgets" class="empty">Chargement…</div>
      <div v-else-if="!budgetsData.budgets?.length" class="empty">Aucun budget créé.</div>
      <template v-else>

        <div class="kpi-row">
          <div class="kpi-card">
            <div class="kpi-label">Total alloué</div>
            <div class="kpi-value">{{ fmtAmount(budgetsData.total_allocated) }}</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">Total dépensé</div>
            <div class="kpi-value">{{ fmtAmount(budgetsData.total_spent) }}</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">Taux global</div>
            <div class="kpi-value" :class="budgetsData.overall_pct > 100 ? 'neg' : 'pos'">
              {{ budgetsData.overall_pct !== null ? budgetsData.overall_pct.toFixed(1) + ' %' : '—' }}
            </div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">Budgets actifs</div>
            <div class="kpi-value">{{ budgetsData.budgets.filter(b => b.status === 'active').length }}</div>
          </div>
        </div>

        <div class="card">
          <div class="card-title">Tous les budgets</div>
          <table class="table">
            <thead>
              <tr>
                <th>Nom</th>
                <th>Période</th>
                <th>Statut</th>
                <th class="num">Alloué</th>
                <th class="num">Dépensé</th>
                <th>Progression</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="b in budgetsData.budgets" :key="b.id">
                <td>{{ b.name }}</td>
                <td class="muted">{{ fmtDate(b.start_date) }} → {{ fmtDate(b.end_date) }}</td>
                <td><span :class="['status-chip', b.status]">{{ STATUS_LABELS[b.status] }}</span></td>
                <td class="num">{{ fmtAmount(b.amount_allocated) }}</td>
                <td class="num">{{ fmtAmount(b.amount_spent) }}</td>
                <td>
                  <div class="acc-bar-track budget-track">
                    <div class="acc-bar-fill" :class="(b.pct ?? 0) > 100 ? 'neg-fill' : 'pos-fill'"
                      :style="{ width: Math.min(Math.abs(b.pct ?? 0), 100) + '%' }"></div>
                  </div>
                  <span class="muted" style="font-size:11px">{{ b.pct !== null ? b.pct.toFixed(1) + ' %' : '—' }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

      </template>
    </div>

    <!-- ── ABONNEMENTS ─────────────────────────────────────────────────── -->
    <div v-if="tab === 'subscriptions'">
      <div v-if="loadingSubs" class="empty">Chargement…</div>
      <div v-else-if="!subsData.subscriptions?.length" class="empty">Aucun abonnement.</div>
      <template v-else>

        <div class="kpi-row">
          <div class="kpi-card">
            <div class="kpi-label">Coût mensuel</div>
            <div class="kpi-value neg">{{ fmtAmount(subsData.total_monthly) }}</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">Coût annuel</div>
            <div class="kpi-value neg">{{ fmtAmount(subsData.total_annual) }}</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">Abonnements actifs</div>
            <div class="kpi-value">{{ subsData.subscriptions.length }}</div>
          </div>
        </div>

        <div class="cat-layout">
          <div class="card donut-card">
            <div class="card-title">Répartition mensuelle par catégorie</div>
            <div class="donut-wrap">
              <svg viewBox="0 0 200 200" class="donut-svg">
                <g transform="rotate(-90, 100, 100)">
                  <circle v-for="seg in subsDonutSegments" :key="seg.name"
                    cx="100" cy="100" r="70"
                    fill="none" :stroke="seg.color" stroke-width="28"
                    :stroke-dasharray="seg.dashArray" :stroke-dashoffset="seg.dashOffset"
                  />
                </g>
                <text x="100" y="95"  text-anchor="middle" class="donut-label-sm">Par mois</text>
                <text x="100" y="115" text-anchor="middle" class="donut-label-lg">{{ fmtAmountShort(subsData.total_monthly) }}</text>
              </svg>
            </div>
            <div class="donut-legend">
              <div v-for="seg in subsDonutSegments" :key="seg.name" class="donut-legend-row">
                <span class="donut-dot" :style="{ background: seg.color }"></span>
                <span class="donut-legend-name">{{ seg.name }}</span>
                <span class="donut-legend-pct muted">{{ seg.pct }}%</span>
              </div>
            </div>
          </div>

          <div class="card bars-card">
            <div class="card-title">Détail des abonnements</div>
            <table class="table">
              <thead>
                <tr>
                  <th>Nom</th>
                  <th>Catégorie</th>
                  <th class="num">Montant</th>
                  <th>Planification</th>
                  <th class="num">Éq. mensuel</th>
                  <th>Prochaine échéance</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="s in subsData.subscriptions" :key="s.id">
                  <td>{{ s.name }}</td>
                  <td class="muted">{{ s.category }}</td>
                  <td class="num">{{ fmtAmount(s.amount) }}</td>
                  <td class="muted">{{ scheduleLabel(s) }}</td>
                  <td class="num">{{ fmtAmount(s.monthly_equivalent) }}</td>
                  <td class="muted">{{ fmtDate(s.next_due_date) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

      </template>
    </div>

    <!-- ── PATRIMOINE ──────────────────────────────────────────────────── -->
    <div v-if="tab === 'wealth'">
      <div class="filters">
        <label>Du <input type="date" v-model="wealthFilter.start" /></label>
        <label>Au <input type="date" v-model="wealthFilter.end" /></label>
        <button class="btn btn-primary" @click="loadWealth(true)">Appliquer</button>
        <button class="btn" @click="wealthFilter.start = ''; wealthFilter.end = ''; loadWealth(true)">Tout l'historique</button>
      </div>

      <div v-if="loadingWealth" class="empty">Chargement…</div>
      <div v-else-if="!wealthOverview" class="empty">Pas encore de données de patrimoine.</div>
      <template v-else>

        <p class="hint">
          <template v-if="wealthHistory.length">
            Période affichée : {{ fmtDate(wealthHistory[0].date) }} → {{ fmtDate(wealthHistory[wealthHistory.length - 1].date) }}
            ({{ wealthHistory.length }} jour{{ wealthHistory.length > 1 ? 's' : '' }}). Les 3 premières cartes reflètent la fin de cette période ; "Aujourd'hui" affiche l'état actuel réel.
          </template>
        </p>

        <div class="kpi-row">
          <div class="kpi-card">
            <div class="kpi-label">Patrimoine ({{ wealthHistory.length ? 'fin période' : '—' }})</div>
            <div class="kpi-value">{{ wealthLatest ? fmtAmount(wealthLatest.total) : '—' }}</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">Bancaire</div>
            <div class="kpi-value">{{ wealthLatest ? fmtAmount(wealthLatest.bank_net_worth) : '—' }}</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">Portefeuille</div>
            <div class="kpi-value">{{ wealthLatest ? fmtAmount(wealthLatest.portfolio_value) : '—' }}</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">Évolution sur la période</div>
            <div class="kpi-value" :class="wealthGrowth === null ? '' : (wealthGrowth >= 0 ? 'pos' : 'neg')">
              {{ wealthGrowth === null ? '—' : (wealthGrowth >= 0 ? '+' : '') + fmtAmount(wealthGrowth) }}
            </div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">Patrimoine (aujourd'hui)</div>
            <div class="kpi-value">{{ fmtAmount(wealthOverview.kpis.net_worth_total) }}</div>
          </div>
        </div>

        <div class="card">
          <div class="card-title">Évolution du patrimoine total</div>
          <div v-if="wealthHistory.length < 2" class="empty">
            Pas assez de points sur cette période pour tracer une évolution ({{ wealthHistory.length }} jour{{ wealthHistory.length > 1 ? 's' : '' }} disponible{{ wealthHistory.length > 1 ? 's' : '' }}). Essayez d'élargir la plage de dates.
          </div>
          <div v-else class="svg-wrap">
            <svg :viewBox="`0 0 ${SW} ${SH}`" preserveAspectRatio="none" class="chart-svg">
              <defs>
                <linearGradient id="wealthGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="#60a5fa" stop-opacity="0.3"/>
                  <stop offset="100%" stop-color="#60a5fa" stop-opacity="0.02"/>
                </linearGradient>
              </defs>
              <polygon v-if="wealthAreaPoints" :points="wealthAreaPoints" fill="url(#wealthGrad)" />
              <polyline v-if="wealthLinePoints" :points="wealthLinePoints"
                fill="none" stroke="#60a5fa" stroke-width="1.8" stroke-linejoin="round"/>
              <circle v-for="(pt, i) in wealthPointCoords" :key="i" :cx="pt.x" :cy="pt.y" r="2.2" fill="#60a5fa">
                <title>{{ fmtDate(wealthHistory[i].date) }} : {{ fmtAmount(wealthHistory[i].total) }}</title>
              </circle>
              <text :x="SP.l - 4" :y="SP.t + 8"      text-anchor="end" class="svg-label">{{ fmtShort(wealthMax) }}</text>
              <text :x="SP.l - 4" :y="SH - SP.b + 4"  text-anchor="end" class="svg-label">{{ fmtShort(wealthMin) }}</text>
              <text :x="SP.l" :y="SH - 2" text-anchor="start" class="svg-label">{{ fmtDate(wealthHistory[0].date) }}</text>
              <text :x="SW - SP.r" :y="SH - 2" text-anchor="end" class="svg-label">{{ fmtDate(wealthHistory[wealthHistory.length-1].date) }}</text>
            </svg>
          </div>
        </div>

      </template>
    </div>

    <!-- ── PORTEFEUILLE ────────────────────────────────────────────────── -->
    <div v-if="tab === 'portfolio'">
      <div v-if="loadingWealth" class="empty">Chargement…</div>
      <div v-else-if="!wealthOverview" class="empty">Aucun actif suivi.</div>
      <template v-else>

        <div class="kpi-row">
          <div class="kpi-card">
            <div class="kpi-label">Valeur du portefeuille</div>
            <div class="kpi-value">{{ fmtAmount(wealthOverview.kpis.portfolio_value) }}</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">Plus-value latente</div>
            <div class="kpi-value" :class="wealthOverview.kpis.unrealized_gain >= 0 ? 'pos' : 'neg'">
              {{ fmtAmount(wealthOverview.kpis.unrealized_gain) }}
            </div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">Performance</div>
            <div class="kpi-value" :class="(wealthOverview.kpis.unrealized_gain_pct ?? 0) >= 0 ? 'pos' : 'neg'">
              {{ wealthOverview.kpis.unrealized_gain_pct !== null ? wealthOverview.kpis.unrealized_gain_pct.toFixed(1) + ' %' : '—' }}
            </div>
          </div>
        </div>

        <div class="cat-layout">
          <div class="card donut-card">
            <div class="card-title">Répartition par secteur</div>
            <div v-if="!wealthOverview.allocation_by_sector?.length" class="empty">Pas de secteur renseigné.</div>
            <template v-else>
              <div class="donut-wrap">
                <svg viewBox="0 0 200 200" class="donut-svg">
                  <g transform="rotate(-90, 100, 100)">
                    <circle v-for="seg in sectorDonutSegments" :key="seg.name"
                      cx="100" cy="100" r="70"
                      fill="none" :stroke="seg.color" stroke-width="28"
                      :stroke-dasharray="seg.dashArray" :stroke-dashoffset="seg.dashOffset"
                    />
                  </g>
                  <text x="100" y="105" text-anchor="middle" class="donut-label-lg">{{ fmtAmountShort(wealthOverview.kpis.portfolio_value) }}</text>
                </svg>
              </div>
              <div class="donut-legend">
                <div v-for="seg in sectorDonutSegments" :key="seg.name" class="donut-legend-row">
                  <span class="donut-dot" :style="{ background: seg.color }"></span>
                  <span class="donut-legend-name">{{ seg.name }}</span>
                  <span class="donut-legend-pct muted">{{ seg.pct }}%</span>
                </div>
              </div>
            </template>
          </div>

          <div class="card bars-card">
            <div class="card-title">Meilleures / pires performances</div>
            <div v-if="!wealthOverview.top_movers?.length && !wealthOverview.worst_movers?.length" class="empty">Pas assez de données de plus-value.</div>
            <template v-else>
              <div class="movers-block" v-if="wealthOverview.top_movers?.length">
                <div class="movers-title pos">▲ Meilleures performances</div>
                <div v-for="a in wealthOverview.top_movers" :key="a.symbol" class="mover-row">
                  <span>{{ a.symbol }} — {{ a.name }}</span>
                  <span class="pos">+{{ a.gain_pct.toFixed(1) }}%</span>
                </div>
              </div>
              <div class="movers-block" v-if="wealthOverview.worst_movers?.length">
                <div class="movers-title neg">▼ Pires performances</div>
                <div v-for="a in wealthOverview.worst_movers" :key="a.symbol" class="mover-row">
                  <span>{{ a.symbol }} — {{ a.name }}</span>
                  <span class="neg">{{ a.gain_pct.toFixed(1) }}%</span>
                </div>
              </div>
            </template>
          </div>
        </div>

      </template>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import { hasPermission } from '@/utils/permissions.js'

// ── State ──────────────────────────────────────────────────────────────────────
const monthly   = ref([])
const catData   = ref({ by_category: [], total: 0 })
const accData   = ref({ by_account: [] })
const tagData   = ref({ by_tag: [], total: 0 })
const budgetsData = ref({ budgets: [], total_allocated: 0, total_spent: 0, overall_pct: null })
const subsData  = ref({ subscriptions: [], total_monthly: 0, total_annual: 0, by_category: [] })
const wealthHistory  = ref([])
const wealthOverview = ref(null)

const loading    = ref(false)
const loadingCat = ref(false)
const loadingAcc = ref(false)
const loadingTag = ref(false)
const loadingBudgets = ref(false)
const loadingSubs    = ref(false)
const loadingWealth  = ref(false)
const error      = ref('')
const tab        = ref('monthly')

const today      = new Date().toISOString().slice(0, 10)
const monthStart = today.slice(0, 8) + '01'
const catFilter  = ref({ start: monthStart, end: today })
const accFilter  = ref({ start: monthStart, end: today })
const tagFilter  = ref({ start: monthStart, end: today })
const wealthFilter = ref({ start: '', end: '' }) // vide = tout l'historique

const STATUS_LABELS = { active: 'En cours', upcoming: 'À venir', past: 'Terminé' }

// ── Colors ─────────────────────────────────────────────────────────────────────
const DONUT_COLORS = ['#3b82f6','#f59e0b','#10b981','#ef4444','#8b5cf6','#06b6d4','#f97316','#ec4899','#84cc16','#14b8a6']

// ── SVG constants ──────────────────────────────────────────────────────────────
const SW = 600
const SH = 160
const SP = { t: 16, b: 22, l: 44, r: 30 }
const innerW = SW - SP.l - SP.r
const innerH = SH - SP.t - SP.b

// ── Formatters ─────────────────────────────────────────────────────────────────
function fmtAmount(v) {
  return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(v || 0)
}
function fmtAmountShort(v) {
  const n = Number(v || 0)
  if (Math.abs(n) >= 1000) return (n / 1000).toFixed(1) + 'k €'
  return Math.round(n) + ' €'
}
function fmtShort(v) {
  const n = Number(v || 0)
  if (Math.abs(n) >= 1000) return (n / 1000).toFixed(1) + 'k'
  return Math.round(n).toString()
}

// ── Monthly computed ───────────────────────────────────────────────────────────
const totalIncome   = computed(() => monthly.value.reduce((s, m) => s + m.income, 0))
const totalExpenses = computed(() => monthly.value.reduce((s, m) => s + m.expenses, 0))
const totalNet      = computed(() => totalIncome.value - totalExpenses.value)
const maxBarVal     = computed(() => Math.max(...monthly.value.map(m => Math.max(m.income, m.expenses)), 1))

const validSavings  = computed(() => monthly.value.filter(m => m.savings_rate !== null))
const avgSavingsRate = computed(() => {
  if (!validSavings.value.length) return null
  return validSavings.value.reduce((s, m) => s + m.savings_rate, 0) / validSavings.value.length
})
const bestMonth  = computed(() => validSavings.value.reduce((best, m) => !best || m.savings_rate > best.savings_rate ? m : best, null))
const worstMonth = computed(() => validSavings.value.reduce((worst, m) => !worst || m.savings_rate < worst.savings_rate ? m : worst, null))

function barHeight(val, max) {
  return Math.max(Math.round((val / max) * 110), 2)
}

// ── Net bar chart ─────────────────────────────────────────────────────────────
const netMax = computed(() => Math.max(...monthly.value.map(m => Math.abs(m.net)), 1))
const midY   = computed(() => SP.t + innerH / 2)

const netBars = computed(() => {
  const n = monthly.value.length
  if (!n) return []
  const slotW = innerW / n
  const bw = slotW * 0.55
  return monthly.value.map((m, i) => {
    const x = SP.l + i * slotW + (slotW - bw) / 2
    const h = Math.max((Math.abs(m.net) / netMax.value) * (innerH / 2), 1)
    return {
      x, w: bw,
      y: m.net >= 0 ? midY.value - h : midY.value,
      h,
      color: m.net >= 0 ? '#34d399' : '#f87171',
    }
  })
})

// ── Donut chart ───────────────────────────────────────────────────────────────
const CIRC = 2 * Math.PI * 70

const donutSegments = computed(() => {
  const items = (catData.value.by_category || []).slice(0, 10)
  if (!items.length || !catData.value.total) return []
  let cumulative = 0
  return items.map((c, i) => {
    const pct = c.total / catData.value.total
    const len = pct * CIRC
    const seg = {
      color: DONUT_COLORS[i % DONUT_COLORS.length],
      dashArray: `${len} ${CIRC}`,
      dashOffset: -cumulative,
      pct: (pct * 100).toFixed(1),
      name: c.name,
      total: c.total,
    }
    cumulative += len
    return seg
  })
})

function catPct(val) {
  if (!catData.value.total) return 0
  return (val / catData.value.total) * 100
}

/** Segments de donut génériques à partir d'une liste [{name, total|monthly_total}] et d'un total. */
function makeDonutSegments(items, total, valueKey = 'total') {
  const list = (items || []).slice(0, 10)
  if (!list.length || !total) return []
  let cumulative = 0
  return list.map((item, i) => {
    const pct = item[valueKey] / total
    const len = pct * CIRC
    const seg = {
      color: DONUT_COLORS[i % DONUT_COLORS.length],
      dashArray: `${len} ${CIRC}`,
      dashOffset: -cumulative,
      pct: (pct * 100).toFixed(1),
      name: item.name,
      total: item[valueKey],
    }
    cumulative += len
    return seg
  })
}

function fmtDate(v) {
  if (!v) return '—'
  return new Date(v).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' })
}

const MONTH_NAMES = [
  'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
]
const WEEKDAY_NAMES = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']

function scheduleLabel(s) {
  if (s.schedule_type === 'monthly') return `Le ${s.day_of_month} de chaque mois`
  if (s.schedule_type === 'yearly') return `Le ${s.day_of_month} ${MONTH_NAMES[s.month_of_year - 1]}`
  if (s.schedule_type === 'weekly') return (s.weekdays || []).map(d => WEEKDAY_NAMES[d - 1]).join(', ') || '—'
  return '—'
}

// ── Par tag ────────────────────────────────────────────────────────────────────
const tagDonutSegments = computed(() => makeDonutSegments(tagData.value.by_tag, tagData.value.total))
function tagPct(val) {
  if (!tagData.value.total) return 0
  return (val / tagData.value.total) * 100
}

// ── Abonnements ────────────────────────────────────────────────────────────────
const subsDonutSegments = computed(() => makeDonutSegments(subsData.value.by_category, subsData.value.total_monthly, 'monthly_total'))

// ── Patrimoine ─────────────────────────────────────────────────────────────────
const wealthLatest = computed(() => wealthHistory.value[wealthHistory.value.length - 1] || null)
const wealthGrowth = computed(() => {
  if (wealthHistory.value.length < 2) return null
  return wealthHistory.value[wealthHistory.value.length - 1].total - wealthHistory.value[0].total
})
const wealthRawMax = computed(() => Math.max(...wealthHistory.value.map(h => h.total), 0))
const wealthRawMin = computed(() => Math.min(...wealthHistory.value.map(h => h.total), 0))
const wealthPad = computed(() => Math.max((wealthRawMax.value - wealthRawMin.value) * 0.1, 1))
const wealthMax = computed(() => wealthRawMax.value + wealthPad.value)
const wealthMin = computed(() => wealthRawMin.value - wealthPad.value)
const wealthPointCoords = computed(() => {
  const n = wealthHistory.value.length
  if (!n) return []
  return wealthHistory.value.map((h, i) => ({
    x: SP.l + (n <= 1 ? innerW / 2 : (i / (n - 1)) * innerW),
    y: scaleY(h.total, wealthMin.value, wealthMax.value),
  }))
})
const wealthLinePoints = computed(() => wealthPointCoords.value.map(p => `${p.x},${p.y}`).join(' '))
const wealthAreaPoints = computed(() => {
  const pts = wealthPointCoords.value
  if (!pts.length) return ''
  const baseY = scaleY(wealthMin.value, wealthMin.value, wealthMax.value)
  const line = pts.map(p => `${p.x},${p.y}`).join(' ')
  return `${pts[0].x},${baseY} ${line} ${pts[pts.length - 1].x},${baseY}`
})

// ── Portefeuille ───────────────────────────────────────────────────────────────
const sectorDonutSegments = computed(() => {
  const sectors = wealthOverview.value?.allocation_by_sector || []
  const total = sectors.reduce((s, x) => s + x.value, 0)
  return makeDonutSegments(sectors.map(s => ({ name: s.sector, total: s.value })), total)
})

// ── Account chart ─────────────────────────────────────────────────────────────
const sortedByAbsNet = computed(() =>
  [...(accData.value.by_account || [])].sort((a, b) => Math.abs(b.net) - Math.abs(a.net))
)
const maxAbsNet = computed(() =>
  Math.max(...(accData.value.by_account || []).map(a => Math.abs(a.net)), 1)
)

// ── Savings line chart ────────────────────────────────────────────────────────
const savingsPointCoords = computed(() => {
  const data = monthly.value.filter(m => m.savings_rate !== null)
  if (!data.length) return []
  const n = monthly.value.length
  return data.map(m => {
    const i = monthly.value.indexOf(m)
    return {
      x: SP.l + (n <= 1 ? innerW / 2 : (i / (n - 1)) * innerW),
      y: scaleY(m.savings_rate, savRateMin.value, savRateMax.value),
      rate: m.savings_rate,
      label: m.label,
    }
  })
})

const savRateMin = computed(() => {
  if (!validSavings.value.length) return -20
  return Math.min(...validSavings.value.map(m => m.savings_rate), 0) - 10
})
const savRateMax = computed(() => {
  if (!validSavings.value.length) return 100
  return Math.max(...validSavings.value.map(m => m.savings_rate), 20) + 10
})

function scaleY(val, min, max) {
  const range = max - min || 1
  return SP.t + (1 - (val - min) / range) * innerH
}

const savingsLinePoints = computed(() =>
  savingsPointCoords.value.map(p => `${p.x},${p.y}`).join(' ')
)
const savingsAreaPoints = computed(() => {
  const pts = savingsPointCoords.value
  if (!pts.length) return ''
  const baseY = scaleY(0, savRateMin.value, savRateMax.value)
  const line = pts.map(p => `${p.x},${p.y}`).join(' ')
  return `${pts[0].x},${baseY} ${line} ${pts[pts.length-1].x},${baseY}`
})
const zeroSavY = computed(() => {
  const y = scaleY(0, savRateMin.value, savRateMax.value)
  return (y > SP.t && y < SH - SP.b) ? y : null
})
const targetSavY = computed(() => {
  const y = scaleY(20, savRateMin.value, savRateMax.value)
  return (y > SP.t && y < SH - SP.b) ? y : null
})

// ── Fetch ─────────────────────────────────────────────────────────────────────
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

async function loadAccount() {
  loadingAcc.value = true
  error.value = ''
  try {
    const res = await axios.get('/api/reports/by-account', {
      params: { start_date: accFilter.value.start, end_date: accFilter.value.end }
    })
    accData.value = res.data?.response_data || { by_account: [] }
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    loadingAcc.value = false
  }
}

async function loadTag() {
  loadingTag.value = true
  error.value = ''
  try {
    const res = await axios.get('/api/reports/by-tag', {
      params: { start_date: tagFilter.value.start, end_date: tagFilter.value.end }
    })
    tagData.value = res.data?.response_data || { by_tag: [], total: 0 }
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    loadingTag.value = false
  }
}

let budgetsLoaded = false
async function loadBudgets() {
  if (budgetsLoaded) return
  loadingBudgets.value = true
  error.value = ''
  try {
    const res = await axios.get('/api/reports/budgets')
    budgetsData.value = res.data?.response_data || { budgets: [], total_allocated: 0, total_spent: 0, overall_pct: null }
    budgetsLoaded = true
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    loadingBudgets.value = false
  }
}

let subsLoaded = false
async function loadSubscriptions() {
  if (subsLoaded) return
  loadingSubs.value = true
  error.value = ''
  try {
    const res = await axios.get('/api/reports/subscriptions')
    subsData.value = res.data?.response_data || { subscriptions: [], total_monthly: 0, total_annual: 0, by_category: [] }
    subsLoaded = true
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    loadingSubs.value = false
  }
}

let wealthLoaded = false
async function loadWealth(force = false) {
  if (wealthLoaded && !force) return
  loadingWealth.value = true
  error.value = ''
  try {
    const [histRes, overviewRes] = await Promise.all([
      axios.get('/api/wealth/history', {
        params: { start_date: wealthFilter.value.start || undefined, end_date: wealthFilter.value.end || undefined },
      }),
      axios.get('/api/wealth/overview'),
    ])
    wealthHistory.value = Array.isArray(histRes.data?.response_data) ? histRes.data.response_data : []
    wealthOverview.value = overviewRes.data?.response_data || null
    wealthLoaded = true
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    loadingWealth.value = false
  }
}

async function reload() {
  budgetsLoaded = false
  subsLoaded = false
  wealthLoaded = false
  await loadMonthly()
  await Promise.all([loadCategory(), loadAccount()])
  if (tab.value === 'tag') await loadTag()
  if (tab.value === 'budgets') await loadBudgets()
  if (tab.value === 'subscriptions') await loadSubscriptions()
  if (tab.value === 'wealth' || tab.value === 'portfolio') await loadWealth()
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
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.page-header {
  display: flex; align-items: flex-end; justify-content: space-between;
  gap: 16px; flex-wrap: wrap;
}
.title-block h1 { margin: 0; font-size: 28px; }
.subtitle { margin: 6px 0 0; color: #9ca3af; font-size: 14px; }

.btn {
  border: 1px solid rgba(148,163,184,0.25);
  background: rgba(15,23,42,0.7);
  color: #e5e7eb;
  padding: 8px 14px; border-radius: 10px; cursor: pointer; font-size: 13px;
}
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-primary { background: linear-gradient(90deg,#2563eb,#4f46e5); border-color: transparent; color:#fff; }

.alert {
  border: 1px solid rgba(239,68,68,0.5);
  background: rgba(239,68,68,0.08);
  padding: 12px 14px; border-radius: 12px; color: #fecaca;
}
.empty {
  padding: 18px;
  border: 1px solid rgba(148,163,184,0.18);
  background: rgba(15,23,42,0.55);
  border-radius: 14px; color: #cbd5e1;
}

/* Tabs */
.tabs { display: flex; gap: 8px; }
.tab {
  padding: 8px 18px; border-radius: 8px;
  border: 1px solid rgba(148,163,184,0.2);
  background: transparent; color: #9ca3af; cursor: pointer; font-size: 14px;
}
.tab.active { background: rgba(37,99,235,0.2); border-color: #2563eb; color: #93c5fd; }

/* Card */
.card {
  background: rgba(15,23,42,0.7);
  border: 1px solid rgba(148,163,184,0.15);
  border-radius: 14px;
  padding: 18px 20px;
}
.card-title { font-size: 13px; font-weight: 600; color: #cbd5e1; margin-bottom: 14px; }

/* KPIs */
.kpi-row { display: flex; gap: 14px; flex-wrap: wrap; }
.kpi-card {
  background: rgba(15,23,42,0.7);
  border: 1px solid rgba(148,163,184,0.18);
  border-radius: 14px; padding: 16px 22px; min-width: 160px; flex: 1;
}
.kpi-label { font-size: 12px; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.05em; }
.kpi-value { font-size: 22px; font-weight: 700; margin-top: 6px; font-variant-numeric: tabular-nums; }
.pos { color: #34d399; }
.neg { color: #f87171; }

/* Bar chart CSS */
.bar-chart { display: flex; gap: 4px; align-items: flex-end; overflow-x: auto; padding-bottom: 4px; }
.bar-group { display: flex; flex-direction: column; align-items: center; gap: 4px; min-width: 46px; }
.bar-label { font-size: 10px; color: #6b7280; text-align: center; }
.bars { display: flex; gap: 3px; align-items: flex-end; height: 120px; }
.bar { width: 16px; border-radius: 3px 3px 0 0; min-height: 2px; transition: height 0.3s ease; }
.bar-income  { background: #34d399; }
.bar-expense { background: #f87171; }
.legend { display: flex; gap: 16px; font-size: 12px; color: #9ca3af; margin-top: 10px; align-items: center; }
.legend-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; margin-right: 4px; }
.income-dot  { background: #34d399; }
.expense-dot { background: #f87171; }

/* SVG charts */
.svg-wrap { width: 100%; }
.chart-svg { width: 100%; height: 160px; overflow: visible; }
.svg-label { font-size: 9px; fill: #6b7280; }

/* Table */
.table { width: 100%; border-collapse: collapse; font-size: 13px; }
.table th {
  text-align: left; padding: 10px 12px;
  border-bottom: 1px solid rgba(148,163,184,0.15);
  color: #9ca3af; font-weight: 500;
}
.table td { padding: 10px 12px; border-bottom: 1px solid rgba(148,163,184,0.07); }
.num { text-align: right; font-variant-numeric: tabular-nums; }

/* Filters */
.filters { display: flex; gap: 12px; align-items: flex-end; flex-wrap: wrap; }
.filters label { display: flex; flex-direction: column; gap: 4px; font-size: 13px; color: #9ca3af; }
.filters input {
  background: rgba(15,23,42,0.7);
  border: 1px solid rgba(148,163,184,0.25);
  border-radius: 8px; padding: 7px 10px; color: #e5e7eb; font-size: 13px;
}

/* Category layout */
.cat-layout { display: grid; grid-template-columns: 300px 1fr; gap: 16px; }
@media (max-width: 800px) { .cat-layout { grid-template-columns: 1fr; } }

/* Donut */
.donut-card { display: flex; flex-direction: column; }
.donut-wrap { display: flex; justify-content: center; }
.donut-svg { width: 180px; height: 180px; }
.donut-label-sm { font-size: 11px; fill: #9ca3af; }
.donut-label-lg { font-size: 18px; font-weight: 700; fill: #e5e7eb; }
.donut-legend { margin-top: 10px; display: flex; flex-direction: column; gap: 5px; }
.donut-legend-row { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.donut-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.donut-legend-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.donut-legend-pct { font-variant-numeric: tabular-nums; }

/* Horizontal cat bars */
.cat-bars { display: flex; flex-direction: column; gap: 10px; }
.cat-row { display: grid; grid-template-columns: 160px 1fr 100px 52px; align-items: center; gap: 10px; }
.cat-name { font-size: 13px; color: #e5e7eb; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cat-bar-wrap { background: rgba(148,163,184,0.1); border-radius: 4px; height: 10px; overflow: hidden; }
.cat-bar { height: 100%; border-radius: 4px; transition: width 0.4s ease; }
.cat-amount { text-align: right; font-size: 13px; color: #e5e7eb; font-variant-numeric: tabular-nums; }
.cat-pct { text-align: right; font-size: 12px; }
.muted { color: #9ca3af; }

/* Account bars */
.acc-bars { display: flex; flex-direction: column; gap: 10px; }
.acc-bar-row { display: grid; grid-template-columns: 220px 1fr 120px; align-items: center; gap: 12px; }
.acc-bar-name { display: flex; align-items: center; gap: 8px; font-size: 13px; overflow: hidden; }
.acc-bar-name span:first-child { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.acc-type-chip {
  font-size: 10px; padding: 1px 6px; border-radius: 999px;
  border: 1px solid rgba(148,163,184,0.2); color: #9ca3af; white-space: nowrap; flex-shrink: 0;
}
.acc-bar-track { background: rgba(148,163,184,0.1); border-radius: 4px; height: 10px; overflow: hidden; }
.acc-bar-fill { height: 100%; border-radius: 4px; transition: width 0.4s ease; }
.pos-fill { background: linear-gradient(90deg, #34d399, #10b981); }
.neg-fill { background: linear-gradient(90deg, #f87171, #ef4444); }
.acc-bar-val { text-align: right; font-size: 13px; font-weight: 600; font-variant-numeric: tabular-nums; }

.type-chip {
  font-size: 11px; padding: 2px 8px; border-radius: 999px;
  border: 1px solid rgba(148,163,184,0.2); color: #9ca3af;
}

/* Savings rate bar in table */
.rate-bar-wrap {
  display: inline-block; width: 60px; height: 6px;
  background: rgba(148,163,184,0.1); border-radius: 3px; overflow: hidden;
  vertical-align: middle; margin-right: 6px;
}
.rate-bar { display: block; height: 100%; border-radius: 3px; transition: width 0.3s ease; }

/* Hint */
.hint { font-size: 12px; color: #9ca3af; margin: -4px 0 10px; }

/* Status chip (budgets) */
.status-chip {
  font-size: 11px; padding: 2px 8px; border-radius: 999px;
  border: 1px solid rgba(148,163,184,0.2); color: #9ca3af;
}
.status-chip.active   { border-color: rgba(52,211,153,0.4); color: #34d399; }
.status-chip.upcoming { border-color: rgba(96,165,250,0.4); color: #60a5fa; }
.status-chip.past     { border-color: rgba(148,163,184,0.3); color: #9ca3af; }

.budget-track { width: 120px; display: inline-block; margin-bottom: 2px; }

/* Movers (portefeuille) */
.movers-block { margin-bottom: 14px; }
.movers-block:last-child { margin-bottom: 0; }
.movers-title { font-size: 12px; font-weight: 600; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.04em; }
.mover-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 6px 0; font-size: 13px; border-bottom: 1px solid rgba(148,163,184,0.07);
}
.mover-row:last-child { border-bottom: none; }
</style>
