<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'

const data = ref<any>(null)        // 主图当前数据：已入库运行 / 试摆预览 / 空态
const vendors = ref<any[]>([])
const error = ref('')
const selected = ref<any>(null)    // 主图点开的摊位
const drawerOpen = ref(false)
const runs = ref<any[]>([])
const drawerRun = ref<any>(null)

function errText(e: any): string {
  try {
    const j = JSON.parse(e?.message || '')
    if (j?.detail) return j.detail
  } catch { /* 非 JSON 错误体 */ }
  return e?.message || String(e)
}

async function loadLatest() {
  error.value = ''
  try {
    data.value = await api('/allocate/latest?segment_id=1')
    selected.value = null
  } catch (e) { error.value = errText(e) }
}

async function preview() {
  error.value = ''
  try {
    data.value = await api('/allocate/preview?segment_id=1', { method: 'POST' })
    selected.value = null
  } catch (e) { error.value = errText(e) }
}

async function confirm() {
  error.value = ''
  try {
    data.value = await api('/allocate/confirm?segment_id=1', { method: 'POST' })
    selected.value = null
  } catch (e) { error.value = errText(e) }
}

async function openDrawer() {
  drawerOpen.value = true
  error.value = ''
  try {
    runs.value = await api('/allocate/runs?segment_id=1')
    drawerRun.value = runs.value.length ? await api(`/allocate/runs/${runs.value[0].id}`) : null
  } catch (e) { error.value = errText(e) }
}

async function selectRun(id: number) {
  error.value = ''
  try { drawerRun.value = await api(`/allocate/runs/${id}`) }
  catch (e) { error.value = errText(e) }
}

onMounted(async () => {
  vendors.value = await api('/vendors')
  await loadLatest()
})

const colors = ['#e8a87c', '#85dcb8', '#e27d60', '#c38d9e', '#41b3a3', '#f4a261', '#e76f51']

const isPreview = computed(() => !!data.value && !data.value.persisted && (data.value.placements || []).length > 0)

const stateBadge = computed(() => {
  if (!data.value) return { cls: 'ss-badge-empty', text: '加载中' }
  if (data.value.persisted) return { cls: 'ss-badge-persisted', text: `已入库 · 运行 #${data.value.run_id}` }
  if ((data.value.placements || []).length) return { cls: 'ss-badge-preview', text: '试摆预览 · 未入库' }
  return { cls: 'ss-badge-empty', text: '尚未入库 · 可试摆或确认' }
})

const cells = computed(() => {
  if (!data.value) return []
  const width = data.value.segment.width_m
  const out: any[] = []
  for (const p of data.value.pillars || []) {
    out.push({ type: 'pillar', start: p.position_m - p.thickness_m / 2, w: p.thickness_m, label: p.label || '挡柱' })
  }
  for (const [i, p] of (data.value.placements || []).entries()) {
    out.push({ type: 'stall', start: p.start_m, w: p.width_m, label: p.vendor_name, color: colors[i % colors.length], p })
  }
  return out.sort((a, b) => a.start - b.start).map(c => ({ ...c, pct: Math.max((c.w / width) * 100, 2) }))
})

function openInfo(c: any) {
  if (c.type !== 'stall') return
  selected.value = c.p
}
</script>

