<script setup>
import { ref } from "vue";

const props = defineProps({
  title: { type: String, required: true },
  sections: { type: Array, required: true },
  // sections: [{ heading: "How to Play", content: "..." }, ...]
});

const expanded = ref(false);
</script>

<template>
  <div class="game-guide">
    <button class="guide-toggle" @click="expanded = !expanded">
      <span class="guide-icon">{{ expanded ? '▼' : '▶' }}</span>
      <span>{{ title }}</span>
    </button>
    <div v-if="expanded" class="guide-body">
      <div v-for="(sec, i) in sections" :key="i" class="guide-section">
        <h4 v-if="sec.heading || sec.label">{{ sec.heading || sec.label }}</h4>
        <p v-html="sec.content || sec.text"></p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.game-guide {
  margin-bottom: 12px;
}

.guide-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: 1px solid #475569;
  border-radius: 8px;
  padding: 6px 14px;
  color: #94a3b8;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.15s;
  width: 100%;
  text-align: left;
}

.guide-toggle:hover {
  border-color: #64748b;
  color: #e2e8f0;
}

.guide-icon {
  font-size: 0.7rem;
}

.guide-body {
  margin-top: 8px;
  padding: 12px 16px;
  background: #1e293b;
  border-radius: 8px;
  border: 1px solid #334155;
  font-size: 0.85rem;
  color: #cbd5e1;
  line-height: 1.6;
}

.guide-section {
  margin-bottom: 8px;
}

.guide-section:last-child {
  margin-bottom: 0;
}

.guide-section h4 {
  color: #e2e8f0;
  font-size: 0.9rem;
  margin: 0 0 4px 0;
}

.guide-section p {
  margin: 0;
}
</style>
