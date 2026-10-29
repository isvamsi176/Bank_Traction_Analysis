-- FinSight educational schema for MySQL 8+
-- Use synthetic data only. Never store real credentials or sensitive financial data.
CREATE DATABASE IF NOT EXISTS finsight_demo CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE finsight_demo;

CREATE TABLE IF NOT EXISTS customers (
  customer_id INT AUTO_INCREMENT PRIMARY KEY,
  display_name VARCHAR(80) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS accounts (
  account_id INT AUTO_INCREMENT PRIMARY KEY,
  customer_id INT NOT NULL,
  account_type ENUM('Savings','Current','Student') NOT NULL,
  opening_balance DECIMAL(14,2) NOT NULL DEFAULT 0 CHECK (opening_balance >= 0),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_accounts_customer FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE IF NOT EXISTS transactions (
  transaction_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  account_id INT NOT NULL,
  transaction_date DATE NOT NULL,
  transaction_type ENUM('Deposit','Withdrawal') NOT NULL,
  amount DECIMAL(14,2) NOT NULL CHECK (amount > 0),
  description VARCHAR(180) NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_transactions_account_date (account_id, transaction_date),
  INDEX idx_transactions_type_date (transaction_type, transaction_date),
  CONSTRAINT fk_transactions_account FOREIGN KEY (account_id) REFERENCES accounts(account_id)
);

-- Balance is intentionally computed in the application:
-- opening_balance + SUM(deposits) - SUM(withdrawals).
