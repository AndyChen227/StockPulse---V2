# Test suite / 测试套件

[English](#english) · [简体中文](#简体中文)

## English

Tests are grouped by product boundary, not implementation detail. Use
`test_<area>.py` for the corresponding module or cross-module contract.
PostgreSQL integration tests require the CI service and are intentionally
skipped when no test database URL is available locally. Container and
deployment tests protect files outside the Python package.

`test_repository_layout.py` additionally protects the organized root layout,
the product README, grouped configuration/container paths, the English-first
bilingual documentation contract, documentation categories, and every relative
Markdown link.

Run the local suite from the repository root:

```powershell
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

### Verified V1 baseline

On 2026-08-21, `python -m unittest discover -s tests -v` ran 145 tests:
137 passed and 8 PostgreSQL integration tests were skipped locally as designed.
`python -m compileall -q src tests` also completed successfully. CI supplies
PostgreSQL 17 for the skipped integration cases and additionally builds and
smoke-tests both production containers.

---

## 简体中文

测试按照产品边界而不是内部实现细节分组。对应模块或跨模块契约使用
`test_<领域>.py`。PostgreSQL 集成测试依赖 CI 数据库；本地没有测试数据库 URL
时会按设计跳过。容器和部署测试用于保护 Python 包之外的文件。

`test_repository_layout.py` 还会保护整理后的根目录、产品 README、分类配置与
容器路径、“英文在前、中文在后”的双语文档契约、文档分类，以及所有相对
Markdown 链接。

请在仓库根目录运行：

```powershell
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

### V1 验证基线

2026-08-21 的本地基线共运行 145 项测试：137 项通过，8 项 PostgreSQL
集成测试按设计在本地跳过；`src` 与 `tests` 的字节码编译检查也成功完成。
CI 会为这 8 项集成测试提供 PostgreSQL 17，并额外构建和冒烟测试两个生产镜像。
