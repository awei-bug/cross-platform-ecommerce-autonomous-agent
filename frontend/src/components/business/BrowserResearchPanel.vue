<script setup lang="ts">
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { ElMessage } from 'element-plus'
import { computed, ref } from 'vue'
import { ecomApi } from '../../api/ecomops'
import { useSessionStore } from '../../stores/session'

const session = useSessionStore()
const client = useQueryClient()
const selected = ref('')
const currency = ref('USD')
const commission = ref(15)
const advertising = ref(10)
const margin = ref(15)
const importing = ref(false)
const collections = useQuery({
  queryKey: ['ecomops', 'research-collections'],
  queryFn: () => ecomApi.researchCollections(session.token!),
})
const collectionKey = (id: string, country: string) => `${id}:${country}`
const current = computed(
  () =>
    collections.data.value?.find(
      (c) => collectionKey(c.collection_id, c.country) === selected.value,
    ) ?? collections.data.value?.[0],
)
const request = computed(() => ({
  collection_id: current.value?.collection_id,
  country: current.value?.country,
  currency: currency.value,
  commission_pct: commission.value,
  ad_rate_pct: advertising.value,
  target_margin_pct: margin.value,
}))
const report = useQuery({
  queryKey: computed(() => ['ecomops', 'research-report', request.value]),
  queryFn: () => ecomApi.analyzeResearch(session.token!, request.value),
  enabled: computed(() => Boolean(current.value)),
})
async function importFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  importing.value = true
  try {
    if (file.size > 1024 * 1024) throw new Error('文件超过1MB，请分批导入')
    const batch = JSON.parse(await file.text())
    await ecomApi.importResearch(session.token!, batch)
    selected.value = collectionKey(batch.collection_id, batch.country)
    await client.invalidateQueries({ queryKey: ['ecomops'] })
    ElMessage.success('公开竞品证据已入库')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '导入失败，请检查采集结果文件')
  } finally {
    importing.value = false
    input.value = ''
  }
}
</script>

