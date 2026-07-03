<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import LogisticsMap from './components/LogisticsMap.vue'

const now = ref(new Date())

let clockTimer: number | undefined

onMounted(() => {
  clockTimer = window.setInterval(() => {
    now.value = new Date()
  }, 1000)
})

onBeforeUnmount(() => {
  if (clockTimer) {
    window.clearInterval(clockTimer)
  }
})

const formattedTime = computed(() =>
  new Intl.DateTimeFormat('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    weekday: 'short',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(now.value),
)

const metrics = [
  { label: '운송 중 HBL', value: '126', tone: 'blue' },
  { label: 'DIRECT Risk', value: '8', tone: 'red' },
  { label: 'ETA 반복 지연', value: '14', tone: 'orange' },
  { label: '생산 영향 후보', value: '3', tone: 'green' },
]

const alerts = [
  {
    severity: 'CRITICAL',
    title: '홍해·수에즈 항로 위험 확대',
    description: '영향 선적 8건 · 48시간 내 접근 3척',
    time: '14:20',
  },
  {
    severity: 'HIGH',
    title: 'Shanghai 항만 적체',
    description: '영향 선적 12건 · 평균 ETA +3.4일',
    time: '13:45',
  },
  {
    severity: 'MEDIUM',
    title: 'Panama Canal 통항 모니터링',
    description: '관련 선적 5건 · 현재 우회 없음',
    time: '11:30',
  },
]
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="brand">
        <div class="brand-mark">LRI</div>

        <div>
          <h1>Global Logistics Risk Intelligence</h1>
          <p>SK-ON Logistics AI Trigger Hub</p>
        </div>
      </div>

      <div class="topbar-status">
        <span class="live-badge">
          <span class="live-dot"></span>
          LIVE
        </span>

        <span>{{ formattedTime }}</span>
      </div>
    </header>

    <main class="dashboard">
      <section class="map-panel">
        <LogisticsMap />
      </section>

      <aside class="side-panel">
        <section class="panel-section">
          <div class="section-heading">
            <div>
              <span class="eyebrow">OVERVIEW</span>
              <h2>물류 위험 현황</h2>
            </div>

            <button type="button" class="ghost-button">새로고침</button>
          </div>

          <div class="metrics-grid">
            <article
              v-for="metric in metrics"
              :key="metric.label"
              class="metric-card"
              :class="`metric-${metric.tone}`"
            >
              <span>{{ metric.label }}</span>
              <strong>{{ metric.value }}</strong>
            </article>
          </div>
        </section>

        <section class="panel-section alerts-section">
          <div class="section-heading">
            <div>
              <span class="eyebrow">EARLY WARNING</span>
              <h2>주요 리스크 이벤트</h2>
            </div>

            <span class="event-count">{{ alerts.length }}</span>
          </div>

          <div class="alert-list">
            <article
              v-for="alert in alerts"
              :key="alert.title"
              class="alert-card"
              :class="`severity-${alert.severity.toLowerCase()}`"
            >
              <div class="alert-level">
                {{ alert.severity }}
              </div>

              <div class="alert-body">
                <strong>{{ alert.title }}</strong>
                <p>{{ alert.description }}</p>
              </div>

              <time>{{ alert.time }}</time>
            </article>
          </div>
        </section>

        <section class="panel-section shipment-section">
          <span class="eyebrow">SELECTED SHIPMENT</span>
          <h2>선택 선적 상세</h2>

          <dl class="detail-grid">
            <div>
              <dt>HBL</dt>
              <dd>HBL-2026-001</dd>
            </div>
            <div>
              <dt>Vessel</dt>
              <dd>SKON DEMO 01</dd>
            </div>
            <div>
              <dt>Route</dt>
              <dd>Busan → Koper</dd>
            </div>
            <div>
              <dt>ETA</dt>
              <dd class="danger-text">07/18 → 07/24</dd>
            </div>
            <div>
              <dt>PO</dt>
              <dd>4건</dd>
            </div>
            <div>
              <dt>Item</dt>
              <dd>7개</dd>
            </div>
          </dl>

          <button type="button" class="primary-button">
            상세 영향 분석
          </button>
        </section>
      </aside>
    </main>

    <footer class="statusbar">
      <div>
        <span class="status-indicator ok"></span>
        B-LAP 연결 정상
      </div>

      <div>
        <span class="status-indicator ok"></span>
        Data Lake 연결 정상
      </div>

      <div>
        <span class="status-indicator warning"></span>
        AIS Mock Data
      </div>

      <div class="status-message">
        마지막 갱신: 방금 전
      </div>
    </footer>
  </div>
</template>
