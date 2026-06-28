# monster-builder

「手搓一个大怪兽」的**设计文档仓库**。一个业余做的小游戏:造怪兽、装配部件、自动对战。

本仓库目前只放**设计文档**,不含游戏代码。文档用 [MkDocs Material](https://squidfunk.github.io/mkdocs-material/) 构建,每次提交后由 GitHub Actions 自动发布成一个手机也能舒服阅读的 wiki 网站。

## 📖 在线 wiki

👉 **https://zhaoyuda.github.io/monster-builder/**

把这个链接存到手机,刷新就是最新版。

---

## ✏️ 给设计师 Akun

完整的傻瓜上手指南(注册、加协作者、改字、改表格的偷懒法、Markdown 小抄)在这里:

👉 **[给 Akun 的改文档指南](design/给Akun的改文档指南.md)**(网站上也能看到这一页)

一句话流程:打开 `design/` 里要改的文件 → 点右上角铅笔 ✏️ → 改 → 拉到底点绿色「Commit changes」→ 等 1-2 分钟刷新网站就是最新版。

设计文件分工:

| 文件 | 管什么 |
|---|---|
| [`index.md`](design/index.md) | 总览 / 系统地图 / MVP |
| [`01-assembly.md`](design/01-assembly.md) | 系统A · 装配(零件表) |
| [`02-combat.md`](design/02-combat.md) | 系统B · 战斗(战斗手册) |
| [`03-pve.md`](design/03-pve.md) | 系统C · PVE |
| [`04-pvp.md`](design/04-pvp.md) | 系统D · PVP |
| [`05-open-questions.md`](design/05-open-questions.md) | 待确认问题(Akun 在这里回填决定) |

---

## 🛠 给开发者

- **文档源文件**:`design/*.md`
- **构建配置**:`mkdocs.yml`(Material 主题,docs 目录指向 `design/`)
- **CI/CD**:`.github/workflows/deploy-docs.yml`,push 到 `main` 后自动 `mkdocs build` 并发布到 GitHub Pages
- **原始设定稿存档**:`design/_source/`(docx 原件,作引用归档;正式内容以 `design/*.md` 为准)

本地预览:

```bash
python3 -m pip install mkdocs-material
mkdocs serve   # 打开 http://127.0.0.1:8000
```

> ⚙️ 首次部署:仓库 **Settings → Pages → Source** 选 **「GitHub Actions」**。
