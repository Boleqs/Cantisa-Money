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
    position: absolute;
    right: 0px;
    top: 0px;
    background: red;
    border: 2px solid red;
    margin-top: 10px;
    margin-right: 10px;
    width: 300px;
  }
  .warning{
    position: absolute;
    right: 0px;
    top: 0px;
    background: yellow;
    border: 2px solid yellow;
    margin-top: 10px;
    margin-right: 10px;
    width: 300px;
  }
  .info{
    position: absolute;
    right: 0px;
    top: 0px;
    background: gray;
    border: 2px solid gray;
    margin-top: 10px;
    margin-right: 10px;
    width: 300px;
  }
</style>