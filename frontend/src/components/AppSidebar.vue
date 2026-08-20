<template>
  <aside class="app-sidebar" aria-label="主导航">
    <div class="brand-mark" aria-label="电商文案质检">✓</div>
    <nav class="sidebar-nav" aria-label="工作台导航">
      <button type="button" data-current="true" aria-current="page">
        <span class="sidebar-icon" aria-hidden="true">▣</span>
        <span class="sidebar-label">质检工作台</span>
      </button>
      <button type="button" data-testid="nav-task-history" aria-disabled="true" disabled>
        <span class="sidebar-icon" aria-hidden="true">▤</span>
        <span class="sidebar-label">任务记录</span>
      </button>
      <button type="button" data-testid="nav-rule-center" aria-disabled="true" disabled>
        <span class="sidebar-icon" aria-hidden="true">◇</span>
        <span class="sidebar-label">规则中心</span>
      </button>
      <button type="button" aria-disabled="true" disabled>
        <span class="sidebar-icon" aria-hidden="true">□</span>
        <span class="sidebar-label">样例库</span>
      </button>
    </nav>
  </aside>
</template>
