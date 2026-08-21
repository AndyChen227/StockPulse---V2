# Test suite / 测试套件

**English:** Tests are grouped by product boundary, not by implementation detail. Use `test_<area>.py` for the corresponding module or cross-module contract. PostgreSQL integration tests require the CI service and are intentionally skipped when no test database URL is available locally. Container and deployment tests protect files outside the Python package.

**中文：** 测试按照产品边界而不是内部实现细节分组。对应模块或跨模块契约使用 `test_<领域>.py`。PostgreSQL 集成测试依赖 CI 数据库；本地没有测试数据库 URL 时会按设计跳过。容器和部署测试用于保护 Python 包之外的文件。

`test_repository_layout.py` additionally protects the organized root layout,
the real product README, grouped configuration/container paths, documentation
categories, and every relative Markdown link. `test_repository_layout.py`
还会保护整理后的根目录、真正的产品 README、分类配置与容器路径、
文档分类，以及所有相对 Markdown 链接。

Run the local suite from the repository root with
`python -m unittest discover -s tests -v`.

请在仓库根目录运行 `python -m unittest discover -s tests -v` 执行本地测试。

## Verified V1 baseline / V1 验证基线

On 2026-08-21, `python -m unittest discover -s tests -v` ran 144 tests:
136 passed and 8 PostgreSQL integration tests were skipped locally as designed.
`python -m compileall -q src tests` also completed successfully. CI supplies
PostgreSQL 17 for the skipped integration cases and additionally builds and
smoke-tests both production containers.

2026-08-21 的本地基线共运行 144 项测试：136 项通过，8 项 PostgreSQL
集成测试按设计在本地跳过；`src` 与 `tests` 的字节码编译检查也成功完成。
CI 会为这 8 项集成测试提供 PostgreSQL 17，并额外构建和冒烟测试两个生产镜像。
