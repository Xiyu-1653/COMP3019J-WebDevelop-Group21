# 借阅与归还 demo

在仓库根目录运行。使用已有 Python 环境和 MySQL 8，页面使用馆员 librarian 和 Clean Code 的实体副本 KB-0001。

## 首次准备

在 PowerShell 执行以下命令，安装项目依赖。

```powershell
python -m pip install -r requirements.txt
```

先确定要使用的数据库。如果已经有组长提供的数据库地址，且其中已导入项目样本，可以直接配置连接并启动。

如果需要本机测试库，在 MySQL 客户端中新建数据库。以本机 root 账号、3306 端口为例，在仓库根目录执行下面命令，输入自己的 MySQL 密码。

```powershell
& "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -h 127.0.0.1 -P 3306 -u root -p
```

在 MySQL 提示符逐条执行，确认建库成功后再导入。导入脚本包含删表操作，请只在新建的测试库执行。

```sql
CREATE DATABASE knowbook_c_demo CHARACTER SET utf8mb4;
USE knowbook_c_demo;
SOURCE database/01_schema.sql
SOURCE database/02_seed.sql
EXIT
```

## 配置连接并启动

仍在仓库根目录的 PowerShell 中执行。凭据窗口中填写自己的 MySQL 用户名和密码。运行后保持终端打开。

```powershell
$credential = Get-Credential -UserName root -Message "请输入本机 MySQL 凭据"
$env:DB_HOST = "127.0.0.1"
$env:DB_PORT = "3306"
$env:DB_USER = $credential.UserName
$env:DB_PASSWORD = $credential.GetNetworkCredential().Password
$env:DB_NAME = "knowbook_c_demo"
python -m flask --app borrow_return.app run --port 5081
```

也可以复制仓库的 .env.example 为 .env，配置 DATABASE_URL。应用和数据库初始化脚本使用同一个 URL。URL 中的用户名和密码如果含有 @、#、% 等字符，需要进行 URL 编码。DATABASE_URL 配置优先于上面的 DB_* 环境变量。

打开 [借还页面](http://127.0.0.1:5081/)。按 Ctrl+C 停止服务。退出 PowerShell 后，当前会话设置的环境变量会结束。

## 演示步骤

1. 选 alice 并点击「借出」。副本变为 borrowed，新增借阅记录，到期时间为借出后 14 天。
2. 刷新页面，确认借阅记录仍然存在。
3. 点击「归还」。副本恢复 available，记录显示归还时间。
4. 选 bob 并点击「借出」。页面显示逾期提示，副本和借阅记录保持原样。

样本里 Alice 的原有借阅在 2026 年 11 月 15 日到期。超过该日期后，需要先处理她的逾期记录，或者在 2026 年 12 月 19 日前使用 carol 验证成功路径。Carol 的新借阅期限为 60 天。

借出操作会检查副本状态、逾期、未缴费用和按书目计算的借阅上限。loan 和 copy 的修改在同一个事务中提交。存在等待预约时，demo 会拒绝办理该副本的归还。登录、续借、费用生成和预约分配需要继续开发。

## 本地文件清理

源码、模板和数据库 SQL 是项目文件，继续保留。__pycache__ 和 .pyc 文件是 Python 缓存，可以删除。若自己创建了专用的 .venv，确认不再使用后可以删除。

.env 可能包含数据库密码，已由仓库 .gitignore 排除，请保留在本机。
