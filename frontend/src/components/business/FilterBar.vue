<template>
  <section class="filter-bar" aria-label="商品筛选条件">
    <div class="filter-bar__main"><slot /></div>
    <div class="filter-bar__actions"><slot name="actions" /></div>
  </section>
</template>

<style scoped lang="scss">
.filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 14px;
  background: var(--surface);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
}
.filter-bar__main,
.filter-bar__actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.filter-bar__main {
  min-width: 0;
  flex: 1;
  flex-wrap: wrap;
}
@media (max-width: 820px) {
  .filter-bar,
  .filter-bar__actions {
    align-items: stretch;
  }
  .filter-bar {
    flex-direction: column;
  }
}
</style>
