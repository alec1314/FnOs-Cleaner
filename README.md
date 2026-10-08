# 🧹 fnos-cleaner

飞牛 NAS（fnOS）垃圾清理工具——Docker 容器形态，带 Web 面板。

**核心原则：宁可少删，不可删错。** 默认 dry-run，所有删除操作都有多重安全检查。

## 功能

### 📊 综合分析
- **磁盘占用地图**：遍历 fnOS 标准目录，显示每个路径占多少空间、什么分类
- **Docker 状态**：列出运行中/已停止容器、镜像、卷、网络的使用情况
- **孤儿目录检测**：扫描 `/vol1/1000/docker/` 下的残留目录（删了容器没删数据）

### 🧹 清理模块
| 模块 | 清理内容 | 安全级别 |
|---|---|---|
| 🐳 Docker | 悬空镜像 `<none>:<none>`、未使用网络 | 安全可自动删 |
| ⬇️ 下载残留 | `.!qB`、`.unwanted`、`.part` 等临时文件 | 安全可自动删 |
| 🗑 回收站 | 回收站旧文件、rotated 日志 `.gz` | 只报告，手动确认 |
| 🎬 媒体缓存 | 缩略图缓存（需确认路径后开启） | 只报告，手动确认 |

## 快速开始

### 1. 复制配置
```bash
cp config.example.yaml config.yaml
```

### 2. 修改 docker-compose.yml
确认挂载路径和你 NAS 实际一致：
```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
  - /vol1:/host/vol1:ro
```

> `:ro` 只读挂载用于扫描。需要删文件时改成 `:rw`。

### 3. 启动
```bash
docker compose up -d --build
```

访问 `http://<NAS-IP>:7878`

## 使用流程

1. **先分析**：点「🔬 开始分析」，看磁盘地图和 Docker 状态
2. **再扫描**：点「🔍 扫描」，列出可清理项
3. **预览**：点「👁 预览清理」，确认将释放多少空间（不删任何东西）
4. **执行**：确认无误后点「🗑 执行清理」，浏览器二次确认后才真删

## 安全设计

### 三重文件删除检查
1. **保护路径列表**：`/usr/local/apps`、`/etc/docker`、`/var/apps` 等直接跳过
2. **普通文件验证**：目录、符号链接一律跳过
3. **挂载范围验证**：只删 `/host/` 下的文件

### Docker 安全
- 运行中容器**绝对不碰**（删除前二次确认 status）
- 停止容器只报告，不自动删
- 悬空卷只报告，不自动删（卷里可能有数据）
- 镜像删除不用 `force=True`

### 其他保护
- 单文件超过 10GB 自动跳过
- 默认 dry-run 模式
- 每次操作写报告，可回溯

## 项目结构

```
fnos-cleaner/
├── Dockerfile
├── docker-compose.yml
├── config.example.yaml
├── requirements.txt
├── README.md
├── app/
│   ├── main.py                 # Flask 入口 + API
│   ├── config.py               # YAML 配置加载
│   ├── models.py               # SQLite 数据模型
│   ├── cleaner.py              # 清理执行器（带安全检查）
│   ├── scheduler.py             # APScheduler 定时任务
│   ├── filesystem_map.py       # fnOS 固定目录基线地图
│   ├── analyzer.py              # 综合分析器
│   ├── scanner/
│   │   ├── base.py
│   │   ├── docker_prune.py
│   │   ├── download_residue.py
│   │   ├── trash_log.py
│   │   └── media_cache.py
│   └── web/
│       ├── templates/
│       │   ├── base.html
│       │   └── dashboard.html
│       └── static/
│           ├── style.css
│           └── app.js
├── data/                       # SQLite 持久化（自动生成）
└── reports/                    # 清理报告
```

## API

| 接口 | 方法 | 说明 |
|---|---|---|
| `/api/analyze` | GET | 综合分析（磁盘+Docker+孤儿目录） |
| `/api/scan` | POST | 扫描可清理项 |
| `/api/cleanup` | POST | 执行清理（dry_run 参数控制） |
| `/api/runs` | GET | 清理历史记录 |

## 技术栈

- Python 3.12 + Flask + Gunicorn
- APScheduler（定时）
- docker SDK
- 原生 HTML/CSS/JS（无构建步骤）
- SQLite

## 路径确认提示

以下路径需要你在实际 NAS 上跑一次分析后确认：
- `.thumbnail` 缩略图缓存位置
- `@recycle` 回收站位置
- `.fnos/media-cache` 影视缓存位置

**第一次使用建议全程 dry-run，确认报告里的路径都正确后再开自动清理。**

## License

MIT
