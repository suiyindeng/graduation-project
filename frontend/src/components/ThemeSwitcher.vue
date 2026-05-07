<script setup>
import { computed } from 'vue'
import { ChevronDown, Palette } from 'lucide-vue-next'

const props = defineProps({
  theme: {
    type: String,
    default: 'arcaea'
  }
})

const emit = defineEmits(['change'])

const themes = [
  { value: 'arcaea', label: 'Arcaea', hint: '玻璃水晶' },
  { value: 'rosmontis', label: '轻盈一梦', hint: '金色花纹' },
]

const currentTheme = computed(() => themes.find((item) => item.value === props.theme) || themes[0])
</script>

<template>
  <div class="theme-switcher" aria-label="主题切换">
    <button type="button" class="theme-current active" aria-haspopup="menu">
      <Palette :size="16" />
      <span>{{ currentTheme.label }}</span>
      <ChevronDown class="theme-chevron" :size="16" />
    </button>

    <div class="theme-options" role="menu">
      <button
        v-for="item in themes"
        :key="item.value"
        type="button"
        role="menuitem"
        :class="{ active: theme === item.value }"
        @click="emit('change', item.value)"
      >
        <span>{{ item.label }}</span>
        <small>{{ item.hint }}</small>
      </button>
    </div>
  </div>
</template>