<template>
  <div class="ss-street-wrap">
    <h1>街段分配带</h1>
    <p class="sub">沿街一维开间 · 挡柱为竖直阻断 · 确认才入库，试摆零写</p>
    <div class="ss-map-toolbar">
      <button class="btn" @click="preview">试摆预览</button>
      <button class="btn ss-btn-confirm" @click="confirm">确认入库</button>
      <button class="btn ss-btn-ghost" @click="openDrawer">运行抽屉</button>
      <span class="ss-state-badge" :class="stateBadge.cls">{{ stateBadge.text }}</span>
    </div>
    <p v-if="error" class="ss-error">{{ error }}</p>
    <div class="ss-band-ruler" v-if="data">
      <span>0 m</span>
      <span>{{ data.segment.name }} · {{ data.segment.width_m }} m</span>
      <span>{{ data.segment.width_m }} m</span>
    </div>
    <div class="ss-street-band" v-if="data">
      <div class="ss-street-inner">
        <div
          v-for="(c, i) in cells" :key="i"
          class="ss-band-cell"
          :class="{ 'ss-pillar': c.type === 'pillar', 'ss-preview': c.type === 'stall' && isPreview, 'ss-clickable': c.type === 'stall' }"
          :style="{ width: c.pct + '%', backgroundColor: c.type === 'pillar' ? undefined : c.color, flex: '0 0 ' + c.pct + '%' }"
          @click="openInfo(c)"
        >{{ c.label }}</div>
      </div>
    </div>

    <div v-if="selected" class="card ss-click-info">
      <div class="ss-click-info-head">
        <strong>{{ selected.vendor_name }}</strong>
        <span class="ss-state-badge" :class="stateBadge.cls">{{ stateBadge.text }}</span>
      </div>
      <div class="ss-click-info-grid">
        <span>摊主号</span><b>{{ selected.vendor_id }}</b>
        <span>街段</span><b>{{ data.segment.name }}</b>
        <span>起止</span><b>{{ selected.start_m }} – {{ selected.end_m }} m</b>
        <span>宽度</span><b>{{ selected.width_m }} m</b>
        <span>空档序号</span><b>#{{ selected.span_index }}（{{ selected.span_left_m }} – {{ selected.span_right_m }} m）</b>
        <span>距左禁入沿</span><b>{{ selected.offset_from_span_left_m }} m</b>
      </div>
    </div>

    <div class="ss-vendor-queue">
      <div v-for="v in vendors" :key="v.id" class="ss-vendor-chip">
        <strong>{{ v.name }}</strong>
        <span>需 {{ v.stall_width_m }} m · 优先 {{ v.priority }}</span>
      </div>
    </div>

    <div class="card" v-if="data && (data.placements || []).length">
      <table>
        <thead>
          <tr><th>摊主</th><th>起点</th><th>终点</th><th>宽度</th><th>空档序号</th><th>距左禁入沿</th></tr>
        </thead>
        <tbody>
          <tr v-for="p in data.placements" :key="p.vendor_id">
            <td>{{ p.vendor_name }}</td>
            <td>{{ p.start_m }}</td>
            <td>{{ p.end_m }}</td>
            <td>{{ p.width_m }}</td>
            <td>#{{ p.span_index }}</td>
            <td>{{ p.offset_from_span_left_m }} m</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="drawerOpen" class="ss-drawer-mask" @click="drawerOpen = false">
      <aside class="ss-drawer" @click.stop>
        <div class="ss-drawer-head">
          <strong>运行抽屉 · 已入库</strong>
          <button class="btn ss-btn-ghost" @click="drawerOpen = false">收起</button>
        </div>
        <p v-if="!runs.length" class="muted">还没有已入库运行，确认入库后才会出现在这里。</p>
        <template v-else>
          <label class="ss-drawer-label">选择运行</label>
          <select class="ss-drawer-select" :value="drawerRun?.run_id" @change="selectRun(Number(($event.target as HTMLSelectElement).value))">
            <option v-for="r in runs" :key="r.id" :value="r.id">
              运行 #{{ r.id }} · {{ r.segment_name }} · {{ r.created_at }} · {{ r.placement_count }} 行
            </option>
          </select>
          <template v-if="drawerRun">
            <p class="ss-drawer-meta">
              运行 #{{ drawerRun.run_id }} · {{ drawerRun.segment.name }} · {{ drawerRun.created_at }}
            </p>
            <table>
              <thead>
                <tr><th>摊主号</th><th>摊主</th><th>起止</th><th>宽度</th><th>空档序号</th><th>距左禁入沿</th></tr>
              </thead>
              <tbody>
                <tr v-for="p in drawerRun.placements" :key="p.id">
                  <td>{{ p.vendor_id }}</td>
                  <td>{{ p.vendor_name }}</td>
                  <td>{{ p.start_m }} – {{ p.end_m }}</td>
                  <td>{{ p.width_m }} m</td>
                  <td>#{{ p.span_index }}</td>
                  <td>{{ p.offset_from_span_left_m }} m</td>
                </tr>
              </tbody>
            </table>
          </template>
        </template>
      </aside>
    </div>
  </div>
</template>
