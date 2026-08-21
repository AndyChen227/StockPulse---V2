# Dashboard frontend / Dashboard 前端

[English](#english) · [简体中文](#简体中文)

## English

FastAPI serves these dependency-free static assets:

| File | Responsibility |
|---|---|
| `index.html` | Semantic page structure |
| `styles.css` | Responsive visual system, states, and accessibility |
| `app.js` | `/api/v1` client, filtering, navigation, and rendering |

Loading this UI must remain read-only and must never trigger Apify
automatically.

---

## 简体中文

这些无外部依赖的静态资源由 FastAPI 提供：

| 文件 | 职责 |
|---|---|
| `index.html` | 语义化页面结构 |
| `styles.css` | 响应式视觉系统、状态和无障碍支持 |
| `app.js` | `/api/v1` 客户端、筛选、导航和渲染 |

加载界面必须保持只读，绝不能自动触发 Apify。
