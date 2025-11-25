<template>
  <div :class="props.pType">
    <slot>
      Default message content.
      A message should be displaying here
    </slot>
  </div>
</template>

<script setup>
  const props = defineProps({
    pType: {
      validator(value, props) {return ['info', 'warning', 'error'].includes(value)},
      type: String,
      required: true}
    }
  )
</script>

<style scoped>
  .error{
    position: fixed;
    right: 0%;
    background: red;
    border: 2px solid red;
    border-radius: 5px;
    margin-top: 10px;
    margin-right: 10px;
    width: 25em;
    height: auto;
    padding: 0.5em;
  }
  .warning{
    position: fixed;
    right: 0%;
    background: orangered;
    border: 2px solid orangered;
    border-radius: 5px;
    margin-top: 10px;
    margin-right: 10px;
    width: 25em;
    height: auto;
    padding: 0.5em;
  }
  .info{
    position: fixed;
    right: 0%;
    background: gray;
    border: 2px solid gray;
    border-radius: 5px;
    margin-top: 10px;
    margin-right: 10px;
    width: 25em;
    height: auto;
    padding: 0.5em;
  }
</style>