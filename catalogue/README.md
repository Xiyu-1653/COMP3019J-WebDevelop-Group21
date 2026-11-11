# Catalogue 模块（阶段 1：数据库与后端基础）

Catalogue 负责展示图书馆的图书（Title）和实体副本（Copy）。本阶段先搭建后端基础：复用现有 MySQL 数据库连接，建立查询函数和 Flask 路由。

## 现状（数据库无需改动）

- 数据库表 `title` 和 `copy` 已在 `database/01_schema.sql` 中定义，含一对多外键、主键、唯一约束和六种副本状态，本阶段直接复用，未做任何修改。
- 样本数据 `database/02_seed.sql` 已包含 8 本图书、17 个副本，覆盖全部六种状态。

## 新增内容

| 文件 | 说明 |
|------|------|
| `common/db.py` | 共享的 MySQL 连接函数 `connect()`，从 `borrow_return/app.py` 抽出，供各模块复用 |
| `catalogue/queries.py` | 图书/副本查询函数 |
| `catalogue/app.py` | Catalogue Flask 后端路由 |
| `catalogue/templates/catalogue.html` | 图书列表页（最小实现） |
| `catalogue/templates/title.html` | 图书详情与副本页（最小实现） |
| `tests/test_catalogue.py` | 数据库连接、查询、外键关系测试 |

## 查询函数

- `get_all_titles(cursor)`：获取全部图书（含可借数/副本总数），按新增时间倒序。
- `get_title(cursor, title_id)`：按 title_id 获取一本图书。
- `get_copies_for_title(cursor, title_id)`：按 title_id 获取全部副本。
- `count_available_copies(cursor, title_id)`：统计可借副本数（仅 `available` 计入）。
- `count_titles(cursor)`：获取图书总数。

所有查询函数接收调用方传入的 `cursor`，不自行开关连接，与 `reservation_management` 模块的约定一致。

## 运行

在仓库根目录，先按根目录 README 配置数据库，然后：

```powershell
python -m flask --app catalogue.app run --port 5082
```

打开 http://127.0.0.1:5082/。

## 测试

```powershell
python -m unittest discover -s tests -v
```

测试需要可访问的 MySQL 数据库。
