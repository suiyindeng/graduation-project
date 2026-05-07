<script setup>
defineProps({
  rows: {
    type: Array,
    default: () => []
  }
})
</script>

<template>
  <div class="table-wrap">
    <table v-if="rows.length">
      <thead>
        <tr>
          <th v-for="key in Object.keys(rows[0])" :key="key">{{ key }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, index) in rows.slice(0, 12)" :key="index">
          <td v-for="key in Object.keys(rows[0])" :key="key">{{ row[key] }}</td>
        </tr>
      </tbody>
    </table>
    <div v-else class="empty-state">暂无预览数据</div>
  </div>
</template>
