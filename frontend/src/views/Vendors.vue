<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
const editId = ref<number | null>(null)
const editName = ref('')
const error = ref('')

async function load() { rows.value = await api('/vendors') }
onMounted(load)

function startEdit(r: any) {
  editId.value = r.id
  editName.value = r.name
  error.value = ''
}

async function saveRename(r: any) {
  error.value = ''
  try {
    await api(`/vendors/${r.id}`, { method: 'PATCH', body: JSON.stringify({ name: editName.value }) })
    editId.value = null
    await load()
  } catch (e: any) {
    try { error.value = JSON.parse(e?.message || '')?.detail || e?.message } catch { error.value = e?.message || String(e) }
  }
}
</script>

<template>
  <h1>摊主队列</h1>
  <p class="sub">底部排队条 · 宽度与优先级 · 改名只影响之后的确认，旧运行保留旧名</p>
  <div class="ss-vendor-queue" style="border-top:none; background:transparent; margin:0; padding:0.5rem 0 1rem">
    <div v-for="r in rows" :key="r.id ?? JSON.stringify(r)" class="ss-vendor-chip">
      <strong>{{ r.name }}</strong>
      <span>需 {{ r.stall_width_m }} m · 优先 {{ r.priority }}</span>
    </div>
  </div>
  <p v-if="error" class="ss-error">{{ error }}</p>
  <div class="card">
    <table>
      <thead><tr><th>摊主号</th><th>摊主</th><th>宽度(m)</th><th>优先级</th><th></th></tr></thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id ?? JSON.stringify(r)">
          <td>{{ r.id }}</td>
          <td>
            <span v-if="editId !== r.id">{{ r.name }}</span>
            <input v-else v-model="editName" class="ss-rename-input" @keyup.enter="saveRename(r)" />
          </td>
          <td>{{ r.stall_width_m }}</td>
          <td>{{ r.priority }}</td>
          <td>
            <button v-if="editId !== r.id" class="btn ss-btn-ghost" @click="startEdit(r)">改名</button>
            <button v-else class="btn" @click="saveRename(r)">保存</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
