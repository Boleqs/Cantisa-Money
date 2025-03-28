<script>
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import { collapsed } from './state';

export default {
    props: {
        to: { type: String, required: true },
        iconFile: { type: String, required: true }
    },
    setup(props) {
        const route = useRoute();
        const isActive = computed(() => route.path === props.to);
        const iconSrc = computed(() => new URL(`../icons/${props.iconFile}`, import.meta.url).href);

        return { isActive, collapsed, iconSrc };
    }
}
</script>

<template>
    <router-link :to="to" class="link" :class="{ active: isActive}">
        <img class="icon" :src="iconSrc" alt="icon" />
        <transition name="fade">
            <span v-if="!collapsed">
                <slot />
            </span>
        </transition>
    </router-link>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
    transition: opacity 0.1s;
}

.fade-enter,
.fade-leave-to {
    opacity: 0;
}
.link {
    display: flex;
    align-items: center;

    cursor: pointer;
    position: relative;
    font-weight: 400;
    user-select: none;

    margin: 0.1em 0;
    padding: 0.4em;
    border-radius: 0.25em;
    height: 1.5em;

    color: white;
    text-decoration: none;
    transition: 0.4s ease;

}

.link:hover {
    background-color: var(--sidebar-item-hover);
    padding: 1em;
}

.link.active {
    background-color: var(--sidebar-item-active);
    padding: 1em;
}

.link .icon {
    flex-shrink: 0;
    width: 25px;
    margin-right: 10px;
}
</style>