# Dashboard frontend / Dashboard 前端

**English:** These dependency-free static assets are served by FastAPI: `index.html` defines structure, `styles.css` defines the responsive visual system, and `app.js` reads `/api/v1` and renders interactions. Loading this UI must remain read-only and must never trigger Apify automatically.

**中文：** 这些无外部依赖的静态资源由 FastAPI 提供：`index.html` 定义结构，`styles.css` 定义响应式视觉系统，`app.js` 读取 `/api/v1` 并实现交互。加载界面必须保持只读，绝不能自动触发 Apify。
