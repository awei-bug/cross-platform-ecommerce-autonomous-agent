<script setup lang="ts">
withDefaults(defineProps<{ compact?: boolean }>(), { compact: false })
</script>

<template>
  <div class="brand" :class="{ 'brand--compact': compact }" aria-label="运营中枢">
    <span class="brand__mark" aria-hidden="true">
      <span></span>
      <span></span>
    </span>
    <span v-if="!compact" class="brand__name">运营中枢</span>
  </div>
</template>

<style scoped lang="scss">
.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  color: #fff;
}

.brand__mark {
  position: relative;
  display: grid;
  width: 32px;
  height: 32px;
  flex: 0 0 32px;
  place-items: center;
  transform: rotate(30deg);

  span {
    position: absolute;
    width: 23px;
    height: 12px;
    border: 5px solid #31d7d0;
    border-radius: 4px;
  }

  span:first-child {
    transform: translateY(-6px);
  }
  span:last-child {
    transform: translateY(6px);
    border-color: #ffffff;
  }
}

.brand__name {
  overflow: hidden;
  font-size: 22px;
  font-weight: 760;
  letter-spacing: -0.02em;
  white-space: nowrap;
}

.brand--compact {
  justify-content: center;
}
</style>
