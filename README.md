# 京师词汇量测评工具

基于北京师范大学词汇体系的英语词汇量测评 Web 应用。

## 功能特性

- **三级词库**：小学（505词）、初中（1110词）、高中（1866词）
- **两种算法**：
  - IRT 自适应算法（项目反应理论，更精准）
  - 二分搜索算法（速度更快）
- **匿名测评**：无需注册即可测试
- **用户系统**：注册登录，保存历史记录
- **学习模式**：基于 SM-2 算法的间隔重复记忆
- **管理后台**：用户管理、词库管理、测评记录查看

## 快速启动

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
python app.py
```

访问 http://localhost:5000

默认管理员账号：`admin` / `admin123`

## 技术栈

- **后端**：Python Flask + SQLAlchemy + SQLite
- **前端**：原生 HTML/CSS/JavaScript（无需构建工具）
- **算法**：IRT 2PL 自适应测评 + SM-2 间隔重复

## 项目结构

```
vocab-app/
├── app.py              # 主应用入口
├── models.py           # 数据库模型
├── routes/
│   ├── auth.py         # 认证接口
│   ├── assessment.py   # 测评接口（含IRT算法）
│   ├── admin.py        # 管理员接口
│   ├── wordbank.py     # 词库接口
│   └── user.py         # 用户接口（学习记录）
├── static/
│   ├── index.html      # 单页应用入口
│   ├── css/style.css   # 样式
│   ├── js/app.js       # 前端逻辑
│   └── data/           # 词库JSON（小学/初中/高中）
└── requirements.txt
```