<template>
  <section class="browser-research" aria-labelledby="research-heading">
    <h2 id="research-heading">公开竞品与热销证据</h2>
    <p>无需店铺授权。查看浏览器采集的商品、榜单和规格，用可调整的费率假设筛查成本空间。</p>
    <div class="research-controls">
      <label class="research-file"
        >{{ importing ? '正在导入…' : '导入采集结果文件' }}
        <input
          type="file"
          accept=".json,application/json"
          :disabled="importing"
          @change="importFile"
        />
      </label>
      <el-button :loading="collections.isFetching.value" @click="collections.refetch()"
        >刷新采集批次</el-button
      >
    </div>
    <el-alert
      v-if="collections.isError.value"
      title="采集批次读取失败，请刷新重试"
      type="error"
      :closable="false"
    />
    <el-skeleton v-else-if="collections.isPending.value" :rows="2" animated />
    <p v-else-if="!current">
      尚无公开采集结果。完成浏览器采集后，导入 observations.json；价格、来源和采集时间会一起保存。
    </p>
    <template v-else>
      <el-form label-position="top" class="research-assumptions">
        <el-form-item label="采集批次">
          <el-select
            :model-value="selected || collectionKey(current.collection_id, current.country)"
            aria-label="采集批次"
            @update:model-value="selected = $event"
          >
            <el-option
              v-for="c in collections.data.value"
              :key="collectionKey(c.collection_id, c.country)"
              :value="collectionKey(c.collection_id, c.country)"
              :label="`${c.category} · ${c.country} · ${c.count}件`"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="分析币种"
          ><el-select v-model="currency" aria-label="分析币种"
            ><el-option
              v-for="c in ['USD', 'EUR', 'GBP', 'JPY', 'CNY']"
              :key="c"
              :value="c"
              :label="c" /></el-select
        ></el-form-item>
        <el-form-item label="佣金假设 %"
          ><el-input-number v-model="commission" aria-label="佣金假设" :min="0" :max="99"
        /></el-form-item>
        <el-form-item label="广告假设 %"
          ><el-input-number v-model="advertising" aria-label="广告假设" :min="0" :max="99"
        /></el-form-item>
        <el-form-item label="目标毛利 %"
          ><el-input-number v-model="margin" aria-label="目标毛利" :min="0" :max="99"
        /></el-form-item>
      </el-form>
      <p>
        可承受成本＝页面售价×（1－佣金率－广告率－目标毛利率），须覆盖采购、物流、税费、履约、包装与损耗等全部非比例成本。未取得报价前，不给出盈利结论。
      </p>
      <el-alert
        v-if="report.isError.value"
        title="分析读取失败，请重试"
        type="error"
        :closable="false"
      />
      <el-button v-if="report.isError.value" @click="report.refetch()">重试分析</el-button>
      <el-skeleton v-if="report.isFetching.value" :rows="3" animated />
      <template v-else-if="report.data.value">
        <p role="status">
          {{ report.data.value.sample_count }} 件有效价格样本，{{
            report.data.value.ranked_sample_count
          }}
          件附榜单证据；{{ report.data.value.excluded.length }} 件因价格、币种或证据缺失未参与测算。
        </p>
        <el-table
          :data="report.data.value.candidates"
          empty-text="该币种暂无有效样本，请切换币种或补采价格"
        >
          <el-table-column prop="title" label="商品" min-width="230" />
          <el-table-column label="页面售价" width="115"
            ><template #default="{ row }"
              >{{ row.currency }} {{ row.price }}</template
            ></el-table-column
          >
          <el-table-column label="热销依据" min-width="190"
            ><template #default="{ row }">
              <a
                v-if="row.ranking"
                :href="row.ranking.source_url"
                target="_blank"
                rel="noopener noreferrer"
                >{{ row.ranking.category }} #{{ row.ranking.rank }}</a
              >
              <span v-else>未采集榜单</span>
              <p v-if="row.popularity_claim">页面声明：{{ row.popularity_claim }}</p>
            </template></el-table-column
          >
          <el-table-column label="可承受成本" width="130"
            ><template #default="{ row }">{{
              row.max_fixed_cost_at_target_margin === null
                ? '无正成本空间'
                : `${row.currency} ${row.max_fixed_cost_at_target_margin.toFixed(2)}`
            }}</template></el-table-column
          >
          <el-table-column label="规格与来源" min-width="210"
            ><template #default="{ row }">
              <details>
                <summary>查看页面证据</summary>
                <a :href="row.source_url" target="_blank" rel="noopener noreferrer">打开原商品页</a>
                <p>采集于 {{ new Date(row.collected_at).toLocaleString('zh-CN') }}</p>
                <dl>
                  <template v-for="(value, key) in row.specifications" :key="key"
                    ><dt>{{ key }}</dt>
                    <dd>{{ value }}</dd></template
                  >
                </dl>
              </details>
            </template></el-table-column
          >
        </el-table>
        <details class="research-limits">
          <summary>样本与测算边界</summary>
          <ul>
            <li v-for="item in report.data.value.limitations" :key="item">{{ item }}</li>
          </ul>
        </details>
      </template>
    </template>
  </section>
</template>

<style scoped>
.browser-research {
  padding-bottom: 28px;
  margin-bottom: 28px;
  border-bottom: 1px solid var(--el-border-color);
}
.browser-research p {
  color: var(--text-secondary);
  line-height: 1.6;
  max-width: 75ch;
}
.research-controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin: 16px 0;
}
.research-file {
  display: grid;
  gap: 6px;
  font-size: 14px;
}
.research-assumptions {
  display: grid;
  grid-template-columns: minmax(200px, 2fr) repeat(4, minmax(120px, 1fr));
  gap: 12px;
  margin-top: 20px;
}
.research-assumptions :deep(.el-input-number) {
  width: 100%;
}
a {
  color: var(--el-color-primary);
  overflow-wrap: anywhere;
}
summary {
  cursor: pointer;
  color: var(--text-primary);
}
dd {
  margin: 0 0 8px;
  overflow-wrap: anywhere;
}
dt {
  font-weight: 600;
}
.research-limits {
  margin-top: 16px;
}
@media (max-width: 1000px) {
  .research-assumptions {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .research-assumptions :first-child {
    grid-column: 1 / -1;
  }
}
@media (max-width: 540px) {
  .research-assumptions {
    grid-template-columns: 1fr;
  }
}
</style>
