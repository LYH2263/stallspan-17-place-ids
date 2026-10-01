<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
const editingId = ref<number|null>(null)
const draftName = ref('')
const saving = ref(false)
const errorMsg = ref('')

async function load() { rows.value = await api('/vendors') }
onMounted(load)

function startEdit(r: any) { editingId.value = r.id; draftName.value = r.name; errorMsg.value = '' }
function cancel() { editingId.value = null; draftName.value = '' }

async function save() {
  if (!draftName.value.trim()) { errorMsg.value = '名称不能为空'; return }
  saving.value = true; errorMsg.value = ''
  try {
    await api(`/vendors/${editingId.value}`, { method: 'PATCH', body: JSON.stringify({ name: draftName.value.trim() }) })
    // 改名只影响之后的新确认运行；旧运行按确认时名称保留，不回刷
    await load()
    cancel()
  } catch (e: any) { errorMsg.value = e.message }
  finally { saving.value = false }
}
</script>
<template>
  <h1>摊主队列</h1>
  <p class="sub">底部排队条 · 宽度与优先级 · 改名只影响之后的新确认运行，旧运行保留旧名</p>
  <div class="ss-vendor-queue" style="border-top:none; background:transparent; margin:0; padding:0.5rem 0 1rem">
    <div v-for="r in rows" :key="r.id ?? JSON.stringify(r)" class="ss-vendor-chip">
      <strong>{{ r.name }}</strong>
      <span>需 {{ r.stall_width_m }} m · 优先 {{ r.priority }}</span>
    </div>
  </div>
  <p v-if="errorMsg" class="ss-error">{{ errorMsg }}</p>
  <div class="card">
    <table>
      <thead><tr><th>摊主号</th><th>名称</th><th>宽度(m)</th><th>优先级</th><th></th></tr></thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id ?? JSON.stringify(r)">
          <td>{{ r.id }}</td>
          <td>
            <input v-if="editingId === r.id" v-model="draftName"
                   class="ss-input" @keyup.enter="save" @keyup.esc="cancel" />
            <span v-else>{{ r.name }}</span>
          </td>
          <td>{{ r.stall_width_m }}</td><td>{{ r.priority }}</td>
          <td class="ss-edit-cell">
            <template v-if="editingId === r.id">
              <button class="btn btn-mini" :disabled="saving" @click="save">保存</button>
              <button class="btn-link" @click="cancel">取消</button>
            </template>
            <button v-else class="btn-link" @click="startEdit(r)">改名</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.ss-input {
  width: 100%; padding: 0.3rem 0.45rem; font-size: 0.85rem;
  border: 2px solid var(--ss-curb); border-radius: 3px; background: #fff;
}
.ss-edit-cell { white-space: nowrap; }
.btn-mini { padding: 0.18rem 0.55rem; font-size: 0.75rem; }
.ss-error {
  background: rgba(163,58,44,0.12); border: 1px solid var(--ss-bad);
  color: var(--ss-bad); padding: 0.4rem 0.6rem; border-radius: 3px; font-size: 0.8rem;
}
</style>
