<template>
  <div class="page">
    <header class="page-header">
      <div class="title-block">
        <h1>Factures</h1>
        <p class="subtitle">Gestion des factures et documents comptables.</p>
      </div>
    </header>
    <div class="placeholder">
      <div class="placeholder-icon">🧾</div>
      <h2>Fonctionnalité en cours de développement</h2>
      <p>La gestion des factures sera disponible dans une prochaine version.</p>
    </div>
  </div>
</template>

<script setup></script>

<style scoped>
.page {
  padding: 28px;
  color: #e5e7eb;
  background: #0b1220;
  min-height: 100vh;
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;
}
.page-header { margin-bottom: 32px; }
.title-block h1 { margin: 0; font-size: 28px; }
.subtitle { margin: 6px 0 0; color: #9ca3af; font-size: 14px; }

.placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 64px 32px;
  border: 1px dashed rgba(148,163,184,0.25);
  border-radius: 16px;
  background: rgba(15,23,42,0.4);
  text-align: center;
}
.placeholder-icon { font-size: 56px; }
.placeholder h2 { margin: 0; font-size: 20px; color: #cbd5e1; }
.placeholder p { margin: 0; color: #6b7280; font-size: 14px; }
</style>
