<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'

interface Cell { type: 'pillar'|'stall'; start: number; w: number; pct: number; label: string;
  color?: string; placement?: any }

const data = ref<any>(null)              // 当前主图数据（试摆预览 或 已确认运行）
const loading = ref(false)
const errorMsg = ref('')
const vendors = ref<any[]>([])
const runs = ref<any[]>([])
const drawerOpen = ref(false)
const activeRunId = ref<number|null>(null)
const selected = ref<Cell|null>(null)    // 点开的色块

const colors = ['#e8a87c','#85dcb8','#e27d60','#c38d9e','#41b3a3','#f4a261','#e76f51']
const isConfirmed = computed(() => !!data.value?.confirmed)

const cells = computed<Cell[]>(() => {
  if (!data.value) return []
  const width = data.value.segment.width_m
  const out: Cell[] = []
  for (const p of data.value.pillars || []) {
    out.push({ type: 'pillar', start: p.position_m - p.thickness_m/2, w: p.thickness_m, pct: 0, label: p.label || '挡柱' })
  }
  for (const [i, p] of (data.value.placements || []).entries()) {
    out.push({ type: 'stall', start: p.start_m, w: p.width_m, pct: 0,
      label: p.vendor_name, color: colors[i % colors.length], placement: p })
  }
  return out.sort((a,b) => a.start - b.start)
    .map(c => ({ ...c, pct: Math.max((c.w / width) * 100, 2) }))
})

const selectedGap = computed(() => {
  const gi = selected.value?.placement?.gap_index
  return (data.value?.gaps || []).find((g: any) => g.index === gi) || null
})

async function loadRuns() {
  runs.value = await api('/allocate/runs?segment_id=1')
}

async function refreshLatest() {
  data.value = await api('/allocate/latest?segment_id=1')
  activeRunId.value = data.value.confirmed ? data.value.id : null
  await loadRuns()
}

async function preview() {
  loading.value = true; errorMsg.value = ''
  try {
    data.value = await api('/allocate/preview?segment_id=1', { method: 'POST' })
    activeRunId.value = null
  } catch (e: any) { errorMsg.value = e.message }
  finally { loading.value = false }
}

async function confirmRun() {
  loading.value = true; errorMsg.value = ''
  try {
    data.value = await api('/allocate/confirm?segment_id=1', { method: 'POST' })
    activeRunId.value = data.value.id
    await loadRuns()
  } catch (e: any) {
    // 422：派生字段对账失败，整次写入作废——明确区别于「空隙不足」
    errorMsg.value = '确认入库失败（整次作废、未写入任何行）：' + parseErr(e.message)
  } finally { loading.value = false }
}

function parseErr(raw: string) {
  try {
    const j = JSON.parse(raw)
    return (j.details || [j.message || raw]).join('；')
  } catch { return raw }
}

async function openRun(runId: number) {
  loading.value = true; errorMsg.value = ''
  try {
    data.value = await api(`/allocate/runs/${runId}`)
    activeRunId.value = runId
  } catch (e: any) { errorMsg.value = e.message }
  finally { loading.value = false }
}

