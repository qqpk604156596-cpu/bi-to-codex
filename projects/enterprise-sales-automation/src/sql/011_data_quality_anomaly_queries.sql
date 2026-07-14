-- Read-only anomaly checks. Run while connected to MYSQL_DATABASE.
-- Results are evidence for review, not automatic deletion instructions.

SELECT 'source_row_count' AS `check_name`, COUNT(*) AS `observed_value`
FROM `vw_fact_sales_line`;

SELECT 'duplicate_source_row_id' AS `check_name`, COUNT(*) AS `observed_value`
FROM (
    SELECT `SourceRowId`
    FROM `vw_fact_sales_line`
    GROUP BY `SourceRowId`
    HAVING COUNT(*) > 1
) AS `duplicates`;

SELECT 'required_field_missing' AS `check_name`, COUNT(*) AS `observed_value`
FROM `vw_fact_sales_line`
WHERE `InvoiceNo` IS NULL OR TRIM(`InvoiceNo`) = ''
   OR `StockCode` IS NULL OR TRIM(`StockCode`) = ''
   OR `Quantity` IS NULL
   OR `InvoiceDate` IS NULL
   OR `UnitPrice` IS NULL
   OR `Country` IS NULL OR TRIM(`Country`) = '';

SELECT 'zero_price_line' AS `check_name`, COUNT(*) AS `observed_value`
FROM `vw_fact_sales_line`
WHERE `ZeroPrice` = 1;

SELECT 'unknown_customer_line' AS `check_name`, COUNT(*) AS `observed_value`
FROM `vw_fact_sales_line`
WHERE `UnknownCustomer` = 1;

SELECT 'cancellation_prefix_mismatch' AS `check_name`, COUNT(*) AS `observed_value`
FROM `vw_fact_sales_line`
WHERE (`InvoiceNo` LIKE 'C%' AND `IsCancellation` <> 1)
   OR (`InvoiceNo` NOT LIKE 'C%' AND `IsCancellation` <> 0);
