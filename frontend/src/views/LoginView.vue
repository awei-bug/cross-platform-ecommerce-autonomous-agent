<script setup lang="ts">
import { Lock, User } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import BrandMark from '../components/shared/BrandMark.vue'
import { ApiError } from '../api/http'
import { useSessionStore } from '../stores/session'

const route = useRoute()
const router = useRouter()
const session = useSessionStore()
const isSubmitting = ref(false)
const form = reactive({ account: 'demo', password: 'demo1234' })

async function submit() {
  isSubmitting.value = true
  try {
    await session.login(form.account, form.password)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/dashboard'
    await router.replace(redirect)
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '无法连接服务，请确认后端已启动')
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <main class="login-page">
    <section class="login-story">
      <BrandMark />
      <div class="login-story__content">
        <p class="login-story__kicker">MULTI-STORE OPERATIONS</p>
        <h1>先处理最可能造成损失的事。</h1>
        <p class="login-story__lead">
          把跨平台经营数据、风险事件、批量动作和 AI 助手放进同一个运营指挥中心。
        </p>
        <div class="login-story__proof">
          <div><strong>6</strong><span>核心运营模块</span></div>
          <div><strong>1</strong><span>统一店铺上下文</span></div>
          <div><strong>全链路</strong><span>操作审计与任务反馈</span></div>
        </div>
      </div>
      <p class="login-story__note">当前为产品基础骨架演示，页面数据均为演示数据。</p>
    </section>

    <section class="login-panel">
      <div class="login-card">
        <div class="login-card__heading">
          <span class="login-card__status"><i></i>演示服务可用</span>
          <h2>登录运营中枢</h2>
          <p>登录后默认进入运营总览，统一查看全部店铺。</p>
        </div>

        <el-form label-position="top" @submit.prevent="submit">
          <el-form-item label="账号">
            <el-input
              v-model="form.account"
              :prefix-icon="User"
              size="large"
              autocomplete="username"
            />
          </el-form-item>
          <el-form-item label="密码">
            <el-input
              v-model="form.password"
              :prefix-icon="Lock"
              size="large"
              type="password"
              show-password
              autocomplete="current-password"
              @keyup.enter="submit"
            />
          </el-form-item>
          <el-button
            class="login-card__submit"
            type="primary"
            size="large"
            :loading="isSubmitting"
            @click="submit"
            >进入工作台</el-button
          >
        </el-form>

        <div class="demo-credentials">
          <span>演示账号</span>
          <code>demo</code>
          <span>密码</span>
          <code>demo1234</code>
        </div>
      </div>
    </section>
  </main>
</template>

<style scoped lang="scss">
.login-page {
  display: grid;
  min-height: 100vh;
  grid-template-columns: minmax(420px, 0.92fr) minmax(520px, 1.08fr);
  background: #fff;
}
.login-story {
  display: flex;
  min-height: 100vh;
  flex-direction: column;
  padding: 34px 48px 30px;
  color: #fff;
  background: var(--sidebar-bg);
}
.login-story__content {
  max-width: 590px;
  margin: auto 0;
  padding-block: 60px;
}
.login-story__kicker {
  margin: 0 0 22px;
  color: #69ddd8;
  font-size: var(--font-size-label);
  font-weight: 700;
  letter-spacing: 0.12em;
}
.login-story h1 {
  max-width: 540px;
  margin: 0;
  font-size: clamp(42px, 5vw, 72px);
  line-height: 1.08;
  letter-spacing: -0.04em;
}
.login-story__lead {
  max-width: 550px;
  margin: 28px 0 0;
  color: #c7d6eb;
  font-size: var(--font-size-section-title);
  line-height: 1.75;
}
.login-story__proof {
  display: grid;
  grid-template-columns: 0.7fr 0.8fr 1.35fr;
  gap: 22px;
  margin-top: 54px;
  padding-top: 26px;
  border-top: 1px solid rgb(255 255 255 / 16%);
}
.login-story__proof strong,
.login-story__proof span {
  display: block;
}
.login-story__proof strong {
  margin-bottom: 8px;
  font-size: 24px;
}
.login-story__proof span {
  color: #aebfda;
  font-size: var(--font-size-label);
  line-height: 1.5;
}
.login-story__note {
  margin: 0;
  color: #8fa6c8;
  font-size: var(--font-size-label);
}
.login-panel {
  display: grid;
  min-height: 100vh;
  padding: 60px;
  place-items: center;
  background: #f7faff;
}
.login-card {
  width: min(430px, 100%);
  padding: 44px;
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: 16px;
  box-shadow: 0 24px 70px rgb(26 61 112 / 12%);
}
.login-card__heading {
  margin-bottom: 32px;
}
.login-card__status {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 24px;
  color: var(--success-dark);
  font-size: var(--font-size-label);
}
.login-card__status i {
  width: 8px;
  height: 8px;
  background: var(--success);
  border-radius: 50%;
  box-shadow: 0 0 0 4px rgb(25 189 133 / 12%);
}
.login-card h2 {
  margin: 0;
  color: var(--text-primary);
  font-size: 30px;
  letter-spacing: -0.025em;
}
.login-card__heading p {
  margin: 10px 0 0;
  color: var(--text-secondary);
  line-height: 1.7;
}
.login-card :deep(.el-form-item) {
  margin-bottom: 22px;
}
.login-card :deep(.el-form-item__label) {
  color: var(--text-primary);
  font-weight: 600;
}
.login-card :deep(.el-input__wrapper) {
  min-height: 48px;
  border-radius: 8px;
  box-shadow: 0 0 0 1px var(--border) inset;
}
.login-card :deep(.el-input__wrapper.is-focus) {
  box-shadow:
    0 0 0 3px rgb(36 116 245 / 12%),
    0 0 0 1px var(--primary) inset;
}
.login-card__submit {
  width: 100%;
  min-height: 48px;
  margin-top: 6px;
  border-radius: 8px;
  font-weight: 700;
}
.demo-credentials {
  display: grid;
  grid-template-columns: auto 1fr auto 1fr;
  gap: 8px;
  margin-top: 22px;
  padding: 13px 14px;
  color: var(--text-tertiary);
  background: var(--surface-muted);
  border-radius: 8px;
  font-size: var(--font-size-meta);
}
.demo-credentials code {
  color: var(--text-primary);
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
}
@media (max-width: 900px) {
  .login-page {
    grid-template-columns: 1fr;
  }
  .login-story {
    min-height: auto;
    padding: 28px;
  }
  .login-story__content {
    padding-block: 70px;
  }
  .login-story h1 {
    font-size: 44px;
  }
  .login-panel {
    min-height: auto;
    padding: 42px 24px 70px;
  }
}
</style>
