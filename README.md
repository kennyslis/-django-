# IntelliJ IDEA 可直接导入运行的完整工程

本仓库已整理为可直接在 IntelliJ IDEA 使用的全栈工程，包含：

- `backend/`：Maven + Spring Boot 3（Java 17）
- `frontend/`：Vite 前端工程（Node.js 20）
- `docker-compose.yml`：一键启动 mysql / backend / frontend / nginx
- `.env.example`：Docker 环境变量模板

---

## 1. 工程目录结构

```text
project-root/
  backend/
  frontend/
  docker-compose.yml
  .env.example
  README.md
```

---

## 2. 后端（Spring Boot）说明

### 2.1 关键点

- Maven 工程：`backend/pom.xml`
- Java 版本：17
- Spring Boot 主类：`backend/src/main/java/com/example/project/Application.java`
- 配置文件：
  - `backend/src/main/resources/application.yml`
  - `backend/src/main/resources/application-dev.yml`
- 健康接口：`GET /health`
- 全局异常处理：`GlobalExceptionHandler`
- 数据库迁移：Flyway（`backend/src/main/resources/db/migration`）

### 2.2 IntelliJ IDEA 打开 backend

1. 打开 IntelliJ IDEA。
2. 选择 **Open**，定位到仓库中的 `backend` 目录并打开。
3. IDEA 会自动识别 Maven 项目；若未自动加载，打开 Maven 工具窗口点击 **Reload All Maven Projects**。
4. 在 **Project Structure > Project SDK** 设置为 **JDK 17**。
5. 在 `Application.java` 上点击绿色运行按钮启动。

### 2.3 本地运行 backend（命令行）

```bash
cd backend
mvn clean install
mvn spring-boot:run
```

默认端口为 `8080`，访问：

- `http://localhost:8080/health`

---

## 3. 前端（Vite）说明

### 3.1 关键点

- 包管理文件：`frontend/package.json`
- Vite 配置：`frontend/vite.config.js`
- Axios 基础地址：`frontend/src/api/http.js`
  - 默认 `baseURL=/api`
- 开发代理：Vite 将 `/api` 代理到后端（默认 `http://localhost:8080`）

### 3.2 IntelliJ IDEA 打开 frontend

1. 在 IDEA 中选择 **Open**，打开 `frontend` 目录（或在同一窗口以模块形式加载）。
2. 打开 Terminal，执行：

```bash
cd frontend
npm install
npm run dev
```

3. 启动后访问：`http://localhost:5173`

---

## 4. 数据库与环境初始化

### 4.1 MySQL 初始化脚本

- 脚本路径：`docker/mysql/init/001_init.sql`
- 作用：初始化 `assignment_system` 数据库。

### 4.2 Spring Boot 默认本地开发配置

- 默认读取以下环境变量（可不设置，使用默认值）：
  - `DB_HOST`（默认 `localhost`）
  - `DB_PORT`（默认 `3306`）
  - `DB_NAME`（默认 `assignment_system`）
  - `DB_USERNAME`（默认 `root`）
  - `DB_PASSWORD`（默认 `root`）

### 4.3 Docker 环境变量示例

1. 复制环境变量模板：

```bash
cp .env.example .env
```

2. 根据实际情况修改 `.env`。

### 4.4 数据表或迁移配置

- 使用 Flyway 自动迁移。
- 首个迁移文件：`backend/src/main/resources/db/migration/V1__init_schema.sql`

---

## 5. Docker Compose 一键启动整套系统

### 5.1 启动步骤

```bash
cp .env.example .env
docker compose up --build
```

启动后服务：

- mysql：`localhost:3306`
- backend：`localhost:8080`
- frontend：`localhost:5173`
- nginx 统一入口：`localhost:80`

Nginx 路由：

- `/` -> frontend
- `/api/*` -> backend

### 5.2 健康检查

```bash
curl http://localhost/health
```

或

```bash
curl http://localhost:8080/health
```

---

## 6. 推荐启动顺序（本地开发）

1. 启动 MySQL（本机或 Docker）。
2. 启动 backend（`mvn spring-boot:run`）。
3. 启动 frontend（`npm run dev`）。
4. 访问前端页面验证接口调用。

---

## 7. 验证步骤（验收清单）

1. **后端可运行**
   - `cd backend && mvn clean install` 成功。
   - IDEA 中可直接运行 `Application.java`。
   - `GET /health` 返回 `{"status":"UP"}`。

2. **前端可运行**
   - `cd frontend && npm install` 成功。
   - `npm run dev` 成功并可访问页面。

3. **Docker 全链路可运行**
   - `docker compose up --build` 可拉起 mysql/backend/frontend/nginx。
   - `http://localhost` 可访问前端。
   - `http://localhost/health` 可访问后端健康检查。

---

## 8. 说明

本次仅做工程化整理和可运行性修复，不新增业务功能。