onMounted(async () => {
  vendors.value = await api('/vendors')
  await refreshLatest()
})
</script>
<template>
  <div class="ss-street-wrap">
    <div class="ss-map-head">
      <h1>街段分配带</h1>
      <button class="btn-link" @click="drawerOpen = !drawerOpen">
        {{ drawerOpen ? '收起' : '打开' }}运行抽屉 ({{ runs.length }})
      </button>
    </div>
    <p class="sub">沿街一维开间 · 挡柱为竖直阻断 · 点摊档色块对账空档序号与距柱</p>

    <div class="ss-actions">
      <button class="btn" :disabled="loading" @click="preview">试摆预览（零写库）</button>
      <button class="btn btn-confirm" :disabled="loading || isConfirmed" @click="confirmRun">
        确认入库
      </button>
      <span v-if="isConfirmed" class="badge badge-ok">已入库 · 运行 #{{ data.id }}</span>
      <span v-else class="badge badge-warn">预览 · 未入库，刷新即失，不产生运行</span>
    </div>
    <p v-if="errorMsg" class="ss-error">{{ errorMsg }}</p>

    <div class="ss-band-ruler" v-if="data">
      <span>0 m</span>
      <span>{{ data.segment.name }} · {{ data.segment.width_m }} m</span>
      <span>{{ data.segment.width_m }} m</span>
    </div>
    <div class="ss-street-band" v-if="data">
      <div class="ss-street-inner">
        <div
          v-for="(c,i) in cells" :key="i"
          class="ss-band-cell"
          :class="{ 'ss-pillar': c.type === 'pillar', 'ss-preview-cell': c.type === 'stall' && !isConfirmed }"
          :style="{ width: c.pct + '%', background: c.type === 'pillar' ? undefined : c.color, flex: '0 0 ' + c.pct + '%' }"
          @click="c.type === 'stall' && (selected = c)"
        >
          <span class="ss-cell-tag" v-if="c.type==='stall'">{{ isConfirmed ? '' : '预览' }}{{ c.label }}</span>
        </div>
      </div>
    </div>

    <div class="ss-vendor-queue">
      <div v-for="v in vendors" :key="v.id" class="ss-vendor-chip">
        <strong>{{ v.name }}</strong>
        <span>需 {{ v.stall_width_m }} m · 优先 {{ v.priority }}</span>
      </div>
    </div>

    <div class="ss-grid">
      <div class="card">
        <h2 class="ss-card-title">{{ isConfirmed ? '正式入库占位行' : '试摆落点（未落库）' }}</h2>
        <table>
          <thead><tr><th>摊主号</th><th>名称</th><th>起</th><th>止</th><th>宽</th><th>空档</th><th>距左禁入沿</th></tr></thead>
          <tbody>
            <tr v-for="p in data?.stalls || data?.placements || []" :key="p.vendor_id"
                class="ss-row-click" @click="selected = { type:'stall', start:p.start_m, w:p.width_m, pct:0, label:p.vendor_name, placement:p }">
              <td>{{ p.vendor_id }}</td>
              <td>{{ p.vendor_name }}</td>
              <td>{{ p.start_m }}</td><td>{{ p.end_m }}</td><td>{{ p.width_m }}</td>
              <td>#{{ p.gap_index }}</td><td>{{ p.offset_from_gap_left_m }} m</td>
            </tr>
          </tbody>
        </table>
        <p v-if="!(data?.placements || []).length" class="muted">暂无落点</p>
      </div>

      <div class="card" v-if="data">
        <h2 class="ss-card-title">柱间空档（切空口径）</h2>
        <table>
          <thead><tr><th>序号</th><th>左禁入沿</th><th>右禁入沿</th><th>净长</th></tr></thead>
          <tbody>
            <tr v-for="g in data.gaps" :key="g.index">
              <td>#{{ g.index }}</td><td>{{ g.start_m }}</td><td>{{ g.end_m }}</td>
              <td>{{ (g.end_m - g.start_m).toFixed(3) }} m</td>
            </tr>
          </tbody>
        </table>
        <h2 class="ss-card-title" style="margin-top:0.6rem">放不下（空隙不足）</h2>
        <table v-if="data.rejected.length">
          <thead><tr><th>摊主</th><th>宽</th><th>原因</th></tr></thead>
          <tbody>
            <tr v-for="r in data.rejected" :key="r.vendor_id">
              <td>{{ r.vendor_name }}</td><td>{{ r.width_m }}</td><td>{{ r.reason }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="muted">全部放下</p>
      </div>
    </div>

    <!-- 点开色块：与切空结果/入库行同一口径 -->
    <div class="ss-modal-mask" v-if="selected" @click.self="selected = null">
      <div class="ss-modal">
        <h3>摊档落点 · {{ selected.placement.vendor_name }}</h3>
        <table>
          <tbody>
            <tr><th>状态</th><td><span :class="isConfirmed ? 'badge badge-ok' : 'badge badge-warn'">
              {{ isConfirmed ? `已入库 #${data.id}` : '预览未入库' }}</span></td></tr>
            <tr><th>摊主号 / 名称</th><td>{{ selected.placement.vendor_id }} · {{ selected.placement.vendor_name }}</td></tr>
            <tr><th>起 / 止米</th><td>{{ selected.placement.start_m }} ~ {{ selected.placement.end_m }} m</td></tr>
            <tr><th>宽度</th><td>{{ selected.placement.width_m }} m</td></tr>
            <tr><th>所属柱间空档</th><td>#{{ selected.placement.gap_index }}
              <span class="muted" v-if="selectedGap">（左禁入沿 {{ selectedGap.start_m }} m / 右禁入沿 {{ selectedGap.end_m }} m）</span></td></tr>
            <tr><th>距该空档左禁入沿</th><td><strong>{{ selected.placement.offset_from_gap_left_m }} m</strong>
              <span class="muted">= 起点 {{ selected.placement.start_m }} − 左沿 {{ selectedGap?.start_m }}</span></td></tr>
          </tbody>
        </table>
        <div class="ss-modal-actions"><button class="btn" @click="selected = null">关闭</button></div>
      </div>
    </div>

    <!-- 运行抽屉：历史已确认运行，展开库行对账 -->
    <transition name="ss-drawer">
      <aside class="ss-drawer" v-if="drawerOpen">
        <div class="ss-drawer-head">
          <strong>运行抽屉</strong>
          <button class="btn-link" @click="drawerOpen = false">×</button>
        </div>
        <p class="muted ss-drawer-note">仅列已确认入库运行；试摆预览不产生运行。</p>
        <div v-if="!runs.length" class="muted">尚无已入库运行</div>
        <div v-for="r in runs" :key="r.id"
             class="ss-run-item" :class="{ active: r.id === activeRunId }"
             @click="openRun(r.id)">
          <div class="ss-run-line">
            <strong>#{{ r.id }}</strong>
            <span class="badge badge-ok">已入库</span>
            <span class="muted">{{ r.created_at }}</span>
          </div>
          <div class="muted ss-run-sub">
            {{ r.segment?.name }} · 入库 {{ r.placement_count }} 行 · 放不下 {{ r.rejected_count }}
          </div>
          <table v-if="r.id === activeRunId && data?.stalls" class="ss-run-stalls">
            <thead><tr><th>摊主</th><th>起~止</th><th>空档</th><th>距左沿</th></tr></thead>
            <tbody>
              <tr v-for="s in data.stalls" :key="s.vendor_id">
                <td>{{ s.vendor_id }}·{{ s.vendor_name }}</td>
                <td>{{ s.start_m }}~{{ s.end_m }}</td>
                <td>#{{ s.gap_index }}</td><td>{{ s.offset_from_gap_left_m }} m</td>
              </tr>
            </tbody>
          </table>
        </div>
      </aside>
    </transition>
  </div>
</template>

<style scoped>
.ss-map-head { display: flex; align-items: baseline; gap: 1rem; }
.ss-map-head h1 { margin-bottom: 0; }
.btn-link { background: none; border: none; color: var(--ss-accent); cursor: pointer; font-weight: 700; font-size: 0.82rem; }
.ss-actions { display: flex; align-items: center; gap: 0.6rem; margin: 0.35rem 0 0.5rem; flex-wrap: wrap; }
.btn-confirm { background: var(--ss-ok); }
.ss-error {
  background: rgba(163,58,44,0.12); border: 1px solid var(--ss-bad);
  color: var(--ss-bad); padding: 0.45rem 0.65rem; border-radius: 3px; font-size: 0.82rem;
}
.ss-preview-cell {
  outline: 2px dashed rgba(26,20,14,0.65); outline-offset: -3px;
  opacity: 0.6; background-image: repeating-linear-gradient(45deg, rgba(255,255,255,0.35) 0 6px, transparent 6px 12px) !important;
  cursor: pointer;
}
.ss-band-cell { cursor: default; }
.ss-band-cell:not(.ss-pillar) { cursor: pointer; }
.ss-cell-tag { pointer-events: none; }
.ss-grid { display: grid; grid-template-columns: 1.2fr 1fr; gap: 0.85rem; }
@media (max-width: 900px) { .ss-grid { grid-template-columns: 1fr; } }
.ss-card-title { font-size: 0.92rem; margin: 0 0 0.5rem; }
.ss-row-click { cursor: pointer; }
.ss-row-click:hover { background: rgba(196,92,38,0.1); }

.ss-modal-mask {
  position: fixed; inset: 0; background: rgba(26,20,14,0.5);
  display: flex; align-items: center; justify-content: center; z-index: 50;
}
.ss-modal {
  background: var(--ss-paper); border: 2px solid var(--ss-curb); border-radius: 4px;
  width: min(520px, 92vw); padding: 1rem 1.1rem; box-shadow: 4px 6px 0 rgba(26,20,14,0.25);
}
.ss-modal h3 { margin: 0 0 0.6rem; font-size: 1rem; }
.ss-modal th { width: 42%; }
.ss-modal-actions { text-align: right; margin-top: 0.7rem; }

.ss-drawer {
  position: fixed; top: 42px; right: 0; bottom: 0; width: min(380px, 92vw);
  background: var(--ss-paper); border-left: 3px solid var(--ss-accent);
  box-shadow: -4px 0 18px rgba(26,20,14,0.25); z-index: 40;
  padding: 0.8rem 0.9rem; overflow-y: auto;
}
.ss-drawer-head { display: flex; justify-content: space-between; align-items: center; font-size: 1rem; }
.ss-drawer-note { font-size: 0.75rem; margin: 0.3rem 0 0.6rem; }
.ss-run-item {
  border: 2px solid var(--ss-curb); border-radius: 4px; padding: 0.5rem 0.65rem;
  margin-bottom: 0.5rem; cursor: pointer; background: rgba(255,255,255,0.4);
}
.ss-run-item.active { border-color: var(--ss-accent); background: rgba(196,92,38,0.08); }
.ss-run-line { display: flex; align-items: center; gap: 0.5rem; font-size: 0.85rem; }
.ss-run-sub { font-size: 0.75rem; margin-top: 0.15rem; }
.ss-run-stalls { margin-top: 0.5rem; font-size: 0.75rem; }
.ss-drawer-enter-active, .ss-drawer-leave-active { transition: transform 0.18s ease; }
.ss-drawer-enter-from, .ss-drawer-leave-to { transform: translateX(100%); }
</style>
