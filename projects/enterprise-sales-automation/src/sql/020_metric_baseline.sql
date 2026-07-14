-- MySQL 8.0 metric baseline template. The Python runner executes this same logic
-- with the three approved slices and writes only aggregate evidence.

SELECT
    COALESCE(SUM(CASE WHEN `IsCancellation` = 0 AND `Quantity` > 0 AND `UnitPrice` > 0 THEN `LineAmount` ELSE 0 END), 0) AS `gross_sales`,
    COALESCE(SUM(CASE WHEN `IsCancellation` = 1 THEN ABS(`LineAmount`) ELSE 0 END), 0) AS `cancelled_sales`,
    COALESCE(SUM(`LineAmount`), 0) AS `net_sales`,
    COUNT(DISTINCT CASE WHEN `IsCancellation` = 0 AND `Quantity` > 0 AND `UnitPrice` > 0 THEN `InvoiceNo` END) AS `order_count`,
    COALESCE(SUM(CASE WHEN `IsCancellation` = 0 AND `Quantity` > 0 AND `UnitPrice` > 0 THEN `Quantity` ELSE 0 END), 0) AS `units_sold`,
    COUNT(DISTINCT CASE WHEN `IsCancellation` = 0 AND `Quantity` > 0 AND `UnitPrice` > 0 AND NULLIF(TRIM(`CustomerID`), '') IS NOT NULL THEN `CustomerID` END) AS `active_customers`,
    COUNT(DISTINCT CASE WHEN `IsCancellation` = 1 THEN `InvoiceNo` END) AS `cancelled_invoice_count`,
    COUNT(DISTINCT NULLIF(TRIM(`InvoiceNo`), '')) AS `all_invoice_count`
FROM `vw_fact_sales_line`;
