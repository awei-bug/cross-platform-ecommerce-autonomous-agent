<script setup lang="ts">
import { ArrowRight, Connection, Cpu, Lock, Setting } from '@element-plus/icons-vue'
</script>

<template>
  <section class="settings-hub">
    <header class="page-heading">
      <div>
        <div class="heading-kicker">
          <span class="kicker-icon"
            ><el-icon><Setting /></el-icon
          ></span>
          工作台配置
        </div>
        <h1>系统设置</h1>
        <p>集中管理 AI 服务、平台连接和工作台级配置。业务模块仍可通过原有直达地址访问。</p>
      </div>
      <el-tag type="success" effect="light">配置按组织隔离</el-tag>
    </header>

    <div class="settings-sections">
      <section class="settings-section">
        <div class="section-heading">
          <span class="section-label">当前可用</span>
          <h2>服务与连接</h2>
        </div>
        <RouterLink to="/ai-settings" class="settings-card">
          <span class="settings-card__icon settings-card__icon--blue">
            <el-icon :size="22"><Cpu /></el-icon>
          </span>
          <span class="settings-card__copy">
            <strong>AI 模型配置</strong>
            <small>管理厂商连接、API Key、模型发现和默认模型。</small>
          </span>
          <el-icon class="settings-card__arrow"><ArrowRight /></el-icon>
        </RouterLink>
        <RouterLink to="/integrations" class="settings-card">
          <span class="settings-card__icon settings-card__icon--green">
            <el-icon :size="22"><Connection /></el-icon>
          </span>
          <span class="settings-card__copy">
            <strong>平台连接</strong>
            <small>查看淘宝、抖店、拼多多的授权状态并发起 / 解除 OAuth 授权。</small>
          </span>
          <el-icon class="settings-card__arrow"><ArrowRight /></el-icon>
        </RouterLink>
      </section>

      <section class="settings-section settings-section--planned">
        <div class="section-heading">
          <span class="section-label">配置规划</span>
          <h2>运营基础设置</h2>
        </div>
        <div class="planned-grid">
          <article class="planned-card">
            <span class="settings-card__icon settings-card__icon--navy">
              <el-icon :size="22"><Lock /></el-icon>
            </span>
            <strong>成员与权限</strong>
            <small>组织成员、角色权限和操作审计将集中到这里。</small>
            <el-tag size="small" effect="plain">建设中</el-tag>
          </article>
        </div>
      </section>
    </div>
  </section>
</template>

<style scoped lang="scss">
.settings-hub {
  min-width: 0;
}
.page-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 20px;
}
.heading-kicker {
  display: flex;
  align-items: center;
  gap: 7px;
  color: var(--success-dark);
  font-size: var(--font-size-label);
  font-weight: 700;
}
.kicker-icon {
  display: inline-grid;
  width: 20px;
  height: 20px;
  place-items: center;
  color: var(--primary);
  background: var(--primary-soft);
  border-radius: 6px;
}
h1 {
  margin: 7px 0 6px;
  font-size: 30px;
  letter-spacing: -0.035em;
}
.page-heading p {
  max-width: 720px;
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--font-size-body);
  line-height: 1.6;
}
.settings-sections {
  display: grid;
  gap: 16px;
}
.settings-section {
  padding: 20px;
  background: #fff;
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}
.settings-section--planned {
  background: var(--surface-subtle);
}
.section-heading {
  margin-bottom: 16px;
}
.section-label {
  color: var(--primary);
  font-size: var(--font-size-meta);
  font-weight: 800;
  letter-spacing: 0.05em;
}
.section-heading h2 {
  margin: 5px 0 0;
  font-size: var(--font-size-section-title);
}
.settings-card,
.planned-card {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 82px;
  padding: 15px;
  border: 1px solid var(--border-soft);
  border-radius: 9px;
}
.settings-card {
  color: inherit;
  text-decoration: none;
  transition:
    border-color 160ms ease,
    background-color 160ms ease,
    transform 160ms var(--ease-out);
}
.settings-card + .settings-card {
  margin-top: 12px;
}
.settings-card:hover {
  background: var(--primary-softer);
  border-color: #b8d0f4;
  transform: translateY(-1px);
}
.settings-card:focus-visible {
  outline: 3px solid rgb(88 189 255 / 45%);
  outline-offset: 2px;
}
.settings-card__icon {
  display: grid;
  width: 42px;
  height: 42px;
  flex: 0 0 42px;
  place-items: center;
  border-radius: 9px;
}
.settings-card__icon--blue {
  color: var(--primary);
  background: var(--primary-soft);
}
.settings-card__icon--green {
  color: var(--success-dark);
  background: var(--success-soft);
}
.settings-card__icon--navy {
  color: var(--navy-700);
  background: rgb(32 67 113 / 10%);
}
.settings-card__copy,
.planned-card {
  min-width: 0;
}
.settings-card__copy strong,
.settings-card__copy small,
.planned-card strong,
.planned-card small {
  display: block;
}
.settings-card__copy strong,
.planned-card strong {
  color: var(--text-primary);
  font-size: var(--font-size-body);
}
.settings-card__copy small,
.planned-card small {
  margin-top: 4px;
  color: var(--text-secondary);
  font-size: var(--font-size-label);
  line-height: 1.5;
}
.settings-card__arrow {
  margin-left: auto;
  color: var(--primary);
}
.planned-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.planned-card {
  align-items: flex-start;
  flex-wrap: wrap;
}
.planned-card small {
  width: calc(100% - 56px);
}
.planned-card .el-tag {
  margin-left: 56px;
}
@media (max-width: 620px) {
  .page-heading {
    flex-direction: column;
  }
  .planned-grid {
    grid-template-columns: 1fr;
  }
}
</style>
