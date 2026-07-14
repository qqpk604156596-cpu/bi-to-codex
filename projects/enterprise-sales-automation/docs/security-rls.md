# 动态RLS设计与验收

## 1. 目的与边界

动态RLS设计用于规定 Power BI Desktop 模型应如何根据用户—国家映射限制数据。映射是公开数据练习中的模拟配置，不代表真实客户组织、账号或授权；已在本地 Desktop Analysis Services 中完成自动化验证。

Service中的真实用户身份、工作区权限、共享方式和网关未验证，不属于当前质量门。

## 2. 安全模型

- 安全表：**SecurityUserCountry**。
- 最低字段：
  - **UserPrincipalName**：模拟用户标识；
  - **Country**：获准国家；
  - **IsActive**：是否启用。
- 关系：SecurityUserCountry通过Country过滤DimCountry，再传播到FactSalesLine。SecurityUserCountry ↔ DimCountry 这一条安全桥关系在 Desktop 中使用 `Both`，并勾选 **Apply security filter in both directions**；其他维度—事实关系保持单向。
- 角色：**CountryManager**。
- 角色逻辑：只保留IsActive为true且UserPrincipalName等于USERPRINCIPALNAME()的映射行。

一个用户可以映射多个国家；一个国家也可以映射多个用户。未配置用户默认看不到受保护事实数据，不提供隐式全局访问。

## 3. 模拟测试用户

使用保留的 **example.invalid** 域，避免与真实账号混淆：

| 用户 | 获准范围 | 用途 |
|---|---|---|
| manager.uk@example.invalid | United Kingdom | 大范围国家测试 |
| manager.fr@example.invalid | France | 小范围国家测试 |
| unmapped.manager@example.invalid | 无 | 默认拒绝测试 |

实际映射在 `src/sql/030_security_user_country.sql` 中以模拟账户生成，不将真实邮箱写入公开仓库。`unmapped.manager@example.invalid` 故意没有映射行；禁用用户场景留待实际 Desktop RLS 测试时以临时模拟行验证。

## 4. 验收场景

1. 无RLS基线：记录全部国家、行数和Net Sales。
2. UK用户：只返回United Kingdom，数值与DuckDB/SQL国家基线一致。
3. France用户：只返回France，数值与独立基线一致。
4. 禁用用户：返回0行或批准的空状态。
5. 未映射用户：返回0行或批准的空状态。
6. 页面筛选：用户不能通过清除筛选器或跨页导航访问其他国家。
7. 明细导出：只包含当前用户获准范围。

每个场景保存DAX查询结果和至少一张经过检查的Desktop截图。

当前状态：本地自动化验证已使用当前运行时身份的临时内存映射完成 UK、France 与未映射三种场景；UK 和 France 的 `Net Sales` 分别与 DuckDB 国家基线一致，未映射状态返回空值。原始安全表分区在 `finally` 中恢复，证据不保存本机身份明文。见 [`../evidence/rls/desktop-rls-validation.json`](../evidence/rls/desktop-rls-validation.json) 与 [`../evidence/metrics/rls-country-baseline.json`](../evidence/metrics/rls-country-baseline.json)。

该证据仅覆盖 Desktop 本地运行时身份模拟；Power BI Service、Entra、真实用户、共享、网关及多用户权限仍未验证。

## 5. 失败条件

- 用户能看到未映射国家；
- 空映射或禁用用户获得全局访问；
- RLS总计与独立国家基线不一致；
- 页面筛选或关系方向绕过安全表；
- 测试只验证视觉隐藏，没有验证模型返回结果；
- 对外文档把模拟RLS描述成真实客户权限。

任一失败将RLS质量门置为 **failed** 并阻断交付。

## 6. 后续Service质量门

进入L2前必须在实际Power BI Service环境重新验证：

- Entra用户身份与USERPRINCIPALNAME()；
- 工作区角色与RLS相互作用；
- 共享、App和Build权限；
- 网关凭据和刷新；
- 至少两个真实测试账号；
- 权限变更、撤销和审计证据。
