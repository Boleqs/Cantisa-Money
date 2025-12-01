<script setup>
import { ref } from 'vue'
import LineChartCard from '@/components/graphs/LineGraph.vue'

const labels = ref(['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin'])
const values = ref([4200, 4600, 4800, 5100, 4950, 5300])

const formatCurrency = (v) =>
  v.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })
</script>

<template>
  <LineChartCard
    title="Évolution du total des comptes"
    subtitle="Somme nette au fil du temps"
    :labels="labels"
    :values="values"
    dataset-label="Total des comptes"
    color="#22c55e"
    :format-value="formatCurrency"
  />
</template>

<style scoped>
</style>