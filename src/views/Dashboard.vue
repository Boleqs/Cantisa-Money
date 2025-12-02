<template>
    <h1>The sidebar is {{ collapsed ? 'closed' : 'open' }}</h1>
    <button @click="toggleSidebar">Toggle sidebar</button>
    <LineChartCard
    title="Évolution du total des comptes"
    subtitle="Somme nette au fil du temps"
    :labels="labels"
    :values="values"
    dataset-label="Total des comptes"
    color="#22c55e"/>
</template>

<script>
import { collapsed, toggleSidebar } from '@/components/sidebar/state'
import LineChartCard from "@/components/graphs/LineGraph.vue";

export default {
  components: {LineChartCard},
  setup() {
    return { collapsed, toggleSidebar }
  }
}
</script>

<style>

</style>