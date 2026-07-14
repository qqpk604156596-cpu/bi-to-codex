-- Run while connected to the database named by MYSQL_DATABASE.
-- The raw table is intentionally retained unchanged as the import audit source.

CREATE OR REPLACE VIEW `vw_fact_sales_line` AS
SELECT
    `SourceRowId`,
    `InvoiceNo`,
    `StockCode`,
    `DescriptionText` AS `Description`,
    `Quantity`,
    `InvoiceDate`,
    `UnitPrice`,
    `CustomerID`,
    TRIM(`Country`) AS `Country`,
    `IsCancellation`,
    `UnknownCustomer`,
    `ZeroPrice`,
    CAST(`Quantity` * `UnitPrice` AS DECIMAL(20,4)) AS `LineAmount`
FROM `online_retail_raw`;

-- Dimension views enforce the one-side key uniqueness required by the Power BI star schema.
-- They are derived only from the approved fact view and contain no customer credentials.

CREATE OR REPLACE VIEW `vw_dim_date` AS
SELECT DISTINCT
    DATE(`InvoiceDate`) AS `Date`
FROM `vw_fact_sales_line`;

CREATE OR REPLACE VIEW `vw_dim_product` AS
SELECT
    `StockCode`,
    MAX(`Description`) AS `Description`
FROM `vw_fact_sales_line`
GROUP BY `StockCode`;

CREATE OR REPLACE VIEW `vw_dim_customer` AS
SELECT
    COALESCE(`CustomerID`, 'UNKNOWN') AS `CustomerKey`,
    MAX(`CustomerID`) AS `CustomerID`,
    MAX(`UnknownCustomer`) AS `IsUnknownCustomer`
FROM `vw_fact_sales_line`
GROUP BY COALESCE(`CustomerID`, 'UNKNOWN');

CREATE OR REPLACE VIEW `vw_dim_country` AS
SELECT DISTINCT
    `Country`
FROM `vw_fact_sales_line`;
