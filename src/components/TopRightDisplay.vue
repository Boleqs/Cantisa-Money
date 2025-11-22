<template>
  <div class="div_msg">
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
  .div_msg{
    position: absolute;
    right: 0px;
    top: 0px;
    background: red;
    border: 2px solid red;
    margin-top: 10px;
    margin-right: 10px;
    width: 300px;
  }
</style>