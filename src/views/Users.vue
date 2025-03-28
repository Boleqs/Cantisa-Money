<template>
  <div class="bandeau">
    <Title class="title" title="Users" />
    <h1 class="menu">Panneau de configuration</h1>
  </div>
</template>

<script>
import Title from './Title.vue';

export default {
  components: {
    Title
  }
}
</script>

<style>
.bandeau {
  left: 0;
  top: 0;
  width: 100%;
  background-color: #1a4396;
  display: flex;
  align-items: center;
  padding: 0 0px;
  color: white;  
}
.title {
  width: 15%;
  padding: 10px;
  background-color: lightblue;
}
.menu {
  width: 85%;
  padding: 10px;
  background-color: grey;
}
</style>