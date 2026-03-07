import apiClient from './api/http'

const app = document.querySelector('#app')

app.innerHTML = `
  <main style="font-family: Arial, sans-serif; padding: 24px; max-width: 760px; margin: 0 auto;">
    <h1>Assignment System</h1>
    <p>前端工程已可在 IntelliJ IDEA 中直接运行。</p>
    <button id="healthBtn" style="padding: 8px 12px; cursor: pointer;">检查后端健康状态</button>
    <pre id="result" style="background: #f5f5f5; padding: 12px; margin-top: 16px;"></pre>
  </main>
`

const result = document.querySelector('#result')
document.querySelector('#healthBtn').addEventListener('click', async () => {
  result.textContent = '请求中...'
  try {
    const { data } = await apiClient.get('/health')
    result.textContent = JSON.stringify(data, null, 2)
  } catch (error) {
    result.textContent = error.message
  }
})
