# monster-builder

「手搓一个大怪兽」的**设计文档仓库**。一个业余做的小游戏:造怪兽、装配部件、自动对战。

本仓库目前只放**设计文档**,不含游戏代码。文档用 [MkDocs Material](https://squidfunk.github.io/mkdocs-material/) 构建,每次提交后由 GitHub Actions 自动发布成一个手机也能舒服阅读的 wiki 网站。

## 📖 在线 wiki

👉 **https://zhaoyuda.github.io/monster-builder/**

把这个链接存到手机,刷新就是最新版。

---

## ✏️ 给设计师 Akun:怎么改文档(不用装任何东西)

全程在浏览器里完成,不碰命令行、不碰代码。

1. 打开 [`design/`](design/) 文件夹,点开你要改的那个文件:
   - [`index.md`](design/index.md) — 总览 / 系统地图
   - [`01-assembly.md`](design/01-assembly.md) — 系统A · 装配
   - [`02-combat.md`](design/02-combat.md) — 系统B · 战斗
   - [`03-pve.md`](design/03-pve.md) — 系统C · PVE
   - [`04-pvp.md`](design/04-pvp.md) — 系统D · PVP
2. 点文件右上角的**铅笔图标 ✏️**(Edit this file)。
3. 直接在网页里改文字。
4. 拉到页面最下方,点绿色按钮 **「Commit changes」**(再点一次确认)。
5. 等一两分钟,刷新上面的 wiki 链接,就能看到最新版了。

> 改错了也不要紧——每次提交都有历史记录,随时能找回旧版本。

### Markdown 小抄

| 想要的效果 | 这样写 |
|---|---|
| 大标题 | `# 标题` |
| 小标题 | `## 小标题` |
| **加粗** | `**加粗**` |
| 列表 | 每行开头写 `- ` |
| 表格 | 见现有文件里的写法,照着改最省事 |

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
