# EvoPlay 服务器使用指南

服务器：`ubuntu@129.80.245.31` （Oracle Cloud）
访问网址：http://129.80.245.31

一般只需要做两件事：**下载日志** 和 **更新部署**。下面是具体步骤。

---

## 0. 一次性准备

### 0.1 把你的私钥放好
拿到对应你那把公钥（`guoyingying01021@gmail.com`）的**私钥文件**，放到一个固定位置，比如：

```bash
~/.ssh/oracle-evoplay.key
```

设置权限（**必须 600，不然 ssh 会拒绝**）：

```bash
chmod 600 ~/.ssh/oracle-evoplay.key
```

> 之后所有命令里看到 `~/.ssh/oracle-evoplay.key` 的位置，换成你实际的路径。

### 0.2 测试连接
```bash
ssh -i ~/.ssh/oracle-evoplay.key ubuntu@129.80.245.31 "echo hi && hostname"
```
能打印出 `hi` 和 `instance-...` 就说明连接 OK。

---

## 1. 下载服务器上的游戏日志

服务器把所有玩家产生的游戏 CSV 存在 `/home/ubuntu/evoplay-data/logs/`。结构：

```
logs/<game_name>/<player_name>/<session_id>_rN.csv
```

把整个 logs 目录拉到本地：

```bash
scp -i ~/.ssh/oracle-evoplay.key -r \
    ubuntu@129.80.245.31:/home/ubuntu/evoplay-data/logs \
    /Users/<your_name>/Desktop/evoplay_related/server_logs
```

只想下载某个游戏 / 某个玩家的：

```bash
# 只要 fourinarow
scp -i ~/.ssh/oracle-evoplay.key -r \
    ubuntu@129.80.245.31:/home/ubuntu/evoplay-data/logs/fourinarow \
    /Users/<your_name>/Desktop/evoplay_related/server_logs/

# 只要某个玩家的所有游戏
scp -i ~/.ssh/oracle-evoplay.key -r \
    'ubuntu@129.80.245.31:/home/ubuntu/evoplay-data/logs/*/Yuzu' \
    /Users/<your_name>/Desktop/evoplay_related/server_logs/
```

> 如果只想增量同步（不下载已经存在的文件），用 `rsync` 更省事：
> ```bash
> rsync -avz -e "ssh -i ~/.ssh/oracle-evoplay.key" \
>     ubuntu@129.80.245.31:/home/ubuntu/evoplay-data/logs/ \
>     /Users/<your_name>/Desktop/evoplay_related/server_logs/
> ```

---

## 2. 把当前的 GitHub 库部署到服务器

部署 = 把代码 rsync 上去 → 在服务器上 build Docker 镜像 → 重启容器。

### 2.1 克隆并切到要部署的分支
```bash
git clone https://github.com/JasonGUTU/EvoPlay.git
cd EvoPlay
# 切到目标分支
git checkout feat/new-games-and-ui     # 或 main
git pull
```

### 2.2 改 `deploy.sh` 里的 KEY 路径
打开 `deploy.sh`，把第 6 行：

```bash
KEY="/Users/shaoshao/Desktop/ssh-key-2026-03-29.key"
```

改成你自己的路径：

```bash
KEY="$HOME/.ssh/oracle-evoplay.key"
```

> 这一改是本地的，**不要 commit 推回去**（不然下次别人 pull 就拿到你的 key 路径了）。可以临时 stash 或者改完别 push。

### 2.3 跑部署
```bash
./deploy.sh
```

部署做的事：
1. `rsync` 当前目录到服务器 `/home/ubuntu/EvoPlay/`（自动排除 `.git`、`node_modules`、`evolution_logs`、`human_data`、各种日志）
2. 在服务器上 `docker build`（前端 + 后端打成一个镜像）
3. 停掉旧容器，跑新的
4. 把 logs / players.json 的卷挂载到 `/home/ubuntu/evoplay-data/`（数据不会因为重建镜像而丢）

成功完成会打印：
```
=== Deploy complete ===
<hash>   evoplay   "python backend/app.…"   ...   0.0.0.0:80->5001/tcp   evoplay
=== Access at: http://129.80.245.31 ===
```

打开 http://129.80.245.31 验证一下页面。

---
