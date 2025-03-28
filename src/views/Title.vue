<template>
    <div class="bandeau">
        <h1>{{ title }}</h1>
    </div>
</template>
  
<script>
    export default {
    props: {
        title: {
        type: String,
        required: true
        }
    }
}
</script>
