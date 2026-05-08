<script setup>
import { computed } from 'vue'
import { ChevronDown, Palette } from 'lucide-vue-next'

const props = defineProps({
  theme: {
    type: String,
    default: 'arcaea'
  },
  user: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['change'])

const themes = [
  { value: 'arcaea', label: 'Arcaea', hint: '玻璃水晶' },
  { value: 'rosmontis', label: '轻盈一梦', hint: '金色花纹' },
  { value: 'skadi', label: '腐蚀之心', hint: '深海侵蚀' },
  { value: 'module_disabled', label: '模块禁用', hint: '千禧蓝白' },
  { value: 'seven_rebirth', label: '七日重生', hint: '符咒阴月' },
  { value: 'forgotten_fenghua', label: '遗忘的风华', hint: '花灯旧梦', restricted: true },
]

const canUseRestrictedThemes = computed(() => props.user?.role === 'super_admin' && props.user?.username === '冴月麟')
const visibleThemes = computed(() => themes.filter((item) => !item.restricted || canUseRestrictedThemes.value))
const currentTheme = computed(() => visibleThemes.value.find((item) => item.value === props.theme) || visibleThemes.value[0] || themes[0])
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
        v-for="item in visibleThemes"
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
