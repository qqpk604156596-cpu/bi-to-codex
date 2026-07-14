CREATE DATABASE IF NOT EXISTS enterprise_sales
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

USE enterprise_sales;

CREATE TABLE IF NOT EXISTS online_retail_raw (
    SourceRowId BIGINT NOT NULL PRIMARY KEY,
    SourceSheet VARCHAR(64) NOT NULL,
    InvoiceNo VARCHAR(32) NOT NULL,
    StockCode VARCHAR(64) NOT NULL,
    DescriptionText VARCHAR(512) NULL,
    Quantity INT NOT NULL,
    InvoiceDate DATETIME NOT NULL,
    UnitPrice DECIMAL(18, 4) NOT NULL,
    CustomerID VARCHAR(64) NULL,
    Country VARCHAR(128) NOT NULL,
    IsCancellation BOOLEAN NOT NULL,
    UnknownCustomer BOOLEAN NOT NULL,
    ZeroPrice BOOLEAN NOT NULL,
    KEY ix_online_retail_raw_invoice_date (InvoiceDate),
    KEY ix_online_retail_raw_country (Country),
    KEY ix_online_retail_raw_customer (CustomerID),
    KEY ix_online_retail_raw_stock_code (StockCode),
    KEY ix_online_retail_raw_product_cover (StockCode, DescriptionText)
) ENGINE=InnoDB;
