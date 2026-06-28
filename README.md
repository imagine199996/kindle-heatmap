# Kindle 股票热力图

用 Kindle 墨水屏显示 FinViz Nasdaq-100 盘后热力图。

## 部署步骤

### 1. Fork 本仓库
点击右上角 **Fork** 按钮，复制到你的 GitHub 账号下。

### 2. 开启 GitHub Pages
进入你 Fork 后的仓库：
- Settings → Pages
- Source 选择 **Deploy from a branch**
- Branch 选择 `main`，目录选择 `/docs`
- 点击 Save

等约 1 分钟后，你会得到一个类似这样的网址：
```
https://你的用户名.github.io/kindle-heatmap/
```

### 3. 开启 Actions 权限
- Settings → Actions → General
- 找到 **Workflow permissions**，选择 **Read and write permissions**
- 点击 Save

### 4. 手动触发第一次运行
- 点击仓库顶部的 **Actions** 标签
- 找到 **Update Kindle Heatmap**
- 点击 **Run workflow** 手动运行一次

等待约 2 分钟，完成后刷新 GitHub Pages 网址即可看到热力图。

### 5. Kindle 访问
在 Kindle 上打开实验性浏览器：
- 点击顶部搜索栏
- 输入你的 GitHub Pages 网址
- 收藏书签方便下次访问

页面会**每小时自动刷新**一次（通过 meta refresh）。

## 自动更新时间

GitHub Actions 会在以下时间自动运行（北京时间）：
- 夏令时（3月-11月）：**次日 06:30**
- 冬令时（11月-3月）：**次日 07:30**

即美东时间收盘后约 1 小时更新。

## 文件说明

| 文件 | 说明 |
|------|------|
| `scripts/capture_heatmap.py` | 截图 + 灰度转换脚本 |
| `.github/workflows/update_heatmap.yml` | 定时任务配置 |
| `docs/index.html` | Kindle 访问的网页 |
| `docs/heatmap.png` | 生成的热力图（自动更新） |
