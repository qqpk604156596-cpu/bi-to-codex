# MySQL schema profile

- Status: **observed**
- Generated at: 2026-07-14T02:25:41.907717+00:00
- Source table: `enterprise_sales.online_retail_raw`

| Column | Type | Nullable |
|---|---|---|
| SourceRowId | bigint | NO |
| SourceSheet | varchar(64) | NO |
| InvoiceNo | varchar(32) | NO |
| StockCode | varchar(64) | NO |
| DescriptionText | varchar(512) | YES |
| Quantity | int | NO |
| InvoiceDate | datetime | NO |
| UnitPrice | decimal(18,4) | NO |
| CustomerID | varchar(64) | YES |
| Country | varchar(128) | NO |
| IsCancellation | tinyint(1) | NO |
| UnknownCustomer | tinyint(1) | NO |
| ZeroPrice | tinyint(1) | NO |
