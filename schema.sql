-- Run once against RDS (see docs/DEPLOYMENT.md). Replace the password first.
CREATE DATABASE IF NOT EXISTS capstone CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE capstone;

CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(80) NOT NULL,
  email VARCHAR(120) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS notes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  content VARCHAR(500) NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_notes_user (user_id),
  CONSTRAINT fk_notes_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Least-privilege app account: data access only (no DROP/ALTER/GRANT); TLS required.
CREATE USER IF NOT EXISTS 'appuser'@'%' IDENTIFIED BY 'CHANGE_ME_STRONG_PASSWORD' REQUIRE SSL;
GRANT SELECT, INSERT, UPDATE, DELETE ON capstone.* TO 'appuser'@'%';
FLUSH PRIVILEGES;
